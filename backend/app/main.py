"""Punto de entrada de la API de SCI (FastAPI)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.compliance import esta_permitido
from .core.config import settings
from .core.scheduler import scheduler
from .core.security import seed_usuarios
from .models import get_or_create_config, init_db, seed_desde_csv
from .routers import (
    analytics,
    assistant,
    auth,
    campaign,
    config,
    deudores,
    orchestrator,
    sms,
    strategy,
    voice,
    whatsapp,
)


def _warm_cache() -> None:
    """Precalcula la analítica pesada en segundo plano tras el arranque,
    para que el primer poll del dashboard ya encuentre la caché caliente."""
    try:
        from sqlmodel import Session

        from .models import engine
        from .routers import analytics, campaign, orchestrator

        with Session(engine) as s:
            analytics.resumen(s)
            analytics.canales(s)
            analytics.cartera(s)
            analytics.priorizacion(s)
            analytics.segmentos(s)
            orchestrator.plan(s)
            campaign.metricas(s)
    except Exception:  # noqa: BLE001  (mejor esfuerzo; no debe tumbar el arranque)
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_desde_csv()
    seed_usuarios()
    get_or_create_config()
    if not scheduler.running:
        scheduler.start()
    # Calienta la caché sin bloquear el arranque (hilo daemon).
    import threading
    threading.Thread(target=_warm_cache, daemon=True).start()
    # WhatsApp no oficial (neonize): conecta por QR en un hilo de fondo.
    if settings.wa_provider == "neonize":
        from .services import whatsapp_neonize
        whatsapp_neonize.iniciar()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# CORS para el frontend de Vite (dev).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(config.router)
app.include_router(deudores.router)
app.include_router(campaign.router)
app.include_router(strategy.router)
app.include_router(orchestrator.router)
app.include_router(analytics.router)
app.include_router(assistant.router)
app.include_router(whatsapp.router)
app.include_router(sms.router)
app.include_router(voice.router)


@app.get("/")
def health():
    permitido, motivo = esta_permitido()
    return {
        "app": settings.app_name,
        "status": "ok",
        "ventana_contacto": {"permitido": permitido, "motivo": motivo},
    }
