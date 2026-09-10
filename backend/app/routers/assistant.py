"""Asistente interno (IA) del panel de SCI.

Un analista de cobranza conversacional para el equipo de cobranzas: interpreta los
KPIs reales (embudo, costos, efectividad por canal, ahorro proyectado), explica
las estrategias del orquestador y guía la navegación del sistema. Reúne un
snapshot de datos vivos y lo inyecta como contexto del LLM en cada pregunta.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from ..core.security import get_current_user
from ..models import get_session
from ..services import llm
from . import analytics, orchestrator

router = APIRouter(
    prefix="/api/assistant", tags=["asistente"],
    dependencies=[Depends(get_current_user)],
)


class Turno(BaseModel):
    role: str       # "user" | "assistant"
    content: str


class ChatIn(BaseModel):
    mensaje: str
    historial: list[Turno] = []


_GUIA = """
# QUIÉN ERES
Eres "SCI IA", el asistente analista del panel de SCI (Sistema de Cobranzas
Inteligente). Hablas con el EQUIPO interno (no con el cliente deudor). Tu trabajo:
1) Evaluar estrategias: qué canal conviene por cliente y por qué, y cómo van los
   resultados de cobranza (embudo, costo por intención de pago, ahorro, promesas).
2) Leer la evolución en el tiempo: comparar cómo mejoran (o no) las tasas y el
   costo a medida que se ejecutan campañas.
3) Guiar la navegación del sistema (dónde hacer cada cosa).

# CÓMO RESPONDES
- Español de Perú, claro y directo. Respuestas breves (2–5 frases o una lista corta).
- Apóyate SIEMPRE en los números del bloque "DATOS EN VIVO". Si citas una cifra,
  que sea de ahí. No inventes datos que no estén en el contexto.
- Si te preguntan algo que los datos no permiten responder, dilo y sugiere dónde
  obtenerlo en el panel.
- Sé concreto y accionable: recomienda el siguiente paso.

# CÓMO FUNCIONA LA ESTRATEGIA (orquestador)
El orquestador asigna a cada cliente un canal "next-best-action" según días de
mora, monto y riesgo, respetando la disponibilidad de canal del cliente y el
opt-out. Tramos: al día → SMS preventivo; mora temprana → WhatsApp (Voz AI si es
alto riesgo + monto); mora media → Voz AI o llamada humana según monto; mora
tardía → llamada humana; mora crítica de monto alto → visita de campo.
Canales (de menor a mayor costo): WhatsApp, SMS, Voz AI, Llamada humana, Visita.

# MAPA DEL SISTEMA (para guiar al usuario)
- "Dashboards" (/): resultados reales de la campaña, cartera, efectividad por
  canal, GAP contactabilidad↔promesas y proyección de ahorro.
- "Base de datos" (/base-datos): lista de clientes con su canal asignado. Ahí el
  admin puede: buscar, "Nuevo cliente" (alta manual), "Importar XLSX", editar,
  y "Ejecutar estrategias" (con o sin "Simular") que registra los envíos por cola.
- "Configuración" (/configuracion, solo admin): umbrales de mora, montos de corte
  y economía por canal (costo/tasa de pago), más los prompts de los bots.
""".strip()


def _fmt(n) -> str:
    try:
        return f"{float(n):,.0f}"
    except (TypeError, ValueError):
        return str(n)


def _snapshot(session: Session) -> str:
    """Texto compacto con los KPIs reales para inyectar como contexto."""
    r = analytics.resumen(session)
    canales = analytics.canales(session)
    plan = orchestrator.plan(session)
    seg = analytics.segmentos(session)

    lineas = [
        "## Cartera",
        f"- Clientes: {r['deudores_total']} · Deuda total: S/{_fmt(r['deuda_total'])}",
    ]

    if seg.get("tiene_uplift"):
        lineas += [
            "## Incrementalidad (uplift) — segmentación y canal",
            f"- Gestión total (se contacta a todos los no excluidos): {seg['total']} · "
            f"Persuadibles: {seg['persuadibles']} ({seg['persuadibles_pct']}% — el contacto "
            f"sí mueve el pago) · Escalados a visita de campo: {seg['escalados_campo']}",
            "- Segmentos: "
            + ", ".join(f"{s['label']} {s['clientes']}" for s in seg["segmentos"]),
            "- Canal recomendado: "
            + ", ".join(f"{k} {v}" for k, v in seg.get("por_canal_recomendado", {}).items()),
        ]

    if r["tiene_datos"]:
        lineas += [
            "## Embudo real de la campaña",
            f"- Contactados: {r['contactados']} · Respondieron: {r['respondidos']} "
            f"(tasa {r['tasa_respuesta']}%)",
            f"- Con intención de pago: {r['intencion']} (tasa {r['tasa_intencion']}%) · "
            f"Promesas: {r['promesas']} por S/{_fmt(r['monto_prometido'])}",
            f"- Costo real: S/{_fmt(r['costo_real'])} · Costo por intención: "
            f"S/{r['costo_por_intencion']}",
            "## Efectividad por canal (real)",
        ]
        for canal, c in canales.items():
            lineas.append(
                f"- {c['nombre']}: {c['enviados']} envíos, {c['intencion']} con intención "
                f"(tasa {c['tasa_intencion']}%), costo S/{_fmt(c['costo'])}, "
                f"costo/intención S/{c['costo_por_intencion']}"
            )
    else:
        lineas.append("## Embudo real: aún no hay contactos registrados "
                      "(ejecuta estrategias o envía por un canal para generar datos).")

    lineas += [
        "## Proyección del plan (orquestador)",
        f"- Gestionables: {plan['deudores_gestionados']} · Excluidos por opt-out: "
        f"{plan['excluidos_opt_out']}",
        f"- Costo optimizado: S/{_fmt(plan['costo_optimizado'])} vs. baseline "
        f"S/{_fmt(plan['costo_baseline'])} → ahorro S/{_fmt(plan['ahorro_soles'])} "
        f"({plan['ahorro_pct']}%)",
        f"- Recupero esperado: S/{_fmt(plan['recupero_esperado'])}",
        "- Clientes por canal asignado: "
        + ", ".join(f"{v['nombre']} {v['deudores']}" for v in plan["por_canal"].values()),
    ]
    return "\n".join(lineas)


@router.post("/chat")
def chat(body: ChatIn, session: Session = Depends(get_session)):
    """Pregunta al asistente analista; responde con los datos vivos del panel."""
    system_prompt = f"{_GUIA}\n\n# DATOS EN VIVO (snapshot actual)\n{_snapshot(session)}"
    historial = [t.model_dump() for t in body.historial]
    try:
        respuesta = llm.responder_asistente(body.mensaje, system_prompt, historial)
    except RuntimeError as e:
        # Falta la API key del LLM: mensaje claro en vez de 500.
        respuesta = (
            f"No puedo responder porque falta configurar el LLM: {e} "
            "Configúralo en el .env del backend (LLM_API_KEY)."
        )
    return {"respuesta": respuesta}
