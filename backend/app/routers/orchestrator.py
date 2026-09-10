"""Endpoints del Orquestador de Canales con IA (plan de campaña + ahorro)."""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..core import orchestrator
from ..core.cache import ttl_cache
from ..core.security import get_current_user
from ..models import (
    Deudor,
    canales_actuales,
    get_session,
    umbrales_actuales,
)

router = APIRouter(
    prefix="/api/orchestrator", tags=["orquestador"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/plan")
@ttl_cache("orchestrator:plan", 30)
def plan(session: Session = Depends(get_session)):
    """Plan de la campaña: asignación por canal, costos y ahorro vs. baseline."""
    deudores = [d.model_dump() for d in session.exec(select(Deudor)).all()]
    return orchestrator.plan_campania(deudores, umbrales_actuales(), canales_actuales())
