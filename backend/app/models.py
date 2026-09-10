"""Modelos de datos (SQLModel + SQLite), carga del dataset e importación XLSX."""
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlmodel import Field, Session, SQLModel, create_engine, select

from .core.config import settings
from .core.nba import CANALES
from .core.orchestrator import UMBRALES_DEFAULT
from .services.prompts import SYSTEM_PROMPT_VOZ, SYSTEM_PROMPT_WHATSAPP

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_CSV = _DATA_DIR / "deudores.csv"            # demo (100 clientes sintéticos con uplift)
DATA_REALES = _DATA_DIR / "clientes_reales.csv"  # cartera real con uplift (opcional, vía ETL)


# --------- helpers de parseo (tolerantes a columnas faltantes / NaN) ---------
def _val(row: dict, key, default=None):
    v = row.get(key, default)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    return v


def _to_float(v, default=0.0):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


def _to_int(v, default=0):
    return int(round(_to_float(v, default)))


def _to_bool(v, default=True):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "si", "sí", "yes", "y", "t", "x")
    return bool(v)


def riesgo_desde_score(score: float) -> str:
    s = score / 100 if score > 1 else score
    if s >= 0.66:
        return "alto"
    if s >= 0.33:
        return "medio"
    return "bajo"


# ------------------------------- modelos -------------------------------
class Deudor(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cliente_id: str = Field(default="", index=True)

    # Datos para envíos (se completan a mano si faltan en el origen)
    nombre: str = ""
    telefono: str = ""
    documento: str = ""
    monto_deuda: float = 0.0

    # Features del dataset (xlsx)
    edad: int = 0
    genero: str = ""
    region: str = ""
    zona: str = ""
    tipo_cliente: str = ""
    es_digital: bool = False
    uso_app: float = 0.0
    uso_whatsapp: float = 0.0
    interaccion_digital_score: float = 0.0
    canal_whatsapp: bool = True
    canal_sms: bool = True
    canal_llamada: bool = True
    canal_campo: bool = True
    score_riesgo: float = 0.0
    prob_default: float = 0.0
    num_atrasos_previos: int = 0
    dias_mora_promedio: float = 0.0
    ratio_pago: float = 0.0
    ultimo_pago_dias: int = 0

    # Derivados / operativos
    dias_mora: int = 0
    riesgo: str = "medio"
    opt_out: bool = False
    consentimiento: bool = True

    # --- Incrementalidad (uplift) ---
    # Probabilidad base de pago a 7 días (sin contacto) y uplift por canal del
    # dataset real (P(pago|contacto canal) - P(pago|sin contacto)). El motor usa
    # esto para decidir A QUIÉN contactar y por qué canal; si no hay datos
    # (tiene_uplift=False), el orquestador cae al árbol de reglas por mora.
    tiene_uplift: bool = False
    cuota_mensual: float = 0.0          # monto recuperable en la ventana de 7 días
    prob_pago_base: float = 0.0
    uplift_whatsapp: float = 0.0
    uplift_sms: float = 0.0
    uplift_llamada: float = 0.0         # cubre Voz AI y llamada humana
    uplift_campo: float = 0.0
    num_contactos_ult7d: int = 0        # fatiga: contactos recientes


class Contacto(SQLModel, table=True):
    """Bitácora auditable de cada contacto (alimenta el GAP en tiempo real)."""
    id: int | None = Field(default=None, primary_key=True)
    deudor_id: int = Field(foreign_key="deudor.id", index=True)
    canal: str
    # enviado · entregado · leido · respondido · pagado · fallido
    estado: str = "enviado"
    costo: float = 0.0
    monto_pagado: float = 0.0
    detalle: str = ""          # id del mensaje / nota
    creado_en: datetime = Field(default_factory=datetime.now)


class Mensaje(SQLModel, table=True):
    """Bitácora de la conversación del bot (alimenta análisis de objeciones/motivos)."""
    id: int | None = Field(default=None, primary_key=True)
    deudor_id: int | None = Field(default=None, foreign_key="deudor.id", index=True)
    canal: str = "whatsapp"
    rol: str = "cliente"       # cliente · bot
    texto: str = ""
    creado_en: datetime = Field(default_factory=datetime.now)


class Promesa(SQLModel, table=True):
    """Compromiso de pago detectado en la conversación (fecha + monto prometido)."""
    id: int | None = Field(default=None, primary_key=True)
    deudor_id: int = Field(foreign_key="deudor.id", index=True)
    monto: float = 0.0
    fecha_texto: str = ""       # lo que dijo el cliente ("mañana", "el viernes")
    fecha: date | None = None   # fecha ISO si se pudo interpretar
    creado_en: datetime = Field(default_factory=datetime.now)


class Usuario(SQLModel, table=True):
    """Usuario del panel web (autenticación + rol)."""
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    nombre: str = ""
    hashed_password: str
    rol: str = "usuario"       # admin · usuario


class AppConfig(SQLModel, table=True):
    """Configuración editable (fila única, id=1)."""
    id: int | None = Field(default=1, primary_key=True)
    prompt_whatsapp: str = ""
    prompt_voz: str = ""
    dias_temprana: int = UMBRALES_DEFAULT["dias_temprana"]
    dias_media: int = UMBRALES_DEFAULT["dias_media"]
    dias_tardia: int = UMBRALES_DEFAULT["dias_tardia"]
    monto_riesgo_temprano: float = UMBRALES_DEFAULT["monto_riesgo_temprano"]
    monto_voz_humano: float = UMBRALES_DEFAULT["monto_voz_humano"]
    monto_visita: float = UMBRALES_DEFAULT["monto_visita"]
    canales_json: str = ""     # overrides de economía por canal (costo, tasa_pago)


engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


# ------------------------- importación de datos -------------------------
def deudor_desde_fila(row: dict) -> Deudor:
    """Mapea una fila (CSV/XLSX) a un Deudor; ignora columnas ausentes."""
    score = _to_float(_val(row, "score_riesgo"))
    dias_prom = _to_float(_val(row, "dias_mora_promedio"))
    riesgo = str(_val(row, "riesgo", "") or "") or riesgo_desde_score(score)
    return Deudor(
        cliente_id=str(_val(row, "cliente_id", "") or ""),
        nombre=str(_val(row, "nombre", "") or ""),
        telefono=str(_val(row, "telefono", "") or ""),
        documento=str(_val(row, "documento", "") or ""),
        monto_deuda=_to_float(_val(row, "monto_deuda")),
        edad=_to_int(_val(row, "edad")),
        genero=str(_val(row, "genero", "") or ""),
        region=str(_val(row, "region", "") or ""),
        zona=str(_val(row, "zona", "") or ""),
        tipo_cliente=str(_val(row, "tipo_cliente", "") or ""),
        es_digital=_to_bool(_val(row, "es_digital"), False),
        uso_app=_to_float(_val(row, "uso_app")),
        uso_whatsapp=_to_float(_val(row, "uso_whatsapp")),
        interaccion_digital_score=_to_float(_val(row, "interaccion_digital_score")),
        canal_whatsapp=_to_bool(_val(row, "canal_whatsapp"), True),
        canal_sms=_to_bool(_val(row, "canal_sms"), True),
        canal_llamada=_to_bool(_val(row, "canal_llamada"), True),
        canal_campo=_to_bool(_val(row, "canal_campo"), True),
        score_riesgo=score,
        prob_default=_to_float(_val(row, "prob_default")),
        num_atrasos_previos=_to_int(_val(row, "num_atrasos_previos")),
        dias_mora_promedio=dias_prom,
        ratio_pago=_to_float(_val(row, "ratio_pago")),
        ultimo_pago_dias=_to_int(_val(row, "ultimo_pago_dias")),
        dias_mora=_to_int(_val(row, "dias_mora"), int(round(dias_prom))),
        riesgo=riesgo,
        opt_out=_to_bool(_val(row, "opt_out"), False),
        consentimiento=_to_bool(_val(row, "consentimiento"), True),
        tiene_uplift=_to_bool(_val(row, "tiene_uplift"), False),
        cuota_mensual=_to_float(_val(row, "cuota_mensual")),
        prob_pago_base=_to_float(_val(row, "prob_pago_base")),
        uplift_whatsapp=_to_float(_val(row, "uplift_whatsapp")),
        uplift_sms=_to_float(_val(row, "uplift_sms")),
        uplift_llamada=_to_float(_val(row, "uplift_llamada")),
        uplift_campo=_to_float(_val(row, "uplift_campo")),
        num_contactos_ult7d=_to_int(_val(row, "num_contactos_ult7d")),
    )


def importar_dataframe(df: pd.DataFrame, reemplazar: bool = False) -> dict:
    """Inserta/actualiza deudores desde un DataFrame (upsert por cliente_id)."""
    df.columns = [str(c).strip() for c in df.columns]
    creados = actualizados = 0
    with Session(engine) as session:
        if reemplazar:
            for d in session.exec(select(Deudor)).all():
                session.delete(d)
            session.commit()
        for _, raw in df.iterrows():
            nuevo = deudor_desde_fila(raw.to_dict())
            existente = None
            if nuevo.cliente_id:
                existente = session.exec(
                    select(Deudor).where(Deudor.cliente_id == nuevo.cliente_id)
                ).first()
            if existente:
                data = nuevo.model_dump(exclude={"id"})
                # No pisar datos completados a mano si el origen los trae vacíos.
                for campo in ("nombre", "telefono", "documento"):
                    if not data.get(campo):
                        data.pop(campo, None)
                if not data.get("monto_deuda"):
                    data.pop("monto_deuda", None)
                for k, v in data.items():
                    setattr(existente, k, v)
                session.add(existente)
                actualizados += 1
            else:
                session.add(nuevo)
                creados += 1
        session.commit()
    return {"creados": creados, "actualizados": actualizados,
            "total": creados + actualizados}


def seed_desde_csv() -> int:
    """Carga inicial si la tabla está vacía.

    Usa `clientes_reales.csv` si existe (cartera real cargada vía ETL) y, si no,
    la cartera demo de 100 clientes sintéticos con uplift. Inserta en bloque (sin
    upsert) por velocidad con volúmenes grandes.
    """
    with Session(engine) as session:
        if session.exec(select(Deudor)).first():
            return 0
    fuente = DATA_REALES if DATA_REALES.exists() else DATA_CSV
    if not fuente.exists():
        return 0
    df = pd.read_csv(fuente)
    df.columns = [str(c).strip() for c in df.columns]
    with Session(engine) as session:
        objs = [deudor_desde_fila(r) for r in df.to_dict("records")]
        session.add_all(objs)
        session.commit()
    return len(objs)


# ------------------------- configuración -------------------------
def get_or_create_config() -> "AppConfig":
    with Session(engine) as session:
        cfg = session.get(AppConfig, 1)
        if not cfg:
            cfg = AppConfig(
                id=1,
                prompt_whatsapp=SYSTEM_PROMPT_WHATSAPP,
                prompt_voz=SYSTEM_PROMPT_VOZ,
            )
            session.add(cfg)
            session.commit()
            session.refresh(cfg)
        return cfg


def umbrales_actuales() -> dict:
    cfg = get_or_create_config()
    return {
        "dias_temprana": cfg.dias_temprana,
        "dias_media": cfg.dias_media,
        "dias_tardia": cfg.dias_tardia,
        "monto_riesgo_temprano": cfg.monto_riesgo_temprano,
        "monto_voz_humano": cfg.monto_voz_humano,
        "monto_visita": cfg.monto_visita,
    }


def canales_actuales() -> dict:
    """Economía de canales: defaults de nba.CANALES + overrides de la config."""
    cfg = get_or_create_config()
    canales = {k: dict(v) for k, v in CANALES.items()}
    if cfg.canales_json:
        try:
            override = json.loads(cfg.canales_json)
            for k, vals in override.items():
                if k in canales and isinstance(vals, dict):
                    for campo in ("costo", "tasa_pago"):
                        if campo in vals:
                            canales[k][campo] = float(vals[campo])
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return canales


def _solo_digitos(valor) -> str:
    return "".join(ch for ch in str(valor) if ch.isdigit())


def buscar_deudor_por_telefono(session: Session, numero: str) -> "Deudor | None":
    """Busca un deudor por los últimos 9 dígitos del teléfono.

    Tolerante a '+', espacios y formato: compara solo dígitos en ambos lados,
    porque WhatsApp/neonize entregan el número sin formato (p. ej. '51962374905')
    y en la base puede estar como '+51 962 374 905'.
    """
    clave = _solo_digitos(numero)[-9:]
    if not clave:
        return None
    for d in session.exec(select(Deudor)).all():
        if d.telefono and _solo_digitos(d.telefono)[-9:] == clave:
            return d
    return None


def get_session():
    with Session(engine) as session:
        yield session
