"""Programador de tareas (APScheduler) en zona horaria de Lima.

Se inicia en el lifespan de FastAPI. Úsalo para programar envíos respetando
`compliance.proximo_horario_permitido` (p. ej. campañas nocturnas que se
disparan a las 07:00 del siguiente día hábil).
"""
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(timezone="America/Lima")
