"""Bot conversacional de cobranza (LLM) para la ventana de 24 h de WhatsApp.

Soporta varios proveedores que hablan la API de chat de OpenAI (Gemini, Groq,
OpenAI) cambiando solo `base_url` y el modelo desde `.env`. El tono, las reglas
de vocabulario y el límite de emojis viven en `prompts.SYSTEM_PROMPT_WHATSAPP`
(lineamientos de marca SCI).
"""
from openai import OpenAI

from ..core.config import settings
from .prompts import SYSTEM_PROMPT_WHATSAPP

# Endpoints compatibles con la API de OpenAI por proveedor (gratis → de pago).
_BASE_URLS = {
    "openai": "",  # endpoint por defecto del SDK
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
}

_client: OpenAI | None = None
_firma: tuple[str, str] | None = None  # (api_key, base_url) con la que se creó


def _resolver() -> tuple[str, str, str]:
    """Devuelve (api_key, base_url, modelo) según el proveedor configurado."""
    provider = (settings.llm_provider or "openai").lower()
    base_url = settings.llm_base_url or _BASE_URLS.get(provider, "")
    api_key = settings.llm_api_key or settings.openai_api_key
    modelo = settings.llm_model or settings.openai_model
    return api_key, base_url, modelo


def _get_client() -> tuple[OpenAI, str]:
    """Cliente OpenAI (cacheado) + modelo a usar; se recrea si cambia la config."""
    global _client, _firma
    api_key, base_url, modelo = _resolver()
    if not api_key:
        raise RuntimeError(
            "Falta la API key del LLM en .env (LLM_API_KEY o, para OpenAI, OPENAI_API_KEY)."
        )
    firma = (api_key, base_url)
    if _client is None or _firma != firma:
        _client = OpenAI(api_key=api_key, base_url=base_url or None)
        _firma = firma
    return _client, modelo


def responder(
    mensaje_usuario: str,
    nombre: str = "",
    monto: float | None = None,
    system_prompt: str | None = None,
    historial: list[dict] | None = None,
    cerrar: bool = False,
) -> str:
    """Genera la respuesta del agente IA de WhatsApp para un mensaje entrante.

    `system_prompt` permite inyectar el prompt editado en la página de
    Configuración; si es None, usa el de marca por defecto. `historial` es la
    lista de turnos previos ({"role": "user"/"assistant", "content": ...}) para
    dar memoria a la conversación. `cerrar=True` fuerza una despedida (cuando el
    cliente se está despidiendo), para que la respuesta cierre la conversación.
    """
    base = system_prompt or SYSTEM_PROMPT_WHATSAPP
    contexto = f"\n# CONTEXTO DEL CLIENTE\nNombre: {nombre or 'desconocido'}"
    if monto:
        contexto += f"\nSaldo pendiente: S/{monto:.2f}"
    if cerrar:
        contexto += (
            "\n\n# INSTRUCCIÓN INMEDIATA\nEl cliente se está despidiendo. "
            "Despídete con calidez en 1 o 2 frases, agradece y confirma en una "
            "línea lo acordado (si lo hubo). NO hagas más preguntas ni ofrezcas "
            "más información: este es tu último mensaje."
        )

    mensajes: list[dict] = [{"role": "system", "content": base + contexto}]
    if historial:
        mensajes.extend(historial)
    mensajes.append({"role": "user", "content": mensaje_usuario})

    client, modelo = _get_client()
    resp = client.chat.completions.create(
        model=modelo,
        messages=mensajes,
        temperature=0.5,
        max_tokens=300,
    )
    return (resp.choices[0].message.content or "").strip()


def responder_asistente(
    mensaje: str,
    system_prompt: str,
    historial: list[dict] | None = None,
) -> str:
    """Respuesta del asistente interno del panel (analista de cobranza + guía).

    A diferencia de `responder` (bot de cara al cliente), este agente habla con
    el equipo de SCI: interpreta los KPIs/estrategias del `system_prompt`
    (que ya trae el snapshot de datos) y ayuda a navegar el sistema.
    """
    mensajes: list[dict] = [{"role": "system", "content": system_prompt}]
    if historial:
        mensajes.extend(historial[-10:])  # acota la memoria a los últimos turnos
    mensajes.append({"role": "user", "content": mensaje})

    client, modelo = _get_client()
    resp = client.chat.completions.create(
        model=modelo,
        messages=mensajes,
        temperature=0.3,
        max_tokens=600,
    )
    return (resp.choices[0].message.content or "").strip()


_CLASIFICADOR_SISTEMA = (
    "Eres un clasificador. Responde con UNA sola palabra: PAGO, CIERRE u OTRO.\n"
    "- PAGO: el cliente expresa intención, disposición o compromiso de pagar "
    "(total o parcial, ahora o en una fecha). Ej: 'el viernes pago', 'abono una parte'.\n"
    "- CIERRE: el cliente se despide o quiere terminar la conversación. "
    "Ej: 'gracias, eso es todo', 'ok chau', 'hasta luego', 'ya, listo'.\n"
    "- OTRO: cualquier otro caso (dudas, excusas, saludos, 'no puedo')."
)


def clasificar_mensaje(mensaje_cliente: str) -> str:
    """Clasifica el mensaje del cliente en 'PAGO', 'CIERRE' u 'OTRO'."""
    if not mensaje_cliente.strip():
        return "OTRO"
    try:
        client, modelo = _get_client()
        resp = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": _CLASIFICADOR_SISTEMA},
                {"role": "user", "content": mensaje_cliente},
            ],
            temperature=0,
            max_tokens=4,
        )
        salida = (resp.choices[0].message.content or "").strip().upper()
        if "PAGO" in salida:
            return "PAGO"
        if "CIERRE" in salida:
            return "CIERRE"
        return "OTRO"
    except Exception:  # noqa: BLE001
        return "OTRO"


def clasificar_intencion_pago(mensaje_cliente: str) -> bool:
    """Devuelve True si el mensaje del cliente muestra intención de pago."""
    return clasificar_mensaje(mensaje_cliente) == "PAGO"


def extraer_promesa(mensaje_cliente: str, hoy: str | None = None) -> dict:
    """Extrae una promesa de pago del mensaje: {monto, fecha_texto, fecha}.

    `monto` es float|None; `fecha_texto` es lo que dijo el cliente ("mañana");
    `fecha` es 'YYYY-MM-DD' o None si no se pudo interpretar.
    """
    from datetime import date

    hoy = hoy or date.today().isoformat()
    sistema = (
        f"Hoy es {hoy}. Extrae la promesa de pago del mensaje del cliente. "
        'Responde SOLO un JSON válido con las claves: '
        '"monto" (número en soles o null), "fecha_texto" (lo que dijo, o ""), '
        '"fecha" ("YYYY-MM-DD" calculada desde hoy, o null). '
        "Si no hay promesa concreta, usa null."
    )
    try:
        client, modelo = _get_client()
        resp = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": sistema},
                {"role": "user", "content": mensaje_cliente},
            ],
            temperature=0,
            max_tokens=60,
            response_format={"type": "json_object"},
        )
        import json

        data = json.loads(resp.choices[0].message.content or "{}")
        monto = data.get("monto")
        return {
            "monto": float(monto) if isinstance(monto, (int, float)) else None,
            "fecha_texto": str(data.get("fecha_texto") or ""),
            "fecha": data.get("fecha") or None,
        }
    except Exception:  # noqa: BLE001
        return {"monto": None, "fecha_texto": "", "fecha": None}
