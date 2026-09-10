"""Configuración editable: prompts IA, umbrales del orquestador y economía de canales. Solo admin."""
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from ..core.security import require_admin
from ..models import AppConfig, canales_actuales, get_or_create_config, get_session

router = APIRouter(prefix="/api/config", tags=["configuración"])


class CanalEconomia(BaseModel):
    costo: float
    tasa_pago: float


class ConfigIn(BaseModel):
    prompt_whatsapp: str | None = None
    prompt_voz: str | None = None
    dias_temprana: int | None = None
    dias_media: int | None = None
    dias_tardia: int | None = None
    monto_riesgo_temprano: float | None = None
    monto_voz_humano: float | None = None
    monto_visita: float | None = None
    canales: dict[str, CanalEconomia] | None = None


def _serializar(cfg: AppConfig) -> dict:
    data = cfg.model_dump()
    data.pop("canales_json", None)
    data["canales"] = canales_actuales()  # economía vigente (defaults + overrides)
    return data


@router.get("", dependencies=[Depends(require_admin)])
def leer_config():
    return _serializar(get_or_create_config())


@router.put("", dependencies=[Depends(require_admin)])
def actualizar_config(body: ConfigIn, session: Session = Depends(get_session)):
    get_or_create_config()  # asegura que exista la fila
    cfg = session.get(AppConfig, 1)
    datos = body.model_dump(exclude_none=True)
    canales = datos.pop("canales", None)
    for campo, valor in datos.items():
        setattr(cfg, campo, valor)
    if canales is not None:
        cfg.canales_json = json.dumps(canales)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return _serializar(cfg)
