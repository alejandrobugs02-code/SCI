"""Cliente de SMS vía Twilio."""
from twilio.rest import Client

from ..core.config import settings


def _client() -> Client:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise RuntimeError("Faltan credenciales de Twilio en .env (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)")
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def enviar_sms(to: str, texto: str) -> str:
    """Envía un SMS transaccional y devuelve el SID del mensaje."""
    msg = _client().messages.create(
        to=to,
        from_=settings.twilio_sms_from,
        body=texto,
    )
    return msg.sid
