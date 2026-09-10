"""Cliente de WhatsApp Cloud API (Meta) vía Graph API.

Envío saliente: usa una plantilla `utility` aprobada para iniciar la
conversación; cuando el cliente responde se abre la ventana de 24 h y puedes
mandar texto libre (gratis) con `enviar_texto`.
"""
import httpx

from ..core.config import settings

GRAPH = "https://graph.facebook.com"


def _url() -> str:
    return f"{GRAPH}/{settings.wa_api_version}/{settings.wa_phone_number_id}/messages"


def _headers() -> dict:
    if not settings.wa_access_token or not settings.wa_phone_number_id:
        raise RuntimeError("Faltan credenciales de WhatsApp en .env (WA_ACCESS_TOKEN / WA_PHONE_NUMBER_ID)")
    return {
        "Authorization": f"Bearer {settings.wa_access_token}",
        "Content-Type": "application/json",
    }


async def enviar_texto(to: str, texto: str) -> dict:
    """Mensaje de texto libre (solo válido dentro de la ventana de 24 h)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": texto},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(_url(), headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()


async def enviar_plantilla(
    to: str,
    plantilla: str,
    idioma: str = "es",
    variables: list[str] | None = None,
) -> dict:
    """Plantilla aprobada (categoría utility para recordatorios de pago)."""
    componentes = []
    if variables:
        componentes.append(
            {
                "type": "body",
                "parameters": [{"type": "text", "text": v} for v in variables],
            }
        )
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": plantilla,
            "language": {"code": idioma},
            "components": componentes,
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(_url(), headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()
