"""Endpoint de envío de SMS (Twilio)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.compliance import esta_permitido
from ..core.security import get_current_user
from ..services import twilio_sms

router = APIRouter(prefix="/api/sms", tags=["sms"], dependencies=[Depends(get_current_user)])


class SMSIn(BaseModel):
    to: str
    texto: str


@router.post("/enviar")
def enviar(body: SMSIn):
    permitido, motivo = esta_permitido()
    if not permitido:
        raise HTTPException(status_code=409, detail=motivo)
    try:
        sid = twilio_sms.enviar_sms(body.to, body.texto)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e))
    return {"status": "enviado", "sid": sid}
