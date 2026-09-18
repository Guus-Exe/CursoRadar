"""Application configuration management using Pydantic Settings."""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Senac Monitor."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram configuration
    telegram_bot_token: Optional[str] = Field(
        default=None,
        description="Token do Bot do Telegram fornecido pelo @BotFather",
        alias="TELEGRAM_BOT_TOKEN",
    )
    telegram_chat_id: Optional[str] = Field(
        default=None,
        description="ID do chat ou usuário no Telegram",
        alias="TELEGRAM_CHAT_ID",
    )

    # Monitoring intervals
    check_interval_minutes: int = Field(
        default=5,
        ge=1,
        description="Intervalo em minutos entre checagens da oferta",
        alias="CHECK_INTERVAL_MINUTES",
    )
    discovery_interval_minutes: int = Field(
        default=60,
        ge=5,
        description="Intervalo em minutos para busca de novas ofertas",
        alias="DISCOVERY_INTERVAL_MINUTES",
    )

    # Database
    database_url: str = Field(
        default="sqlite:///data/senac_monitor.db",
        description="URL de conexão com o banco de dados",
        alias="DATABASE_URL",
    )

    # Supabase (Backend Multi-usuário)
    supabase_url: Optional[str] = Field(
        default=None,
        description="URL do projeto Supabase",
        alias="SUPABASE_URL",
    )
    supabase_service_role_key: Optional[str] = Field(
        default=None,
        description="Chave Service Role privada do Supabase para acesso backend",
        alias="SUPABASE_SERVICE_ROLE_KEY",
    )

    # Monitored Course and Offer
    senac_offer_url: str = Field(
        default="https://www.sp.senac.br/senac-lapa-faustolo/cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario?bolsa=true&oferta=9900357333",
        description="URL da oferta inicial a monitorar",
        alias="SENAC_OFFER_URL",
    )
    course_name: str = Field(
        default="Técnico em Modelagem do Vestuário",
        description="Nome do curso para pesquisa e exibição",
        alias="COURSE_NAME",
    )
    unit_name: str = Field(
        default="Senac Lapa Faustolo",
        description="Unidade Senac alvo",
        alias="UNIT_NAME",
    )
    target_shift: str = Field(
        default="Noturno",
        description="Turno de interesse (Noturno, Manhã, Tarde, Integral)",
        alias="TARGET_SHIFT",
    )
    target_offer_id: Optional[str] = Field(
        default="9900357333",
        description="Código da oferta específica a monitorar",
        alias="TARGET_OFFER_ID",
    )
    senac_bolsa_auth: str = Field(
        default="",
        description="Authorization header para API de bolsas do Senac SP (definido via env var SENAC_BOLSA_AUTH)",
        alias="SENAC_BOLSA_AUTH",
    )

    # Resilience & Alert thresholds
    consecutive_failures_alert_threshold: int = Field(
        default=5,
        ge=2,
        description="Falhas consecutivas antes de emitir alerta de saúde",
        alias="CONSECUTIVE_FAILURES_ALERT_THRESHOLD",
    )
    request_timeout_seconds: float = Field(
        default=20.0,
        description="Timeout em segundos para requisições HTTP",
        alias="REQUEST_TIMEOUT_SECONDS",
    )
    max_retries: int = Field(
        default=3,
        description="Tentativas em caso de erro temporário",
        alias="MAX_RETRIES",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Nível de log (DEBUG, INFO, WARNING, ERROR)",
        alias="LOG_LEVEL",
    )

    # Optional WhatsApp integration
    whatsapp_enabled: bool = Field(
        default=False,
        description="Habilita provedor WhatsApp",
        alias="WHATSAPP_ENABLED",
    )
    whatsapp_api_url: Optional[str] = Field(
        default=None,
        alias="WHATSAPP_API_URL",
    )
    whatsapp_api_token: Optional[str] = Field(
        default=None,
        alias="WHATSAPP_API_TOKEN",
    )
    whatsapp_phone_number: Optional[str] = Field(
        default=None,
        alias="WHATSAPP_PHONE_NUMBER",
    )

    # Legacy CourseMonitor toggle (disabled by default in production)
    enable_legacy_monitor: bool = Field(
        default=False,
        description="Habilita monitor legado CourseMonitor em produção (desativado por padrão)",
        alias="ENABLE_LEGACY_MONITOR",
    )


def get_settings() -> Settings:
    """Returns singleton instance of application settings."""
    return Settings()
