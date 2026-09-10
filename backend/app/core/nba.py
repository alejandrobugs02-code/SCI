"""Catálogo de canales y economía base (costo, tasa de pago, contactabilidad).

Los valores son editables desde la página de Configuración (ver
`models.canales_actuales`). Las funciones aceptan un `canales` opcional para
usar la economía vigente; si se omite, usan estos defaults.
"""

CANALES: dict[str, dict] = {
    "whatsapp":       {"nombre": "WhatsApp",        "costo": 0.10, "tasa_pago": 0.535, "contactabilidad": 0.72, "orden": 1, "categoria": "Interactivo IA"},
    "sms":            {"nombre": "SMS",             "costo": 0.20, "tasa_pago": 0.450, "contactabilidad": 0.60, "orden": 2, "categoria": "Preventivo"},
    "voz_ai":         {"nombre": "Voz AI",          "costo": 0.80, "tasa_pago": 0.500, "contactabilidad": 0.66, "orden": 3, "categoria": "Interactivo IA"},
    "llamada_humana": {"nombre": "Llamada humana",  "costo": 1.50, "tasa_pago": 0.470, "contactabilidad": 0.55, "orden": 4, "categoria": "Alto costo"},
    "visita":         {"nombre": "Visita de campo", "costo": 8.00, "tasa_pago": 0.480, "contactabilidad": 0.62, "orden": 5, "categoria": "Crítico"},
}


def valor_esperado(canal: str, monto: float, canales: dict | None = None) -> float:
    """Valor esperado = tasa_pago * monto - costo del canal."""
    c = (canales or CANALES)[canal]
    return round(c["tasa_pago"] * monto - c["costo"], 2)


def tabla_valor_esperado(monto: float, canales: dict | None = None) -> list[dict]:
    cat = canales or CANALES
    return [
        {
            "canal": key,
            "nombre": c["nombre"],
            "categoria": c["categoria"],
            "costo": c["costo"],
            "tasa_pago": c["tasa_pago"],
            "valor_esperado": valor_esperado(key, monto, cat),
        }
        for key, c in cat.items()
    ]
