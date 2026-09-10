"""Motor de incrementalidad (uplift) — PDF 4.1.

Cambia la pregunta de "¿quién va a pagar?" a "¿a quién hace pagar el contacto,
que no pagaría solo?". Para cada cliente con datos de uplift decide el canal que
maximiza el **pago incremental** (uplift × monto − costo − fatiga) y, si ningún
canal aporta valor incremental, decide **NO CONTACTAR** (supresión) para ahorrar
costo sin perder recuperación.

El uplift por canal viene precalculado del dataset real (tabla de contactos):
    uplift_canal = P(pago 7d | contacto por canal) − P(pago 7d | sin contacto)
"""

# Canal del sistema → atributo de uplift en el deudor. "llamada" del dataset
# cubre tanto Voz AI como llamada humana; "campo" → visita.
UPLIFT_POR_CANAL: dict[str, str] = {
    "whatsapp": "uplift_whatsapp",
    "sms": "uplift_sms",
    "voz_ai": "uplift_llamada",
    "llamada_humana": "uplift_llamada",
    "visita": "uplift_campo",
}

# Disponibilidad de cada canal según las columnas del cliente (igual que el
# orquestador; duplicado aquí para evitar el import circular).
DISPONIBILIDAD = {
    "whatsapp": "canal_whatsapp",
    "sms": "canal_sms",
    "voz_ai": "canal_llamada",
    "llamada_humana": "canal_llamada",
    "visita": "canal_campo",
}

# Sols de penalización por cada contacto reciente (anti-sobregestión/fatiga).
LAMBDA_FATIGA = 1.0
# Valor incremental mínimo (S/) para que valga la pena contactar; por debajo se
# suprime. 0 = solo contactamos si el pago incremental supera costo + fatiga.
UMBRAL_NO_CONTACTAR = 0.0

# Umbrales de segmentación causal de la cartera (PDF sec. 3).
UMBRAL_PERSUADIBLE = 0.03   # el contacto sí mueve el pago
BASE_SEGURO = 0.60          # paga prácticamente solo
BASE_PERDIDO = 0.25         # no reacciona ni con contacto


def _disponible(canal: str, d: dict) -> bool:
    return bool(d.get(DISPONIBILIDAD[canal], True))


def uplift_de(d: dict, canal: str) -> float:
    return float(d.get(UPLIFT_POR_CANAL[canal]) or 0.0)


def _monto_recuperable(d: dict) -> float:
    """Monto en juego en la ventana de 7 días: la cuota; si no, el saldo."""
    return float(d.get("cuota_mensual") or 0.0) or float(d.get("monto_deuda") or 0.0)


def valor_esperado(d: dict, canal: str, cat: dict) -> float:
    """Valor incremental: uplift × monto − costo del canal − fatiga."""
    up = uplift_de(d, canal)
    monto = _monto_recuperable(d)
    costo = float(cat[canal]["costo"])
    fatiga = LAMBDA_FATIGA * int(d.get("num_contactos_ult7d") or 0)
    return round(up * monto - costo - fatiga, 2)


def mejor_uplift(d: dict) -> float:
    """Mayor uplift entre los canales del dataset (whatsapp/sms/llamada/campo)."""
    return max(
        float(d.get("uplift_whatsapp") or 0.0),
        float(d.get("uplift_sms") or 0.0),
        float(d.get("uplift_llamada") or 0.0),
        float(d.get("uplift_campo") or 0.0),
    )


def segmentar(d: dict) -> str:
    """Segmento causal: persuadible · seguro · perdido · neutro."""
    if mejor_uplift(d) >= UMBRAL_PERSUADIBLE:
        return "persuadible"
    base = float(d.get("prob_pago_base") or 0.0)
    if base >= BASE_SEGURO:
        return "seguro"
    if base <= BASE_PERDIDO:
        return "perdido"
    return "neutro"


def decidir(d: dict, cat: dict) -> dict:
    """Decisión por incrementalidad para un deudor con datos de uplift.

    Devuelve una `recomendacion` compatible con la del orquestador, más las
    claves `accion` ('contactar' | 'no_contactar'), `uplift` y `segmento`.
    """
    if d.get("opt_out"):
        return {
            "canal": "ninguno", "nombre": "—", "categoria": "Excluido",
            "costo": 0.0, "valor_esperado": 0.0, "uplift": 0.0,
            "accion": "no_contactar", "segmento": "excluido",
            "motivo": "Cliente con opt-out / sin consentimiento: excluido de la campaña.",
        }

    candidatos = [
        (canal, valor_esperado(d, canal, cat))
        for canal in cat
        if canal in UPLIFT_POR_CANAL and _disponible(canal, d)
    ]
    if not candidatos:  # ningún canal disponible
        canal, ev = "whatsapp", -1.0
    else:
        canal, ev = max(candidatos, key=lambda x: x[1])

    c = cat[canal]
    up_best = uplift_de(d, canal)
    segmento = segmentar(d)
    base = {
        "canal": canal, "nombre": c["nombre"], "categoria": c["categoria"],
        "costo": c["costo"], "valor_esperado": ev, "uplift": round(up_best, 4),
        "segmento": segmento,
    }

    if ev <= UMBRAL_NO_CONTACTAR:
        base["accion"] = "no_contactar"
        base["motivo"] = (
            f"Uplift insuficiente (máx {up_best:+.2f}): el contacto no mejora el pago. "
            f"Se suprime ({segmento}) para no gastar sin retorno incremental."
        )
    else:
        base["accion"] = "contactar"
        base["motivo"] = (
            f"Persuadible: {c['nombre']} maximiza el pago incremental "
            f"(uplift {up_best:+.2f}, valor S/{ev})."
        )
    return base
