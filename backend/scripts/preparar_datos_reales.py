"""ETL de datos reales → cartera con uplift lista para el motor (PDF 4.1).

OPCIONAL: el proyecto funciona con la cartera demo de 100 clientes sintéticos
(`scripts/generar_cartera_demo.py`). Este ETL solo se usa si dispones de una
cartera real; sus tablas fuente NO vienen en el repositorio y deben colocarse en
`datos previos/` (carpeta gitignoreada).

Cruza las 3 tablas de origen:
  01_Tabla_de_Clientes  (features demográficas / riesgo / disponibilidad)
  02_Tabla_de_Crditos   (saldo, cuota, mora real y prob_pago_7d_base)
  03_Tabla_contactos    (prob_pago_7d_post por canal → uplift, costo, fatiga)

Produce, por cliente:
  - monto_deuda (saldo), cuota_mensual, dias_mora real, prob_pago_base
  - uplift_{whatsapp,sms,llamada,campo} = post_por_canal − base
  - num_contactos_ult7d (fatiga reciente) y riesgo recalibrado desde prob_default

Escribe `backend/data/clientes_reales.csv` y (opcional) lo carga en la base.

Uso:
    python -m scripts.preparar_datos_reales            # genera CSV + carga DB
    python -m scripts.preparar_datos_reales --solo-csv # solo genera el CSV
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

RAIZ = Path(__file__).resolve().parent.parent.parent  # raíz del proyecto SCI
ORIGEN = RAIZ / "datos previos"
SALIDA = RAIZ / "backend" / "data" / "clientes_reales.csv"

CLIENTES = ORIGEN / "01_Tabla_de_Clientes.xlsx"
CREDITOS = ORIGEN / "02_Tabla_de_Crditos.xlsx"
CONTACTOS = ORIGEN / "03_Tabla_contactos_(1).xlsx"

# Canal del dataset → columna de uplift del modelo.
CANAL_A_UPLIFT = {
    "whatsapp": "uplift_whatsapp",
    "sms": "uplift_sms",
    "llamada": "uplift_llamada",
    "campo": "uplift_campo",
}

NOMBRES = ["María", "José", "Rosa", "Carlos", "Ana", "Luis", "Carmen", "Jorge",
           "Lucía", "Pedro", "Sofía", "Miguel", "Elena", "Juan", "Rocío", "Víctor"]
APELLIDOS = ["Quispe", "Mamani", "Huamán", "Flores", "Rojas", "Vargas", "Ccahuana",
             "Choque", "Apaza", "Condori", "Ramos", "Sánchez", "Torres", "Cruz"]


def _riesgo(prob_default: float) -> str:
    if prob_default >= 0.66:
        return "alto"
    if prob_default >= 0.33:
        return "medio"
    return "bajo"


def _nombre(cid: int) -> str:
    return f"{NOMBRES[cid % len(NOMBRES)]} {APELLIDOS[(cid // len(NOMBRES)) % len(APELLIDOS)]}"


def main(solo_csv: bool = False, limite: int = 0) -> None:
    print("1/5  Leyendo clientes…")
    cli = pd.read_excel(CLIENTES)

    print("2/5  Leyendo créditos (último corte por crédito)…")
    cr = pd.read_excel(CREDITOS)
    cr = cr.sort_values("fecha_corte").groupby("credito_id").tail(1)  # corte más reciente
    por_cli = cr.groupby("cliente_id").agg(
        monto_deuda=("saldo_restante", "sum"),
        cuota_mensual=("cuota_mensual", "sum"),
        dias_mora=("dias_mora", "max"),
        prob_pago_base=("prob_pago_7d_base", "mean"),
    ).reset_index()

    print("3/5  Leyendo contactos (uplift por canal + fatiga)… puede tardar ~3 min")
    ct = pd.read_excel(
        CONTACTOS,
        usecols=["cliente_id", "canal_contacto", "fecha_contacto",
                 "prob_pago_7d_post_contacto_modelada", "num_contactos_ult7d"],
    )
    # prob de pago post-contacto promedio por cliente × canal
    post = (ct.groupby(["cliente_id", "canal_contacto"])
              ["prob_pago_7d_post_contacto_modelada"].mean().unstack())
    post_global = ct.groupby("canal_contacto")["prob_pago_7d_post_contacto_modelada"].mean()
    # fatiga reciente: num_contactos_ult7d del contacto más reciente del cliente
    fatiga = (ct.sort_values("fecha_contacto")
                .groupby("cliente_id")["num_contactos_ult7d"].last())

    print("4/5  Cruzando y calculando uplift…")
    df = cli.merge(por_cli, on="cliente_id", how="left")
    df["prob_pago_base"] = df["prob_pago_base"].fillna(df["prob_default"].clip(0, 1))
    df["monto_deuda"] = df["monto_deuda"].fillna(0.0)
    df["cuota_mensual"] = df["cuota_mensual"].fillna(0.0)
    df["dias_mora"] = df["dias_mora"].fillna(0).astype(int)
    df["num_contactos_ult7d"] = df["cliente_id"].map(fatiga).fillna(0).astype(int)

    for canal, col in CANAL_A_UPLIFT.items():
        # post por cliente×canal; si el cliente no tuvo ese canal → media global del canal
        serie = post[canal] if canal in post.columns else pd.Series(index=df.index, dtype=float)
        post_cli = df["cliente_id"].map(serie).fillna(post_global.get(canal, 0.0))
        df[col] = (post_cli - df["prob_pago_base"]).round(4)

    df["riesgo"] = df["prob_default"].apply(_riesgo)
    df["nombre"] = df["cliente_id"].apply(_nombre)
    df["documento"] = (40000000 + df["cliente_id"]).astype(str)
    df["telefono"] = ""          # el envío real usa pocos números de prueba (se editan a mano)
    df["opt_out"] = False
    df["consentimiento"] = True
    df["tiene_uplift"] = True

    columnas = [
        "cliente_id", "nombre", "telefono", "documento", "monto_deuda",
        "edad", "genero", "region", "zona", "tipo_cliente", "es_digital",
        "uso_app", "uso_whatsapp", "interaccion_digital_score",
        "canal_whatsapp", "canal_sms", "canal_llamada", "canal_campo",
        "score_riesgo", "prob_default", "num_atrasos_previos",
        "dias_mora_promedio", "ratio_pago", "ultimo_pago_dias",
        "dias_mora", "riesgo", "opt_out", "consentimiento",
        "tiene_uplift", "cuota_mensual", "prob_pago_base",
        "uplift_whatsapp", "uplift_sms", "uplift_llamada", "uplift_campo",
        "num_contactos_ult7d",
    ]
    df = df[columnas]
    if limite and limite < len(df):
        # Muestra aleatoria (semilla fija) que conserva la distribución de la cartera.
        df = df.sample(n=limite, random_state=42).reset_index(drop=True)
        print(f"     (limitado a {limite:,} clientes)")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SALIDA, index=False)
    print(f"     -> {SALIDA}  ({len(df):,} clientes)")

    # Resumen de segmentos (validación rápida)
    mejor = df[["uplift_whatsapp", "uplift_sms", "uplift_llamada", "uplift_campo"]].max(axis=1)
    persu = (mejor >= 0.03).mean() * 100
    print(f"     Persuadibles (uplift>=0.03): {persu:.1f}%  |  "
          f"uplift WhatsApp medio: {df['uplift_whatsapp'].mean():+.3f}")

    if solo_csv:
        return

    print("5/5  Cargando en la base (reemplaza la cartera y la actividad)…")
    sys.path.insert(0, str(RAIZ / "backend"))
    from sqlmodel import Session, SQLModel
    from app.models import Contacto, Deudor, Mensaje, Promesa, deudor_desde_fila, engine

    for tabla in (Contacto, Mensaje, Promesa, Deudor):  # hijos antes que el padre
        tabla.__table__.drop(engine, checkfirst=True)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([deudor_desde_fila(r) for r in df.to_dict("records")])
        session.commit()
    print(f"     -> {len(df):,} clientes cargados. Reinicia el backend.")


if __name__ == "__main__":
    lim = 0
    if "--limite" in sys.argv:
        i = sys.argv.index("--limite")
        if i + 1 < len(sys.argv):
            lim = int(sys.argv[i + 1])
    main(solo_csv="--solo-csv" in sys.argv, limite=lim)
