"""Cumplimiento normativo de cobranza en Perú.

Indecopi · Código de Protección y Defensa del Consumidor (Ley 29571), Art. 62(b):
prohíbe "visitas o llamadas telefónicas entre las 20.00 horas y las 07.00 horas
o los días sábados, domingos y feriados". Aplicamos el mismo criterio a
WhatsApp / SMS / Voz AI por prudencia.

NOTA: esto es una guía técnica, no asesoría legal. Validar con el área legal de la entidad.
"""
from datetime import datetime, time, timedelta

import holidays

from .config import settings

# Días bloqueados (0=lunes … 6=domingo).
# Brief IAthon: ventana hábil L–S, solo se bloquea DOMINGO (+ feriados).
# ⚠️ El texto literal de la Ley 29571 Art. 62b también menciona "sábados".
#    Validar con el área legal de la entidad. Para bloquear también el sábado: {5, 6}.
DIAS_BLOQUEADOS = {6}

# Calendario de feriados de Perú (se actualiza por año automáticamente).
_feriados_pe = holidays.Peru()


def _ventana() -> tuple[time, time]:
    """Horario permitido vigente (configurable por .env)."""
    return time(settings.compliance_hora_inicio, 0), time(settings.compliance_hora_fin, 0)


def esta_permitido(momento: datetime | None = None) -> tuple[bool, str]:
    """Devuelve (permitido, motivo) según horario y calendario peruano."""
    momento = momento or datetime.now()

    # Modo pruebas: salta la validación de horario/día (no usar en producción).
    if not settings.compliance_enabled:
        return True, "Validación de horario desactivada (COMPLIANCE_ENABLED=false, modo pruebas)."

    inicio, fin = _ventana()

    if momento.weekday() in DIAS_BLOQUEADOS:
        return False, "No se permite contactar los domingos (Indecopi Art. 62b)."

    if momento.date() in _feriados_pe:
        nombre = _feriados_pe.get(momento.date())
        return False, f"Feriado en Perú ({nombre}); contacto no permitido (Indecopi Art. 62b)."

    if not (inicio <= momento.time() < fin):
        return False, f"Fuera del horario permitido {inicio:%H:%M}–{fin:%H:%M} (Indecopi Art. 62b)."

    return True, "Contacto permitido."


def proximo_horario_permitido(desde: datetime | None = None) -> datetime:
    """Calcula el siguiente instante permitido (para reprogramar envíos)."""
    inicio, _ = _ventana()
    actual = desde or datetime.now()
    # Avanza en pasos de 30 min hasta encontrar una ventana válida (máx. 8 días).
    limite = actual + timedelta(days=8)
    while actual < limite:
        if actual.time() < inicio:
            actual = actual.replace(hour=inicio.hour, minute=inicio.minute, second=0, microsecond=0)
        permitido, _ = esta_permitido(actual)
        if permitido:
            return actual
        actual += timedelta(minutes=30)
    return actual
