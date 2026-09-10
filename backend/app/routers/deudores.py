"""Gestión de la base de datos de deudores: edición manual e importación XLSX (admin)."""
import io

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core.cache import clear as clear_cache
from ..core.security import require_admin
from ..models import Deudor, get_session, importar_dataframe

router = APIRouter(prefix="/api/deudores", tags=["deudores"], dependencies=[Depends(require_admin)])

# Score representativo para cada nivel de riesgo elegido en el alta manual,
# para que el orquestador asigne un canal coherente sin pedir el score crudo.
SCORE_POR_RIESGO = {"bajo": 0.2, "medio": 0.5, "alto": 0.8}


class DeudorUpdate(BaseModel):
    nombre: str | None = None
    telefono: str | None = None
    documento: str | None = None
    monto_deuda: float | None = None
    opt_out: bool | None = None
    consentimiento: bool | None = None


class DeudorCreate(BaseModel):
    nombre: str
    telefono: str = ""
    documento: str = ""
    monto_deuda: float = 0.0
    dias_mora: int = 0
    riesgo: str = "medio"      # bajo · medio · alto
    region: str = ""
    cliente_id: str = ""       # opcional; se autogenera si viene vacío


def _nuevo_cliente_id(session: Session) -> str:
    """Genera un cliente_id único tipo MAN-0001 para altas manuales."""
    n = 1
    while session.exec(select(Deudor).where(Deudor.cliente_id == f"MAN-{n:04d}")).first():
        n += 1
    return f"MAN-{n:04d}"


@router.post("", status_code=201)
def crear(body: DeudorCreate, session: Session = Depends(get_session)):
    """Alta manual de un cliente en la cartera (admin)."""
    cliente_id = body.cliente_id.strip()
    if cliente_id:
        if session.exec(select(Deudor).where(Deudor.cliente_id == cliente_id)).first():
            raise HTTPException(status_code=409, detail=f"Ya existe un cliente con ID {cliente_id}.")
    else:
        cliente_id = _nuevo_cliente_id(session)

    riesgo = body.riesgo if body.riesgo in SCORE_POR_RIESGO else "medio"
    d = Deudor(
        cliente_id=cliente_id,
        nombre=body.nombre.strip(),
        telefono=body.telefono.strip(),
        documento=body.documento.strip(),
        monto_deuda=body.monto_deuda,
        region=body.region.strip(),
        dias_mora=body.dias_mora,
        dias_mora_promedio=float(body.dias_mora),
        riesgo=riesgo,
        score_riesgo=SCORE_POR_RIESGO[riesgo],
    )
    session.add(d)
    session.commit()
    session.refresh(d)
    clear_cache()
    return d


@router.put("/{deudor_id}")
def actualizar(deudor_id: int, body: DeudorUpdate, session: Session = Depends(get_session)):
    """Completa/edita a mano los datos del cliente (nombre, teléfono, monto…)."""
    d = session.get(Deudor, deudor_id)
    if not d:
        raise HTTPException(status_code=404, detail="Deudor no encontrado")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    session.add(d)
    session.commit()
    session.refresh(d)
    clear_cache()
    return d


@router.post("/importar")
async def importar(
    archivo: UploadFile = File(...),
    reemplazar: bool = False,
):
    """Importa deudores desde un archivo .xlsx o .csv (upsert por cliente_id)."""
    contenido = await archivo.read()
    nombre = (archivo.filename or "").lower()
    try:
        if nombre.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contenido))
        else:
            df = pd.read_excel(io.BytesIO(contenido))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"No se pudo leer el archivo: {e}")

    resultado = importar_dataframe(df, reemplazar=reemplazar)
    clear_cache()
    return resultado
