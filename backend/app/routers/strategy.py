"""Catálogo de canales, asignación por deudor y cartera (requiere sesión)."""
from fastapi import APIRouter, Depends
from sqlmodel import Session, func, or_, select

from ..core import nba, orchestrator
from ..core.security import get_current_user
from ..models import (
    Deudor,
    canales_actuales,
    get_session,
    umbrales_actuales,
)

router = APIRouter(prefix="/api/strategy", tags=["estrategia"], dependencies=[Depends(get_current_user)])


@router.get("/canales")
def canales():
    """Economía vigente de los canales (defaults + overrides de configuración)."""
    return canales_actuales()


@router.get("/deudores")
def listar_deudores(
    q: str = "",
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    """Página de deudores (filtrada en SQL) con el canal asignado por el orquestador.

    Con decenas de miles de clientes no se puede devolver todo: se busca y pagina en la base, y
    solo se calcula la recomendación de la página pedida. Devuelve `{items, total}`.
    """
    cond = []
    if q:
        like = f"%{q}%"
        cond.append(or_(
            Deudor.nombre.ilike(like),
            Deudor.cliente_id.ilike(like),
            Deudor.documento.ilike(like),
            Deudor.telefono.ilike(like),
        ))

    total = session.exec(select(func.count(Deudor.id)).where(*cond)).one()
    rows = session.exec(
        select(Deudor).where(*cond).order_by(Deudor.id).offset(offset).limit(limit)
    ).all()

    cat = canales_actuales()
    umbrales = umbrales_actuales()
    items = []
    for d in rows:
        data = d.model_dump()
        items.append({**data, "recomendacion": orchestrator.asignar_canal(data, umbrales, cat)})
    return {"items": items, "total": total}


@router.get("/cartera")
def cartera(session: Session = Depends(get_session)):
    """Distribución de la cartera por tramo de mora × canal asignado."""
    deudores = [d.model_dump() for d in session.exec(select(Deudor)).all()]
    return orchestrator.cartera_mora_canal(deudores, umbrales_actuales(), canales_actuales())


@router.get("/valor-esperado")
def valor_esperado(monto: float):
    """Tabla de valor esperado por canal para un monto dado."""
    return nba.tabla_valor_esperado(monto, canales_actuales())
