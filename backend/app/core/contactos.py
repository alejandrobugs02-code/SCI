"""Estados de un Contacto y su jerarquía.

El embudo (GAP) avanza por estos estados sin retroceder. "intencion_pago" se
marca cuando el cliente expresa disposición/compromiso de pago en la conversación
(no es un pago confirmado, que sería "pagado").
"""

ESTADOS_RANK: dict[str, int] = {
    "fallido": 0,
    "enviado": 1,
    "entregado": 2,
    "leido": 3,
    "respondido": 4,
    "intencion_pago": 5,
    "pagado": 6,
}


def rank(estado: str) -> int:
    return ESTADOS_RANK.get(estado, 0)
