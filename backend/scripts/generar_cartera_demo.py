"""Genera la cartera de demostración de SCI: 100 clientes sintéticos con uplift.

Los datos son inventados (ningún registro proviene de una cartera real) pero están
calibrados para que el sistema se comporte como con una cartera de verdad:

- Mezcla de tramos de mora (al día, temprana, media, tardía, crítica).
- Riesgo, probabilidad de incumplimiento y ratio de pago correlacionados con la mora.
- Disponibilidad de canal ligada al perfil digital del cliente.
- Incrementalidad (uplift) por canal con los cuatro segmentos causales:
  persuadible, seguro, perdido y neutro → el motor de uplift decide a quién
  contactar y a quién suprimir.

Los teléfonos son secuenciales de prueba (+5198710xxxx): NO corresponden a personas
reales. Reemplázalos por números propios antes de hacer envíos reales.

Uso:
    backend\\.venv\\Scripts\\python.exe -m scripts.generar_cartera_demo
    backend\\.venv\\Scripts\\python.exe -m scripts.generar_cartera_demo --n 250
    backend\\.venv\\Scripts\\python.exe -m scripts.generar_cartera_demo --recargar
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

SALIDA = Path(__file__).resolve().parent.parent / "data" / "deudores.csv"
SEMILLA = 20260830

NOMBRES_F = ["María", "Rosa", "Carmen", "Lucía", "Ana", "Elena", "Julia", "Patricia",
             "Silvia", "Gladys", "Yolanda", "Norma", "Sonia", "Miriam", "Betty",
             "Doris", "Nancy", "Roxana", "Marisol", "Flor", "Isabel", "Teresa"]
NOMBRES_M = ["José", "Carlos", "Luis", "Jorge", "Miguel", "Pedro", "Juan", "Víctor",
             "Ricardo", "Wilmer", "Édgar", "Raúl", "Óscar", "Elmer", "Percy",
             "Marco", "Hugo", "Julio", "Ronald", "Freddy", "Alberto", "Nelson"]
APELLIDOS = ["Quispe", "Mamani", "Huamán", "Flores", "Ramírez", "Vargas", "Condori",
             "Chávez", "Rojas", "Salazar", "Paredes", "Ccahuana", "Ticona", "Apaza",
             "Cáceres", "Aliaga", "Mendoza", "Tapia", "Espinoza", "Cordova",
             "Loayza", "Ñahui", "Sulca", "Yupanqui", "Bautista", "Cusi", "Pariona",
             "Ayala", "Salas", "Trujillo", "Peralta", "Zegarra", "Ibáñez", "Coaquira"]

# region → (peso, zonas posibles con su peso)
REGIONES = [
    ("Lima", 32, [("urbana", 85), ("periurbana", 15)]),
    ("Arequipa", 12, [("urbana", 70), ("periurbana", 25), ("rural", 5)]),
    ("Cusco", 11, [("urbana", 45), ("periurbana", 30), ("rural", 25)]),
    ("La Libertad", 9, [("urbana", 60), ("periurbana", 30), ("rural", 10)]),
    ("Piura", 9, [("urbana", 50), ("periurbana", 30), ("rural", 20)]),
    ("Junín", 8, [("urbana", 50), ("periurbana", 30), ("rural", 20)]),
    ("Lambayeque", 7, [("urbana", 55), ("periurbana", 30), ("rural", 15)]),
    ("Puno", 7, [("urbana", 35), ("periurbana", 30), ("rural", 35)]),
    ("Cajamarca", 5, [("urbana", 35), ("periurbana", 30), ("rural", 35)]),
]

# tramo de mora → (peso, rango de días)
TRAMOS = [
    ("al_dia", 20, (0, 0)),
    ("temprana", 34, (1, 30)),
    ("media", 20, (31, 60)),
    ("tardia", 15, (61, 90)),
    ("critica", 11, (91, 180)),
]

# segmento causal → peso. Define cómo se comporta el cliente ante el contacto.
SEGMENTOS = [("persuadible", 44), ("seguro", 21), ("perdido", 15), ("neutro", 20)]


def elegir(opciones: list[tuple], rnd: random.Random):
    """Elige una opción por peso. Cada opción es (valor, peso, ...)."""
    total = sum(o[1] for o in opciones)
    r = rnd.uniform(0, total)
    acc = 0.0
    for op in opciones:
        acc += op[1]
        if r <= acc:
            return op
    return opciones[-1]


def generar(n: int, semilla: int) -> list[dict]:
    rnd = random.Random(semilla)
    filas = []

    for i in range(1, n + 1):
        # ---- identidad -------------------------------------------------
        genero = "F" if rnd.random() < 0.54 else "M"
        nombre_pila = rnd.choice(NOMBRES_F if genero == "F" else NOMBRES_M)
        nombre = f"{nombre_pila} {rnd.choice(APELLIDOS)} {rnd.choice(APELLIDOS)}"
        edad = int(rnd.triangular(21, 70, 38))

        region, _, zonas = elegir(REGIONES, rnd)
        zona = elegir(zonas, rnd)[0]

        # ---- perfil digital (define disponibilidad de canal) ------------
        p_digital = {"urbana": 0.78, "periurbana": 0.55, "rural": 0.30}[zona]
        if edad > 55:
            p_digital -= 0.20
        es_digital = rnd.random() < max(p_digital, 0.05)

        uso_app = round(rnd.uniform(0.35, 0.95) if es_digital else rnd.uniform(0.0, 0.3), 2)
        uso_whatsapp = round(min(1.0, uso_app + rnd.uniform(0.05, 0.3)), 2)
        interaccion = round((uso_app + uso_whatsapp) / 2, 2)

        canal_whatsapp = uso_whatsapp >= 0.35
        canal_sms = rnd.random() < 0.97
        canal_llamada = rnd.random() < 0.93
        canal_campo = zona != "rural" or rnd.random() < 0.7

        # ---- deuda y mora ----------------------------------------------
        tramo, _, (mora_min, mora_max) = elegir(TRAMOS, rnd)
        dias_mora = rnd.randint(mora_min, mora_max)

        tipo_cliente = elegir(
            [("microempresa", 58), ("pequeña", 30), ("mediana", 12)], rnd)[0]
        base_monto = {"microempresa": (300, 4500), "pequeña": (2500, 12000),
                      "mediana": (8000, 26000)}[tipo_cliente]
        monto_deuda = round(rnd.uniform(*base_monto), 2)
        cuota_mensual = round(max(80.0, monto_deuda / rnd.uniform(6, 18)), 2)

        # ---- riesgo (correlacionado con la mora) ------------------------
        riesgo_tramo = {"al_dia": 0.12, "temprana": 0.30, "media": 0.50,
                        "tardia": 0.68, "critica": 0.85}[tramo]
        score_riesgo = round(min(0.98, max(0.03, rnd.gauss(riesgo_tramo, 0.11))), 3)
        prob_default = round(min(0.95, max(0.02, score_riesgo * rnd.uniform(0.75, 1.05))), 3)
        riesgo = "alto" if score_riesgo >= 0.66 else "medio" if score_riesgo >= 0.33 else "bajo"

        num_atrasos = {"al_dia": (0, 1), "temprana": (0, 3), "media": (1, 5),
                       "tardia": (2, 7), "critica": (3, 10)}[tramo]
        num_atrasos_previos = rnd.randint(*num_atrasos)
        ratio_pago = round(min(0.99, max(0.10, rnd.gauss(1 - riesgo_tramo, 0.12))), 2)
        ultimo_pago_dias = max(1, int(dias_mora + rnd.triangular(0, 45, 12)))
        dias_mora_promedio = round(max(0.0, rnd.gauss(dias_mora, 6)), 1)

        # ---- incrementalidad (uplift) ----------------------------------
        segmento = elegir(SEGMENTOS, rnd)[0]
        if segmento == "persuadible":
            prob_pago_base = round(rnd.uniform(0.26, 0.58), 3)
            mejor = rnd.uniform(0.06, 0.34)
        elif segmento == "seguro":
            prob_pago_base = round(rnd.uniform(0.62, 0.90), 3)
            mejor = rnd.uniform(-0.06, 0.02)
        elif segmento == "perdido":
            prob_pago_base = round(rnd.uniform(0.05, 0.24), 3)
            mejor = rnd.uniform(-0.05, 0.015)
        else:  # neutro
            prob_pago_base = round(rnd.uniform(0.27, 0.57), 3)
            mejor = rnd.uniform(-0.03, 0.025)

        # El canal con mejor uplift depende del perfil: digital → WhatsApp,
        # no digital / mora alta → llamada o campo.
        if es_digital and canal_whatsapp:
            preferido = "whatsapp" if rnd.random() < 0.72 else "llamada"
        elif tramo in ("tardia", "critica"):
            preferido = "campo" if rnd.random() < 0.45 else "llamada"
        else:
            preferido = "llamada" if rnd.random() < 0.6 else "sms"

        ups = {}
        for canal in ("whatsapp", "sms", "llamada", "campo"):
            if canal == preferido:
                ups[canal] = mejor
            else:
                # Los demás canales quedan por debajo del preferido.
                ups[canal] = mejor - abs(rnd.gauss(0.05, 0.05))
        # SMS casi nunca supera a un canal conversacional.
        ups["sms"] = min(ups["sms"], mejor - 0.01)

        num_contactos_ult7d = elegir(
            [(0, 34), (1, 26), (2, 18), (3, 12), (4, 6), (5, 3), (6, 1)], rnd)[0]

        # ---- cumplimiento ----------------------------------------------
        opt_out = rnd.random() < 0.03
        consentimiento = False if (not opt_out and rnd.random() < 0.02) else True

        filas.append({
            "cliente_id": f"C{i:04d}",
            "nombre": nombre,
            "telefono": f"+5198710{i:04d}",
            "documento": f"{rnd.randint(40000000, 79999999)}",
            "monto_deuda": monto_deuda,
            "edad": edad,
            "genero": genero,
            "region": region,
            "zona": zona,
            "tipo_cliente": tipo_cliente,
            "es_digital": es_digital,
            "uso_app": uso_app,
            "uso_whatsapp": uso_whatsapp,
            "interaccion_digital_score": interaccion,
            "canal_whatsapp": canal_whatsapp,
            "canal_sms": canal_sms,
            "canal_llamada": canal_llamada,
            "canal_campo": canal_campo,
            "score_riesgo": score_riesgo,
            "prob_default": prob_default,
            "num_atrasos_previos": num_atrasos_previos,
            "dias_mora_promedio": dias_mora_promedio,
            "ratio_pago": ratio_pago,
            "ultimo_pago_dias": ultimo_pago_dias,
            "dias_mora": dias_mora,
            "riesgo": riesgo,
            "opt_out": opt_out,
            "consentimiento": consentimiento,
            "tiene_uplift": True,
            "cuota_mensual": cuota_mensual,
            "prob_pago_base": prob_pago_base,
            "uplift_whatsapp": round(ups["whatsapp"], 4),
            "uplift_sms": round(ups["sms"], 4),
            "uplift_llamada": round(ups["llamada"], 4),
            "uplift_campo": round(ups["campo"], 4),
            "num_contactos_ult7d": num_contactos_ult7d,
        })

    # Garantiza casos de cumplimiento visibles en la demo (opt-out y sin
    # consentimiento), que con solo 100 clientes el azar puede dejar en cero.
    candidatos = rnd.sample(range(n), 5)
    for idx in candidatos[:3]:
        filas[idx]["opt_out"] = True
        filas[idx]["consentimiento"] = True
    for idx in candidatos[3:]:
        filas[idx]["opt_out"] = False
        filas[idx]["consentimiento"] = False
    return filas


def recargar_base(filas: list[dict]) -> None:
    """Reemplaza la cartera y la actividad de la base con las filas generadas.

    Conserva usuarios y configuración (solo recrea cartera, contactos, mensajes
    y promesas).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sqlmodel import Session, SQLModel

    from app.models import Contacto, Deudor, Mensaje, Promesa, deudor_desde_fila, engine

    for tabla in (Contacto, Mensaje, Promesa, Deudor):  # hijos antes que el padre
        tabla.__table__.drop(engine, checkfirst=True)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([deudor_desde_fila(r) for r in filas])
        session.commit()
    print(f"  Base recargada con {len(filas)} clientes. Reinicia el backend.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera la cartera demo de SCI.")
    ap.add_argument("--n", type=int, default=100, help="número de clientes (default 100)")
    ap.add_argument("--semilla", type=int, default=SEMILLA, help="semilla reproducible")
    ap.add_argument("--salida", type=Path, default=SALIDA)
    ap.add_argument("--recargar", action="store_true",
                    help="además del CSV, reemplaza la cartera y la actividad en la base")
    args = ap.parse_args()

    filas = generar(args.n, args.semilla)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)

    print(f"Cartera demo generada: {args.salida}  ({len(filas)} clientes)")
    tramos = {"al día": 0, "1-30": 0, "31-60": 0, "61-90": 0, ">90": 0}
    for r in filas:
        d = r["dias_mora"]
        clave = ("al día" if d == 0 else "1-30" if d <= 30 else "31-60" if d <= 60
                 else "61-90" if d <= 90 else ">90")
        tramos[clave] += 1
    print("  Mora   :", " · ".join(f"{k}: {v}" for k, v in tramos.items()))
    print(f"  Deuda  : S/{sum(r['monto_deuda'] for r in filas):,.2f}")
    print(f"  Opt-out: {sum(1 for r in filas if r['opt_out'])} · "
          f"sin consentimiento: {sum(1 for r in filas if not r['consentimiento'])}")

    if args.recargar:
        recargar_base(filas)


if __name__ == "__main__":
    main()
