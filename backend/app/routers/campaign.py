"""Campaña: ejecución de envíos reales y métricas de engagement (GAP en vivo)."""
import asyncio
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core import cache, execution
from ..core.compliance import esta_permitido
from ..core.config import settings
from ..core.contactos import rank
from ..core.security import get_current_user, require_admin
from ..models import (
    Contacto,
    Deudor,
    Mensaje,
    Promesa,
    canales_actuales,
    get_session,
    umbrales_actuales,
)
from ..services import twilio_sms, vapi
from ..services import whatsapp as wa_service

router = APIRouter(prefix="/api/campaign", tags=["campaña"], dependencies=[Depends(get_current_user)])

CANALES_ENVIABLES = {"sms", "whatsapp", "voz_ai"}

# Pausa entre envíos dentro de una misma cola (anti-saturación del servidor/proveedor).
THROTTLE_SEGUNDOS = 0.3


class EnvioIn(BaseModel):
    deudor_id: int
    canal: str  # sms · whatsapp · voz_ai


def _texto_recordatorio(d: Deudor) -> str:
    saldo = f" (saldo S/{d.monto_deuda:.2f})" if d.monto_deuda else ""
    nombre = d.nombre or "estimado cliente"
    return (
        f"Hola {nombre}, le saludamos de SCI. Le recordamos su cuota "
        f"pendiente{saldo}. Escríbanos y juntos coordinamos su pago."
    )


async def _enviar_whatsapp(d: Deudor) -> str:
    """Envía el recordatorio por WhatsApp según el proveedor (cloud/neonize)."""
    if settings.wa_provider == "neonize":
        from ..services import whatsapp_neonize
        # neonize es síncrono: a un hilo para no bloquear el bucle async.
        return await asyncio.to_thread(
            whatsapp_neonize.enviar_texto, d.telefono, _texto_recordatorio(d)
        )
    res = await wa_service.enviar_plantilla(
        d.telefono, "recordatorio_pago",
        variables=[d.nombre or "cliente", f"{d.monto_deuda:.2f}"],
    )
    return res.get("messages", [{}])[0].get("id", "") if isinstance(res, dict) else ""


@router.post("/enviar")
async def enviar(body: EnvioIn, session: Session = Depends(get_session)):
    if body.canal not in CANALES_ENVIABLES:
        raise HTTPException(status_code=400, detail=f"Canal no enviable: {body.canal}")

    deudor = session.get(Deudor, body.deudor_id)
    if not deudor:
        raise HTTPException(status_code=404, detail="Deudor no encontrado")
    if deudor.opt_out:
        raise HTTPException(status_code=409, detail="Cliente con opt-out: no se puede contactar")
    if not deudor.telefono:
        raise HTTPException(status_code=422, detail="El cliente no tiene teléfono. Complétalo primero.")

    permitido, motivo = esta_permitido()
    if not permitido:
        raise HTTPException(status_code=409, detail=motivo)

    costo = canales_actuales().get(body.canal, {}).get("costo", 0.0)
    detalle = ""
    try:
        if body.canal == "sms":
            detalle = twilio_sms.enviar_sms(deudor.telefono, _texto_recordatorio(deudor))
        elif body.canal == "whatsapp":
            detalle = await _enviar_whatsapp(deudor)
        elif body.canal == "voz_ai":
            res = await vapi.iniciar_llamada(
                deudor.telefono, deudor.nombre, deudor.monto_deuda, deudor.documento
            )
            detalle = res.get("id", "") if isinstance(res, dict) else ""
    except Exception as e:  # noqa: BLE001
        contacto = Contacto(deudor_id=deudor.id, canal=body.canal, estado="fallido",
                            costo=0.0, detalle=str(e)[:200])
        session.add(contacto)
        session.commit()
        raise HTTPException(status_code=502, detail=f"Error al enviar: {e}")

    contacto = Contacto(deudor_id=deudor.id, canal=body.canal, estado="enviado",
                        costo=costo, detalle=detalle)
    session.add(contacto)
    session.commit()
    session.refresh(contacto)
    cache.clear()  # la actividad cambió: invalida la analítica cacheada
    return {"status": "enviado", "contacto_id": contacto.id, "canal": body.canal, "detalle": detalle}


class EstadoIn(BaseModel):
    estado: str  # entregado · leido · respondido · pagado · fallido
    monto_pagado: float | None = None


@router.post("/contacto/{contacto_id}/estado")
def actualizar_estado(contacto_id: int, body: EstadoIn, session: Session = Depends(get_session)):
    c = session.get(Contacto, contacto_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    c.estado = body.estado
    if body.monto_pagado is not None:
        c.monto_pagado = body.monto_pagado
    session.add(c)
    session.commit()
    session.refresh(c)
    cache.clear()
    return c


def _embudo(items: list[Contacto], montos: dict[int, float]) -> dict:
    """Embudo acumulativo de un grupo de contactos (global o por canal)."""
    def cuenta(estado_min: str) -> int:
        return sum(1 for c in items if rank(c.estado) >= rank(estado_min))

    enviados = cuenta("enviado")   # excluye fallidos
    entregados = cuenta("entregado")
    vistos = cuenta("leido")
    respondidos = cuenta("respondido")
    intencion = cuenta("intencion_pago")
    pagados = cuenta("pagado")
    monto_intencion = round(
        sum(montos.get(c.deudor_id, 0.0) for c in items
            if rank(c.estado) >= rank("intencion_pago")),
        2,
    )

    def tasa(n: int) -> float:
        return round(n / enviados * 100, 1) if enviados else 0.0

    return {
        "enviados": enviados,
        "entregados": entregados,
        "vistos": vistos,
        "respondidos": respondidos,
        "intencion": intencion,
        "pagados": pagados,
        "monto_intencion": monto_intencion,
        "tasas": {
            "entrega": tasa(entregados),
            "apertura": tasa(vistos),
            "respuesta": tasa(respondidos),
            "intencion": tasa(intencion),
            "pago": tasa(pagados),
        },
    }


@router.get("/metricas")
@cache.ttl_cache("campaign:metricas", 8)
def metricas(session: Session = Depends(get_session)):
    """Engagement en tiempo real (GAP), global y por canal, + gasto mensual."""
    contactos = session.exec(select(Contacto)).all()
    montos = {d.id: d.monto_deuda for d in session.exec(select(Deudor)).all()}
    total = len(contactos)

    glob = _embudo(contactos, montos)
    canales = sorted({c.canal for c in contactos})
    embudo_por_canal = {
        canal: _embudo([c for c in contactos if c.canal == canal], montos)
        for canal in canales
    }

    costo_acumulado = round(sum(c.costo for c in contactos), 2)
    monto_recuperado = round(sum(c.monto_pagado for c in contactos), 2)

    por_mes: dict[str, float] = {}
    for c in contactos:
        k = c.creado_en.strftime("%Y-%m")
        por_mes[k] = round(por_mes.get(k, 0.0) + c.costo, 2)
    gasto_por_mes = [{"mes": k, "costo": v} for k, v in sorted(por_mes.items())]

    por_canal = {
        canal: {
            "enviados": embudo_por_canal[canal]["enviados"],
            "costo": round(sum(c.costo for c in contactos if c.canal == canal), 2),
        }
        for canal in canales
    }

    return {
        "campania_iniciada": total > 0,
        # Globales (compatibilidad):
        "enviados": glob["enviados"],
        "vistos": glob["vistos"],
        "respondidos": glob["respondidos"],
        "intencion": glob["intencion"],
        "pagados": glob["pagados"],
        "costo_acumulado": costo_acumulado,
        "monto_recuperado": monto_recuperado,
        "tasas": glob["tasas"],
        # Detallado:
        "embudo": glob,
        "embudo_por_canal": embudo_por_canal,
        "gasto_por_mes": gasto_por_mes,
        "por_canal": por_canal,
    }


@router.post("/reset", dependencies=[Depends(require_admin)])
def reset_datos(session: Session = Depends(get_session)):
    """Borra la actividad de campaña (contactos, mensajes, promesas) para empezar
    un demo desde cero. NO toca la base de clientes (Deudor) ni la configuración.
    """
    borrados: dict[str, int] = {}
    for modelo, nombre in ((Contacto, "contactos"), (Mensaje, "mensajes"), (Promesa, "promesas")):
        filas = session.exec(select(modelo)).all()
        for fila in filas:
            session.delete(fila)
        borrados[nombre] = len(filas)
    session.commit()
    cache.clear()
    return {"status": "ok", "borrados": borrados}


# ----------------- Ejecución automatizada de estrategias -----------------
class EjecutarIn(BaseModel):
    # Por defecto NO consume créditos: registra envíos simulados para iluminar
    # los dashboards. Poner en False para disparar los envíos reales.
    simular: bool = True


async def _enviar_uno(canal: str, d: Deudor, simular: bool, costo: float) -> tuple[str, float, str]:
    """Ejecuta (o simula) un envío y devuelve (estado, costo, detalle)."""
    if simular:
        return "enviado", costo, "simulado"
    if not d.telefono:
        return "fallido", 0.0, "Sin teléfono"
    try:
        if canal == "sms":
            # El SDK de Twilio es síncrono: a un hilo para no bloquear el bucle.
            detalle = await asyncio.to_thread(
                twilio_sms.enviar_sms, d.telefono, _texto_recordatorio(d)
            )
        elif canal == "whatsapp":
            detalle = await _enviar_whatsapp(d)
        else:  # voz_ai
            res = await vapi.iniciar_llamada(d.telefono, d.nombre, d.monto_deuda, d.documento)
            detalle = res.get("id", "") if isinstance(res, dict) else ""
        return "enviado", costo, detalle
    except Exception as e:  # noqa: BLE001
        return "fallido", 0.0, str(e)[:200]


async def _procesar_cola(
    canal: str, items: list[dict], simular: bool, costo: float
) -> list[tuple[int, str, str, float, str]]:
    """Procesa una cola en orden de prioridad, con throttling entre envíos."""
    resultados: list[tuple[int, str, str, float, str]] = []
    for it in items:
        d: Deudor = it["_obj"]
        estado, c, detalle = await _enviar_uno(canal, d, simular, costo)
        resultados.append((d.id, canal, estado, c, detalle))
        await asyncio.sleep(THROTTLE_SEGUNDOS)
    return resultados


@router.post("/ejecutar", dependencies=[Depends(require_admin)])
async def ejecutar(body: EjecutarIn, session: Session = Depends(get_session)):
    """Ejecuta las estrategias del orquestador.

    Las 3 colas automatizables (WhatsApp · SMS · Voz AI) corren a la vez y, dentro
    de cada una, en orden de prioridad por puntaje. Llamada humana y visita de
    campo NO se automatizan: se cuentan aquí y se descargan vía
    `/reporte-gestion-humana`.
    """
    permitido, motivo = esta_permitido()
    if not permitido:
        raise HTTPException(status_code=409, detail=motivo)

    canales = canales_actuales()
    umbrales = umbrales_actuales()
    deudores_obj = session.exec(select(Deudor)).all()
    por_id = {d.id: d for d in deudores_obj}
    deudores = [d.model_dump() for d in deudores_obj]

    colas, gestion_humana, suprimidos, excluidos = execution.planificar(deudores, umbrales, canales)
    for canal, items in colas.items():
        for it in items:
            it["_obj"] = por_id[it["deudor"]["id"]]

    # Las 3 colas se ejecutan en paralelo; cada una secuencial y con throttling.
    resultados = await asyncio.gather(
        *(
            _procesar_cola(canal, colas[canal], body.simular, canales[canal]["costo"])
            for canal in execution.CANALES_AUTOMATIZABLES
        )
    )

    resumen_colas: dict[str, dict] = {}
    creados = 0
    for canal, grupo in zip(execution.CANALES_AUTOMATIZABLES, resultados):
        enviados = fallidos = 0
        for deudor_id, c, estado, costo, detalle in grupo:
            session.add(Contacto(deudor_id=deudor_id, canal=c, estado=estado,
                                 costo=costo, detalle=detalle))
            creados += 1
            enviados += estado == "enviado"
            fallidos += estado == "fallido"
        resumen_colas[canal] = {"total": len(grupo), "enviados": enviados, "fallidos": fallidos}
    session.commit()
    cache.clear()

    por_canal_humano: dict[str, int] = {}
    for it in gestion_humana:
        cn = it["recomendacion"]["canal"]
        por_canal_humano[cn] = por_canal_humano.get(cn, 0) + 1

    return {
        "simulado": body.simular,
        "contactos_registrados": creados,
        "colas": resumen_colas,
        "gestion_humana": {"total": len(gestion_humana), "por_canal": por_canal_humano},
        "suprimidos": len(suprimidos),
        "excluidos": len(excluidos),
    }


# Columnas (clave del deudor, encabezado legible) del reporte de gestión humana.
_REPORTE_COLUMNAS = [
    ("cliente_id", "Cliente ID"),
    ("nombre", "Nombre"),
    ("documento", "Documento"),
    ("telefono", "Teléfono"),
    ("monto_deuda", "Monto deuda (S/)"),
    ("dias_mora", "Días de mora"),
    ("riesgo", "Riesgo"),
    ("region", "Región"),
    ("zona", "Zona"),
]


@router.get("/reporte-gestion-humana", dependencies=[Depends(require_admin)])
def reporte_gestion_humana(session: Session = Depends(get_session)):
    """CSV descargable con los clientes que requieren llamada humana o visita."""
    deudores = [d.model_dump() for d in session.exec(select(Deudor)).all()]
    _, gestion_humana, _, _ = execution.planificar(
        deudores, umbrales_actuales(), canales_actuales()
    )

    buffer = io.StringIO()
    buffer.write("﻿")  # BOM para que Excel respete los acentos
    writer = csv.writer(buffer)
    writer.writerow([encabezado for _, encabezado in _REPORTE_COLUMNAS]
                    + ["Acción requerida", "Motivo"])
    for it in gestion_humana:
        d, rec = it["deudor"], it["recomendacion"]
        writer.writerow([d.get(clave, "") for clave, _ in _REPORTE_COLUMNAS]
                        + [rec["nombre"], rec["motivo"]])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=reporte_gestion_humana.csv"},
    )
