"""Cliente de Vapi para iniciar llamadas de Voz AI salientes.

Requiere un assistant creado en Vapi y un número (importado de Twilio)
registrado como phoneNumberId. Las variables dinámicas (nombre, monto, dni) se
inyectan al prompt del assistant con `assistantOverrides.variableValues`.
"""
import httpx

from ..core.config import settings

VAPI_API = "https://api.vapi.ai"

# --- Conversión de números a palabras (para que el TTS lea montos claros) ---
_UNIDADES = [
    "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho",
    "nueve", "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis",
    "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós",
    "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete",
    "veintiocho", "veintinueve",
]
_DECENAS = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta",
            "ochenta", "noventa"]
_CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos",
             "quinientos", "seiscientos", "setecientos", "ochocientos",
             "novecientos"]


def _menos_de_cien(n: int) -> str:
    if n < 30:
        return _UNIDADES[n]
    d, u = divmod(n, 10)
    return f"{_DECENAS[d]} y {_UNIDADES[u]}" if u else _DECENAS[d]


def _menos_de_mil(n: int) -> str:
    if n == 100:
        return "cien"
    c, r = divmod(n, 100)
    partes = []
    if c:
        partes.append(_CENTENAS[c])
    if r:
        partes.append(_menos_de_cien(r))
    return " ".join(partes)


def _numero_a_palabras(n: int) -> str:
    """Entero (0..999.999.999) a palabras en español: 2800 -> 'dos mil ochocientos'."""
    if n == 0:
        return "cero"
    millones, resto = divmod(n, 1_000_000)
    miles, cientos = divmod(resto, 1000)
    partes = []
    if millones:
        partes.append("un millón" if millones == 1
                      else f"{_numero_a_palabras(millones)} millones")
    if miles:
        partes.append("mil" if miles == 1 else f"{_menos_de_mil(miles)} mil")
    if cientos:
        partes.append(_menos_de_mil(cientos))
    return " ".join(partes)


def _apocopar(texto: str) -> str:
    """'uno' -> 'un', 'veintiuno' -> 'veintiún' antes de un sustantivo masculino."""
    if texto.endswith("veintiuno"):
        return texto[:-len("veintiuno")] + "veintiún"
    if texto.endswith("uno"):
        return texto[:-3] + "un"
    return texto


def _formato_monto(monto: float) -> str:
    """Convierte el monto a palabras para que el TTS lo lea claro y natural.

    2800.0 -> "dos mil ochocientos soles"
    150.5  -> "ciento cincuenta soles con cincuenta céntimos"
    Evita que la voz deletree "dos ocho cero cero" o lea "punto cero cero".
    """
    soles = int(monto)
    centimos = round((monto - soles) * 100)
    if soles == 1:
        texto = "un sol"
    else:
        texto = f"{_apocopar(_numero_a_palabras(soles))} soles"
    if centimos:
        cent = ("un céntimo" if centimos == 1
                else f"{_apocopar(_numero_a_palabras(centimos))} céntimos")
        texto += f" con {cent}"
    return texto


async def iniciar_llamada(
    numero_destino: str,
    nombre: str | None = None,
    monto: float | None = None,
    dni: str | None = None,
) -> dict:
    if not settings.vapi_api_key:
        raise RuntimeError("Falta VAPI_API_KEY en .env")
    if not settings.vapi_assistant_id or not settings.vapi_phone_number_id:
        raise RuntimeError("Faltan VAPI_ASSISTANT_ID / VAPI_PHONE_NUMBER_ID en .env")

    payload: dict = {
        "assistantId": settings.vapi_assistant_id,
        "phoneNumberId": settings.vapi_phone_number_id,
        "customer": {"number": numero_destino},
    }
    if nombre or monto or dni:
        # Vapi exige que variableValues sean strings.
        payload["assistantOverrides"] = {
            "variableValues": {
                "nombre": nombre or "",
                "monto": _formato_monto(monto) if monto else "0 soles",
                "dni": dni or "",
            }
        }

    headers = {
        "Authorization": f"Bearer {settings.vapi_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{VAPI_API}/call", headers=headers, json=payload)
        if r.status_code >= 400:
            # Surfacea el motivo real de Vapi (p. ej. "Free Vapi numbers do not
            # support international calls") en vez de un 400 genérico.
            try:
                detalle = r.json().get("message") or r.text
            except Exception:  # noqa: BLE001
                detalle = r.text
            raise RuntimeError(f"Vapi {r.status_code}: {detalle}")
        return r.json()


async def obtener_llamada(call_id: str) -> dict:
    """Consulta el estado y resultado de una llamada en Vapi (GET /call/{id}).

    Se usa para sincronizar el embudo sin webhooks: trae status, endedReason,
    startedAt y el `analysis.structuredData` (intención de pago, monto, fecha).
    """
    if not settings.vapi_api_key:
        raise RuntimeError("Falta VAPI_API_KEY en .env")
    headers = {"Authorization": f"Bearer {settings.vapi_api_key}"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{VAPI_API}/call/{call_id}", headers=headers)
        if r.status_code >= 400:
            raise RuntimeError(f"Vapi {r.status_code}: {r.text[:200]}")
        return r.json()
