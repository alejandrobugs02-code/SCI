"""Orquestador de Canales con IA.

Decide el canal óptimo por deudor (next-best-action) priorizando lo digital en
mora temprana y respetando la disponibilidad de cada canal por cliente
(canal_whatsapp/sms/llamada/campo). Proyecta el costo de la campaña, el ahorro
vs. el modelo tradicional, el costo por canal y la cartera por tramo de mora.
"""
from . import uplift
from .nba import CANALES, valor_esperado

UMBRALES_DEFAULT: dict = {
    "dias_temprana": 30,
    "dias_media": 60,
    "dias_tardia": 90,
    "monto_riesgo_temprano": 1000.0,
    "monto_voz_humano": 3000.0,
    "monto_visita": 5000.0,
}

# Disponibilidad de cada canal según las columnas del cliente.
DISPONIBILIDAD = {
    "whatsapp": "canal_whatsapp",
    "sms": "canal_sms",
    "voz_ai": "canal_llamada",
    "llamada_humana": "canal_llamada",
    "visita": "canal_campo",
}
ORDEN_FALLBACK = ["whatsapp", "sms", "voz_ai", "llamada_humana", "visita"]


def _disponible(canal: str, deudor: dict) -> bool:
    return bool(deudor.get(DISPONIBILIDAD[canal], True))


def asignar_canal(deudor: dict, umbrales: dict | None = None, canales: dict | None = None) -> dict:
    """Decide el next-best-action de un deudor (dict).

    Política de gestión total del banco: **siempre** se asigna un canal de
    contacto, salvo el opt-out (exclusión legal, Ley 29733).

    - Opt-out / sin consentimiento → excluido (único "no_contactar"; no se reasigna).
    - Con datos de incrementalidad (`tiene_uplift`): el motor de uplift elige el
      canal que más mueve el pago. Si ningún canal aporta valor incremental (lo
      que antes era "no contactar"), se **re-evalúa por la escalera de mora**
      (visita de campo solo para los casos más duros), conservando el segmento.
    - Sin datos de uplift: escalera de mora directa (guardrail/demo).
    """
    u = {**UMBRALES_DEFAULT, **(umbrales or {})}
    cat = canales or CANALES

    # Opt-out: exclusión legal. Es el único caso que se mantiene como no_contactar.
    if deudor.get("opt_out"):
        return {
            "canal": "ninguno", "nombre": "—", "categoria": "Excluido",
            "costo": 0.0, "valor_esperado": 0.0, "accion": "no_contactar",
            "segmento": "excluido",
            "motivo": "Cliente con opt-out / sin consentimiento: excluido de la campaña.",
        }

    if deudor.get("tiene_uplift"):
        rec = uplift.decidir(deudor, cat)
        if rec.get("accion") == "contactar":
            return rec
        # El uplift no encontró valor incremental en ningún canal. El banco no
        # acepta "no contactar": se re-evalúa por la escalera de mora.
        rec_mora = _asignar_por_mora(deudor, u, cat)
        rec_mora["segmento"] = rec.get("segmento")
        rec_mora["uplift"] = rec.get("uplift")
        rec_mora["motivo"] = (
            f"Sin valor incremental por canal ({rec.get('segmento', 'n/d')}); por "
            f"política de gestión total se asigna {rec_mora['nombre']} según su mora."
        )
        return rec_mora

    return _asignar_por_mora(deudor, u, cat)


def _asignar_por_mora(deudor: dict, u: dict, cat: dict) -> dict:
    """Escalera de costo creciente por tramo de mora × monto × riesgo.

    Asume un deudor contactable (el opt-out se filtra en `asignar_canal`).
    Aplica fallback por disponibilidad de canal del cliente.
    """
    monto = float(deudor.get("monto_deuda") or 0)
    dias = int(deudor.get("dias_mora") or 0)
    riesgo = deudor.get("riesgo", "medio")

    if dias <= 0:
        canal = "sms"
        motivo = "Preventivo (al día / por vencer): SMS unidireccional de bajo costo."
    elif dias <= u["dias_temprana"]:
        if not _disponible("whatsapp", deudor):
            canal = "sms"
            motivo = "Mora temprana sin WhatsApp: recordatorio por SMS."
        elif riesgo == "alto" and monto >= u["monto_riesgo_temprano"]:
            canal = "voz_ai"
            motivo = "Mora temprana de alto riesgo y monto: refuerzo con Voz AI."
        else:
            canal = "whatsapp"
            motivo = "Mora temprana: gestión interactiva con agente IA en WhatsApp."
    elif dias <= u["dias_media"]:
        if monto < u["monto_voz_humano"]:
            canal = "voz_ai"
            motivo = "Mora media: Voz AI persuasiva a bajo costo unitario."
        else:
            canal = "llamada_humana"
            motivo = "Mora media de monto alto: negociación con agente humano."
    elif dias <= u["dias_tardia"]:
        canal = "llamada_humana"
        motivo = "Mora tardía: gestión humana para acordar plan de pago."
    else:
        if monto >= u["monto_visita"]:
            canal = "visita"
            motivo = "Mora crítica de monto alto: visita de campo como último recurso."
        else:
            canal = "llamada_humana"
            motivo = "Mora crítica: gestión humana antes de escalar a campo."

    # Fallback por disponibilidad del canal en el cliente.
    if not _disponible(canal, deudor):
        for alt in ORDEN_FALLBACK:
            if _disponible(alt, deudor):
                canal = alt
                motivo += " (ajustado por disponibilidad de canal)."
                break

    c = cat[canal]
    return {
        "canal": canal, "nombre": c["nombre"], "categoria": c["categoria"],
        "costo": c["costo"], "valor_esperado": valor_esperado(canal, monto, cat),
        "motivo": motivo, "accion": "contactar",
    }


def asignar_canal_baseline(dias_mora: int, monto: float) -> str:
    """Modelo tradicional (pre-digital): contact center humano + campo."""
    if dias_mora <= 90:
        return "llamada_humana"
    return "visita" if monto >= 3000 else "llamada_humana"


def plan_campania(deudores: list[dict], umbrales: dict | None = None,
                  canales: dict | None = None) -> dict:
    """Plan de campaña: asignación, costo por canal, ahorro y GAP proyectado.

    Política de gestión total: se contacta a todos los no excluidos (opt-out).
    El ahorro vs. el modelo tradicional viene de la **sustitución de canal**: el
    uplift (o la escalera de mora) elige el canal más barato que funciona y
    escala a humano/campo solo cuando hace falta, mientras el baseline manda todo
    a contact center / visita.
    """
    cat = canales or CANALES
    por_canal: dict[str, dict] = {}
    costo_opt = costo_base = recupero = 0.0
    contactabilidad = promesas = 0.0
    excluidos = gestionados = 0
    deuda_total = 0.0

    for d in deudores:
        monto = float(d.get("monto_deuda") or 0)
        deuda_total += monto
        if d.get("opt_out"):
            excluidos += 1
            continue

        rec = asignar_canal(d, umbrales, cat)

        # Baseline tradicional (contact center humano + campo): contacta a TODOS
        # los no excluidos → contraste para el ahorro por sustitución de canal.
        cb = asignar_canal_baseline(int(d.get("dias_mora") or 0), monto)
        costo_base += cat[cb]["costo"]

        gestionados += 1
        canal = rec["canal"]
        c = cat[canal]
        b = por_canal.setdefault(
            canal,
            {"nombre": c["nombre"], "categoria": c["categoria"],
             "deudores": 0, "monto": 0.0, "costo": 0.0},
        )
        b["deudores"] += 1
        b["monto"] = round(b["monto"] + monto, 2)
        b["costo"] = round(b["costo"] + c["costo"], 2)

        costo_opt += c["costo"]
        recupero += c["tasa_pago"] * monto
        contactabilidad += c["contactabilidad"]
        promesas += c["tasa_pago"]

    ahorro = round(costo_base - costo_opt, 2)
    ahorro_pct = round(ahorro / costo_base * 100, 1) if costo_base else 0.0
    contact_rate = round(contactabilidad / gestionados * 100, 1) if gestionados else 0.0
    promesas_rate = round(promesas / gestionados * 100, 1) if gestionados else 0.0

    return {
        "deudores_gestionados": gestionados,
        "suprimidos": 0,  # política de gestión total: no se suprime a nadie
        "excluidos_opt_out": excluidos,
        "deuda_total": round(deuda_total, 2),
        "costo_optimizado": round(costo_opt, 2),
        "costo_baseline": round(costo_base, 2),
        "ahorro_soles": ahorro,
        "ahorro_pct": ahorro_pct,
        "recupero_esperado": round(recupero, 2),
        "por_canal": por_canal,
        "proyeccion_gap": {
            "contactabilidad_pct": contact_rate,
            "promesas_pago_pct": promesas_rate,
            "gap_pct": round(contact_rate - promesas_rate, 1),
        },
    }


def cartera_mora_canal(deudores: list[dict], umbrales: dict | None = None,
                       canales: dict | None = None) -> list[dict]:
    """Distribución de la cartera: monto y nº de deudores por tramo de mora × canal."""
    u = {**UMBRALES_DEFAULT, **(umbrales or {})}
    cat = canales or CANALES
    edges = [
        ("Al día / preventivo", lambda x: x <= 0),
        (f"1–{u['dias_temprana']}d", lambda x: 1 <= x <= u["dias_temprana"]),
        (f"{u['dias_temprana'] + 1}–{u['dias_media']}d", lambda x: u["dias_temprana"] < x <= u["dias_media"]),
        (f"{u['dias_media'] + 1}–{u['dias_tardia']}d", lambda x: u["dias_media"] < x <= u["dias_tardia"]),
        (f"{u['dias_tardia'] + 1}d+", lambda x: x > u["dias_tardia"]),
    ]

    filas = []
    for etiqueta, test in edges:
        fila: dict = {"tramo": etiqueta, "deudores": 0, "monto": 0.0}
        for canal in cat:
            fila[canal] = 0.0
            fila[f"{canal}_n"] = 0
        for d in deudores:
            if d.get("opt_out"):
                continue
            if not test(int(d.get("dias_mora") or 0)):
                continue
            rec = asignar_canal(d, umbrales, cat)
            canal = rec["canal"]
            monto = float(d.get("monto_deuda") or 0)
            fila[canal] = round(fila[canal] + monto, 2)
            fila[f"{canal}_n"] += 1
            fila["deudores"] += 1
            fila["monto"] = round(fila["monto"] + monto, 2)
        filas.append(fila)
    return filas
