"""Webhook y envío de WhatsApp Cloud API."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core.compliance import esta_permitido
from ..core.config import settings
from ..core.contactos import rank
from ..core.security import get_current_user
from ..models import Contacto, buscar_deudor_por_telefono, get_or_create_config, get_session
from ..services import llm
from ..services import whatsapp as wa_service

router = APIRouter(tags=["whatsapp"])

_WA_ESTADO = {"sent": "enviado", "delivered": "entregado", "read": "leido", "failed": "fallido"}


def _avanzar(contacto: Contacto, nuevo: str) -> None:
    if rank(nuevo) > rank(contacto.estado):
        contacto.estado = nuevo


@router.get("/webhook/whatsapp", response_class=PlainTextResponse)
def verificar_webhook(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_challenge: str = Query("", alias="hub.challenge"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
):
    """Verificación del webhook que exige Meta (GET)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.wa_verify_token:
        return hub_challenge
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


@router.post("/webhook/whatsapp")
async def recibir_mensaje(request: Request, session: Session = Depends(get_session)):
    """Recibe estados de entrega y mensajes entrantes; actualiza el GAP y responde."""
    data = await request.json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError):
        return {"status": "ignored"}

    # 1) Estados de entrega (sent/delivered/read/failed) → avanzan el Contacto.
    for st in value.get("statuses", []):
        contacto = session.exec(
            select(Contacto).where(Contacto.detalle == st.get("id", "")).order_by(Contacto.id.desc())
        ).first()
        if contacto:
            _avanzar(contacto, _WA_ESTADO.get(st.get("status", ""), contacto.estado))
            session.add(contacto)
    if value.get("statuses"):
        session.commit()

    # 2) Mensajes entrantes → marcan "respondido" y dispara el bot LLM.
    mensajes = value.get("messages", [])
    if not mensajes:
        return {"status": "ok"}

    msg = mensajes[0]
    de = msg["from"]
    texto = msg.get("text", {}).get("body", "")
    nombre = value.get("contacts", [{}])[0].get("profile", {}).get("name", "")

    # Si el mensaje muestra disposición de pago, avanza a "intencion_pago".
    nuevo_estado = "intencion_pago" if llm.clasificar_intencion_pago(texto) else "respondido"
    deudor = buscar_deudor_por_telefono(session, de)
    if deudor:
        contacto = session.exec(
            select(Contacto)
            .where(Contacto.deudor_id == deudor.id)
            .order_by(Contacto.id.desc())
        ).first()
        if contacto:
            _avanzar(contacto, nuevo_estado)
            session.add(contacto)
            session.commit()

    prompt = get_or_create_config().prompt_whatsapp or None
    monto = deudor.monto_deuda if deudor else None
    respuesta = llm.responder(texto, nombre=nombre, monto=monto, system_prompt=prompt)
    await wa_service.enviar_texto(de, respuesta)
    return {"status": "ok"}


class PlantillaIn(BaseModel):
    to: str
    plantilla: str = "recordatorio_pago"
    nombre: str = ""
    monto: str = ""


@router.post("/api/whatsapp/plantilla", dependencies=[Depends(get_current_user)])
async def enviar_plantilla(body: PlantillaIn):
    """Inicia conversación saliente con una plantilla utility aprobada."""
    permitido, motivo = esta_permitido()
    if not permitido:
        raise HTTPException(status_code=409, detail=motivo)
    variables = [v for v in [body.nombre, body.monto] if v]
    try:
        return await wa_service.enviar_plantilla(
            body.to, body.plantilla, variables=variables or None
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e))
