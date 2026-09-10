"""Endpoint de Voz AI (Vapi)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core.compliance import esta_permitido
from ..core.contactos import rank
from ..core.security import get_current_user
from ..models import Contacto, Promesa, get_session
from ..services import vapi

router = APIRouter(prefix="/api/voz", tags=["voz"], dependencies=[Depends(get_current_user)])

# endedReason que indican que la llamada NO fue contestada (no avanza el embudo).
_NO_CONTESTADA = ("did-not-answer", "no-answer", "voicemail", "busy", "twilio", "failed")


class LlamadaIn(BaseModel):
    numero: str            # destino en formato E.164, p. ej. +51987654321
    nombre: str | None = None
    monto: float | None = None
    dni: str | None = None  # DNI del titular para validar identidad en la llamada


@router.post("/llamar")
async def llamar(body: LlamadaIn):
    permitido, motivo = esta_permitido()
    if not permitido:
        raise HTTPException(status_code=409, detail=motivo)
    try:
        return await vapi.iniciar_llamada(body.numero, body.nombre, body.monto, body.dni)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/sync")
async def sync_llamadas(session: Session = Depends(get_session)):
    """Trae de Vapi el resultado de las llamadas recientes y avanza el embudo:
    'entregado' (contestada) e 'intencion_pago', creando la promesa si la hubo.

    Pensado para llamarse periódicamente desde el dashboard. No requiere webhook
    (consulta directa a la API de Vapi), así funciona en local sin túnel.
    """
    limite = datetime.now() - timedelta(minutes=30)
    recientes = session.exec(
        select(Contacto).where(
            Contacto.canal == "voz_ai",
            Contacto.creado_en >= limite,
        )
    ).all()
    # Solo las que aún no llegaron a "intención de pago" (las demás ya están listas).
    pendientes = [c for c in recientes if rank(c.estado) < rank("intencion_pago")]

    actualizados = 0
    for c in pendientes:
        call_id = (c.detalle or "").strip()
        if len(call_id) < 20:  # el detalle debe ser un id de llamada de Vapi
            continue
        try:
            call = await vapi.obtener_llamada(call_id)
        except Exception:  # noqa: BLE001
            continue
        if call.get("status") != "ended":
            continue  # la llamada sigue en curso

        motivo = (call.get("endedReason") or "").lower()
        contestada = bool(call.get("startedAt")) and not any(k in motivo for k in _NO_CONTESTADA)
        if not contestada:
            continue  # se queda en "enviado": enviada pero no contestada

        analisis = call.get("analysis") or {}
        datos = analisis.get("structuredData") or {}
        if datos:
            intencion = bool(datos.get("intencion_pago"))
        else:
            # Llamadas previas a configurar el structuredDataPlan: cae a successEvaluation.
            intencion = str(analisis.get("successEvaluation")).lower() in ("true", "pass")
        nuevo = "intencion_pago" if intencion else "entregado"
        if rank(nuevo) > rank(c.estado):
            c.estado = nuevo
            session.add(c)
            actualizados += 1
        if intencion and (datos.get("monto_prometido") or datos.get("fecha_compromiso")):
            existe = session.exec(
                select(Promesa).where(Promesa.deudor_id == c.deudor_id)
            ).first()
            if not existe:
                session.add(Promesa(
                    deudor_id=c.deudor_id,
                    monto=float(datos.get("monto_prometido") or 0),
                    fecha_texto=str(datos.get("fecha_compromiso") or ""),
                ))
    session.commit()
    return {"revisados": len(pendientes), "actualizados": actualizados}
