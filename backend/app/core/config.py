"""Configuración central del backend.

Lee variables de entorno desde `.env` (ver `.env.example`). Todos los campos
tienen valor por defecto vacío para que la app arranque sin credenciales:
cada servicio valida sus llaves solo cuando se usa.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "SCI · Sistema de Cobranzas Inteligente"
    environment: str = "development"

    # --- WhatsApp: proveedor del canal ---
    # "cloud"   = API oficial de Meta (producción).
    # "neonize" = WhatsApp Web NO oficial (solo pruebas; riesgo de baneo).
    wa_provider: str = "cloud"
    wa_neonize_session: str = "sci_wa.db"  # archivo de sesión local (gitignoreado)
    # Gracia (segundos) que espera antes de ignorar un mensaje "sin contacto
    # previo": da tiempo a que se registre el contacto recién enviado. 0 = no espera.
    wa_gracia_segundos: int = 0

    # --- WhatsApp Cloud API (Meta) ---
    wa_access_token: str = ""
    wa_phone_number_id: str = ""
    wa_verify_token: str = "sci-verify-token"
    wa_api_version: str = "v21.0"

    # --- Twilio (SMS + número de voz) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_sms_from: str = ""  # número E.164 o sender ID alfanumérico

    # --- Vapi (Voz AI) ---
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""

    # --- LLM del bot conversacional (proveedor configurable) ---
    # Gemini, Groq y OpenAI exponen la misma API de chat, así que se usa un
    # único cliente cambiando provider/base_url/modelo. Por defecto Gemini Flash
    # (gratis, sin tarjeta); para "mejores resultados" usar openai/gpt-4o-mini.
    llm_provider: str = "gemini"            # gemini · groq · openai
    llm_api_key: str = ""                   # si vacío, cae a openai_api_key
    llm_model: str = "gemini-2.5-flash"
    llm_base_url: str = ""                  # si vacío, se deriva del provider

    # --- OpenAI (compat. y proveedor "openai") ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- Cumplimiento (Indecopi Art. 62b) ---
    # En producción: True con el horario legal 07:00–20:00. Para PRUEBAS fuera de
    # horario, pon COMPLIANCE_ENABLED=false en .env (vuelve a true para el demo real).
    compliance_enabled: bool = True
    compliance_hora_inicio: int = 7   # 07:00
    compliance_hora_fin: int = 20     # 20:00

    # --- Autenticación (JWT) ---
    jwt_secret: str = "cambia-esto-en-produccion-sci-2026"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 horas

    # --- Base de datos ---
    database_url: str = "sqlite:///./sci.db"


settings = Settings()
