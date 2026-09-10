"""Analítica de la operación REAL: datos recolectados (Contacto, Deudor, Promesa).

A diferencia de /orchestrator (proyección del plan), aquí todo sale de lo que de
verdad pasó: contactos, estados del embudo, costos reales, intención de pago y
las promesas de pago extraídas de las conversaciones.
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..core import uplift
from ..core.cache import ttl_cache
from ..core.contactos import rank
from ..core.orchestrator import asignar_canal
from ..core.security import get_current_user
from ..models import (
    Contacto,
    Deudor,
    Promesa,
    canales_actuales,
    get_session,
    umbrales_actuales,
)

router = APIRouter(
    prefix="/api/analytics", tags=["analítica"],
    dependencies=[Depends(get_current_user)],
)


def _mejor_estado(contactos: list[Contacto]) -> dict[int, int]:
    """deudor_id → mayor rank de estado alcanzado (mejor punto del embudo)."""
    mejor: dict[int, int] = {}
    for c in contactos:
        mejor[c.deudor_id] = max(mejor.get(c.deudor_id, 0), rank(c.estado))
    return mejor


def _tasa(n: int, base: int) -> float:
    return round(n / base * 100, 1) if base else 0.0


@router.get("/resumen")
@ttl_cache("analytics:resumen", 8)
def resumen(session: Session = Depends(get_session)):
    """KPIs reales: contactados, respuesta, intención de pago, costo y ROI."""
    deudores = session.exec(select(Deudor)).all()
    contactos = session.exec(select(Contacto)).all()
    promesas = session.exec(select(Promesa)).all()
    monto = {d.id: d.monto_deuda for d in deudores}

    mejor = _mejor_estado(contactos)
    en = lambda estado: [did for did, mr in mejor.items() if mr >= rank(estado)]  # noqa: E731
    contactados = en("enviado")
    respondidos = en("respondido")
    intencion = en("intencion_pago")
    costo_real = round(sum(c.costo for c in contactos), 2)
    n_int = len(intencion)

    return {
        "tiene_datos": bool(contactos),
        "deudores_total": len(deudores),
        "deuda_total": round(sum(d.monto_deuda for d in deudores), 2),
        "contactados": len(contactados),
        "respondidos": len(respondidos),
        "intencion": n_int,
        "tasa_respuesta": _tasa(len(respondidos), len(contactados)),
        "tasa_intencion": _tasa(n_int, len(contactados)),
        "monto_intencion": round(sum(monto.get(d, 0.0) for d in intencion), 2),
        "costo_real": costo_real,
        "costo_por_intencion": round(costo_real / n_int, 2) if n_int else 0.0,
        "promesas": len(promesas),
        "monto_prometido": round(sum(p.monto for p in promesas), 2),
    }


@router.get("/canales")
@ttl_cache("analytics:canales", 8)
def canales(session: Session = Depends(get_session)):
    """Efectividad real por canal: embudo, costo y costo por conversión."""
    contactos = session.exec(select(Contacto)).all()
    cat = canales_actuales()
    salida: dict[str, dict] = {}
    for canal in sorted({c.canal for c in contactos}):
        items = [c for c in contactos if c.canal == canal]
        cuenta = lambda e: sum(1 for c in items if rank(c.estado) >= rank(e))  # noqa: E731
        enviados = cuenta("enviado")
        intencion = cuenta("intencion_pago")
        costo = round(sum(c.costo for c in items), 2)
        salida[canal] = {
            "nombre": cat.get(canal, {}).get("nombre", canal),
            "enviados": enviados,
            "entregados": cuenta("entregado"),
            "vistos": cuenta("leido"),
            "respondidos": cuenta("respondido"),
            "intencion": intencion,
            "costo": costo,
            "costo_por_intencion": round(costo / intencion, 2) if intencion else 0.0,
            "tasa_lectura": _tasa(cuenta("leido"), enviados),
            "tasa_respuesta": _tasa(cuenta("respondido"), enviados),
            "tasa_intencion": _tasa(intencion, enviados),
        }
    return salida


@router.get("/cartera")
@ttl_cache("analytics:cartera", 20)
def cartera(session: Session = Depends(get_session)):
    """Portafolio real (Deudor): distribución por riesgo, mora, región y digital."""
    deudores = session.exec(select(Deudor)).all()
    u = umbrales_actuales()

    def agrupar(keyfn) -> dict:
        g: dict[str, dict] = {}
        for d in deudores:
            b = g.setdefault(str(keyfn(d)), {"deudores": 0, "monto": 0.0})
            b["deudores"] += 1
            b["monto"] = round(b["monto"] + d.monto_deuda, 2)
        return g

    def tramo(d: Deudor) -> str:
        x = d.dias_mora
        if x <= 0:
            return "Al día"
        if x <= u["dias_temprana"]:
            return f"1–{u['dias_temprana']}d"
        if x <= u["dias_media"]:
            return f"{u['dias_temprana'] + 1}–{u['dias_media']}d"
        if x <= u["dias_tardia"]:
            return f"{u['dias_media'] + 1}–{u['dias_tardia']}d"
        return f"{u['dias_tardia'] + 1}d+"

    return {
        "deudores_total": len(deudores),
        "deuda_total": round(sum(d.monto_deuda for d in deudores), 2),
        "monto_en_riesgo": round(sum((d.prob_default or 0) * d.monto_deuda for d in deudores), 2),
        "por_riesgo": agrupar(lambda d: d.riesgo or "—"),
        "por_tramo_mora": agrupar(tramo),
        "por_region": agrupar(lambda d: d.region or "—"),
        "digital": agrupar(lambda d: "Digital" if d.es_digital else "No digital"),
    }


_ORDEN_SEGMENTO = ["persuadible", "seguro", "perdido", "neutro"]
_LABEL_SEGMENTO = {
    "persuadible": "Persuadibles",
    "seguro": "Seguros (pagan solos)",
    "perdido": "Perdidos",
    "neutro": "Neutro / dudoso",
}


@router.get("/segmentos")
@ttl_cache("analytics:segmentos", 30)
def segmentos(session: Session = Depends(get_session)):
    """Mapa de segmentos causales de la cartera por uplift.

    Clasifica a cada cliente (persuadible / seguro / perdido / neutro) y resume,
    bajo la política de **gestión total** (se contacta a todos los no excluidos),
    el canal que el motor le asigna: el más rentable para los persuadibles y, para
    quienes ningún canal aporta valor incremental, la escalera de mora que los
    escala a **visita de campo** cuando no hay otra forma. Solo aplica con uplift.
    """
    deudores = [d.model_dump() for d in session.exec(select(Deudor)).all()]
    tiene_uplift = any(d.get("tiene_uplift") for d in deudores)
    if not tiene_uplift:
        return {"tiene_uplift": False}

    cat = canales_actuales()
    seg: dict[str, dict] = {
        k: {"label": _LABEL_SEGMENTO[k], "clientes": 0, "monto": 0.0, "uplift_medio": 0.0}
        for k in _ORDEN_SEGMENTO
    }
    total = persuadibles = escalados_campo = 0
    costo_opt = 0.0
    por_canal: dict[str, int] = {}

    for d in deudores:
        if d.get("opt_out"):
            continue
        s = uplift.segmentar(d)
        b = seg[s]
        b["clientes"] += 1
        b["monto"] = round(b["monto"] + float(d.get("monto_deuda") or 0), 2)
        b["uplift_medio"] += uplift.mejor_uplift(d)

        total += 1
        if s == "persuadible":
            persuadibles += 1
        rec = asignar_canal(d, None, cat)
        canal = rec["canal"]
        por_canal[canal] = por_canal.get(canal, 0) + 1
        costo_opt += float(rec.get("costo") or 0)
        if canal == "visita":
            escalados_campo += 1

    for b in seg.values():
        if b["clientes"]:
            b["uplift_medio"] = round(b["uplift_medio"] / b["clientes"], 3)

    return {
        "tiene_uplift": True,
        "segmentos": [seg[k] for k in _ORDEN_SEGMENTO],
        "total": total,
        "persuadibles": persuadibles,
        "persuadibles_pct": round(persuadibles / total * 100, 1) if total else 0.0,
        "escalados_campo": escalados_campo,
        "por_canal_recomendado": por_canal,
        "costo_optimizado": round(costo_opt, 2),
    }


@router.get("/priorizacion")
@ttl_cache("analytics:priorizacion", 15)
def priorizacion(session: Session = Depends(get_session)):
    """Listas accionables: a quién dar seguimiento y a quién falta contactar."""
    deudores = {d.id: d for d in session.exec(select(Deudor)).all()}
    contactos = session.exec(select(Contacto)).all()
    promesas = session.exec(select(Promesa)).all()
    mejor = _mejor_estado(contactos)

    # Promesa más reciente por deudor.
    prom: dict[int, Promesa] = {}
    for p in sorted(promesas, key=lambda p: p.id or 0):
        prom[p.deudor_id] = p

    con_intencion = []
    for did, mr in mejor.items():
        d = deudores.get(did)
        if not d or mr < rank("intencion_pago"):
            continue
        p = prom.get(did)
        con_intencion.append({
            "cliente_id": d.cliente_id, "nombre": d.nombre, "telefono": d.telefono,
            "monto_deuda": d.monto_deuda, "riesgo": d.riesgo,
            "promesa_monto": p.monto if p else None,
            "promesa_fecha_texto": p.fecha_texto if p else "",
            "promesa_fecha": p.fecha.isoformat() if (p and p.fecha) else None,
        })
    con_intencion.sort(key=lambda x: -x["monto_deuda"])

    sin_contactar = []
    for did, d in deudores.items():
        if d.opt_out or d.riesgo != "alto":
            continue
        if mejor.get(did, 0) >= rank("enviado"):
            continue
        sin_contactar.append({
            "cliente_id": d.cliente_id, "nombre": d.nombre, "telefono": d.telefono,
            "monto_deuda": d.monto_deuda, "dias_mora": d.dias_mora, "riesgo": d.riesgo,
        })
    sin_contactar.sort(key=lambda x: -x["monto_deuda"])

    # Listas de prioridad: solo los más relevantes por monto (evita payloads enormes
    # con carteras grandes; la UI los muestra paginados).
    return {
        "con_intencion": con_intencion[:100],
        "alto_riesgo_sin_contactar": sin_contactar[:100],
    }
