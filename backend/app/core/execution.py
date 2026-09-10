"""Planificación de la ejecución automatizada de estrategias.

Reparte a los deudores en colas según la decisión del orquestador (next-best-action):

- **Canales automatizables** (WhatsApp, SMS, Voz AI) → se ejecutan en 3 colas que
  corren a la vez (concurrentes), cada una procesando en orden de prioridad
  (mayor riesgo/monto/mora primero) y con *throttling* para no saturar al
  servidor ni a los proveedores.
- **Canales de gestión humana** (llamada humana, visita de campo) → NO se
  automatizan: se devuelven para generar un reporte descargable con sus datos.
- **Excluidos** (opt-out / sin consentimiento) → quedan fuera de la campaña.
"""
from .orchestrator import asignar_canal

# Canales que el sistema puede ejecutar solo (una cola por canal).
CANALES_AUTOMATIZABLES: tuple[str, ...] = ("whatsapp", "sms", "voz_ai")
# Canales que requieren a una persona: solo se reportan, no se disparan.
CANALES_GESTION_HUMANA: tuple[str, ...] = ("llamada_humana", "visita")


def _score(d: dict) -> float:
    """Riesgo normalizado a 0–1 (mayor = más riesgo).

    Prefiere `prob_default` (ya en 0–1 y orientado a riesgo). Si no está, cae al
    `score_riesgo` normalizado (el dataset puede venir en 0–100 o 0–1).
    """
    pd = d.get("prob_default")
    if pd is not None:
        return float(pd)
    s = float(d.get("score_riesgo") or 0)
    return s / 100 if s > 1 else s


def prioridad(d: dict) -> tuple[float, float, int]:
    """Clave de orden dentro de una cola: primero mayor riesgo, monto y mora."""
    return (
        -_score(d),
        -float(d.get("monto_deuda") or 0),
        -int(d.get("dias_mora") or 0),
    )


def planificar(
    deudores: list[dict],
    umbrales: dict | None = None,
    canales: dict | None = None,
) -> tuple[dict[str, list[dict]], list[dict], list[dict], list[dict]]:
    """Asigna canal a cada deudor y arma las colas de ejecución.

    Devuelve `(colas, gestion_humana, suprimidos, excluidos)` donde `colas` es
    `{canal: [items]}` y cada item es `{"deudor": dict, "recomendacion": dict}`,
    ya ordenado por prioridad. `excluidos` = opt-out / sin consentimiento.
    `suprimidos` es una red de seguridad: bajo la política de gestión total el
    orquestador no suprime a nadie, así que normalmente queda vacío.
    """
    colas: dict[str, list[dict]] = {c: [] for c in CANALES_AUTOMATIZABLES}
    gestion_humana: list[dict] = []
    suprimidos: list[dict] = []
    excluidos: list[dict] = []

    for d in deudores:
        rec = asignar_canal(d, umbrales, canales)
        item = {"deudor": d, "recomendacion": rec}
        # Único "no contactar" posible: opt-out (canal "ninguno") → excluido. El
        # resto (incl. los que el uplift habría suprimido) ya trae un canal real.
        if rec.get("accion") == "no_contactar":
            (excluidos if rec["canal"] == "ninguno" else suprimidos).append(item)
            continue
        canal = rec["canal"]
        if canal in CANALES_AUTOMATIZABLES:
            colas[canal].append(item)
        elif canal in CANALES_GESTION_HUMANA:
            gestion_humana.append(item)
        else:  # "ninguno": opt-out / sin consentimiento
            excluidos.append(item)

    for canal in colas:
        colas[canal].sort(key=lambda it: prioridad(it["deudor"]))
    gestion_humana.sort(key=lambda it: prioridad(it["deudor"]))
    return colas, gestion_humana, suprimidos, excluidos
