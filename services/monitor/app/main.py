"""Main application entry point."""

import asyncio
import signal
import sys
from typing import Optional
from app.config import get_settings
from app.database import Database
from app.matching import MatchingEngine
from app.monitor import CourseMonitor
from app.monitors_repo import SupabaseMonitorRepository
from app.notifications.telegram import TelegramProvider
from app.notifications.whatsapp import WhatsAppProvider
from app.providers.registry import get_provider_registry
from app.providers.senac import SenacSPProvider
from app.scrapers.senac import SenacScraper
from app.telegram_link import TelegramLinkManager
from app.utils.logger import logger
from app.worker import CourseWorker


async def run_application() -> None:
    """Initializes and runs the CursoRadar multi-user worker."""
    settings = get_settings()
    logger.info("==================================================")
    logger.info("     INICIANDO CURSORADAR MULTI-USER WORKER       ")
    logger.info("==================================================")
    logger.info(f"Intervalo de checagem: {settings.check_interval_minutes} minuto(s)")
    logger.info(f"Intervalo de descoberta: {settings.discovery_interval_minutes} minuto(s)")
    logger.info(f"Legacy Monitor Habilitado: {settings.enable_legacy_monitor}")

    # Database
    db = Database(settings.database_url)

    # Link Manager (Supabase persistence with in-memory fallback)
    link_manager = TelegramLinkManager(
        supabase_url=settings.supabase_url,
        supabase_service_role_key=settings.supabase_service_role_key,
    )

    # Providers
    telegram_provider = TelegramProvider(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        link_manager=link_manager,
    )

    # Monitor Repository
    monitor_repo = SupabaseMonitorRepository(
        supabase_url=settings.supabase_url,
        supabase_service_role_key=settings.supabase_service_role_key,
        supabase_client=link_manager.supabase,
    )

    # Provider Registry
    registry = get_provider_registry()
    senac_provider = SenacSPProvider(settings=settings)
    registry.register(senac_provider)

    # Matching Engine
    matching_engine = MatchingEngine(registry=registry)

    # Primary Multi-User Worker
    worker = CourseWorker(
        worker_id="cursoradar-worker-main",
        settings=settings,
        database=db,
        registry=registry,
        telegram_provider=telegram_provider,
        link_manager=link_manager,
        matching_engine=matching_engine,
        monitor_repo=monitor_repo,
    )

    # Initial sync from Supabase
    await worker.sync_monitors_from_supabase()

    # Callbacks for Telegram bot commands wired to CourseWorker
    async def cmd_status_callback(chat_id: Optional[str] = None) -> str:
        return await worker.get_status_summary(chat_id)

    async def cmd_check_callback(chat_id: Optional[str] = None) -> str:
        return await worker.run_user_check(chat_id)

    async def cmd_link_callback(chat_id: Optional[str] = None) -> str:
        return await worker.get_user_links(chat_id)

    async def cmd_pause_callback(chat_id: Optional[str] = None, arg: Optional[str] = None) -> str:
        return await worker.pause_user(chat_id, arg)

    async def cmd_resume_callback(chat_id: Optional[str] = None, arg: Optional[str] = None) -> str:
        return await worker.resume_user(chat_id, arg)

    # Telegram bot app
    telegram_app = telegram_provider.create_application(
        status_callback=cmd_status_callback,
        check_callback=cmd_check_callback,
        link_callback=cmd_link_callback,
        pause_callback=cmd_pause_callback,
        resume_callback=cmd_resume_callback,
    )

    # Start primary multi-user scheduler
    worker.start_scheduler()

    # Optional legacy fallback (only if explicitly enabled)
    legacy_monitor: Optional[CourseMonitor] = None
    if settings.enable_legacy_monitor:
        logger.warning("ATENÇÃO: ENABLE_LEGACY_MONITOR está ativo. Iniciando CourseMonitor legado em paralelo.")
        scraper = SenacScraper()
        legacy_monitor = CourseMonitor(
            settings=settings,
            database=db,
            scraper=scraper,
            providers=[telegram_provider],
        )
        legacy_monitor.start_scheduler()

    # Graceful shutdown event
    stop_event = asyncio.Event()

    def request_shutdown() -> None:
        logger.info("Recebido sinal de encerramento. Finalizando worker...")
        stop_event.set()

    # Setup signal handlers where supported
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown)
        except (NotImplementedError, RuntimeError):
            # Windows may not support add_signal_handler for some signals
            pass

    if telegram_app is not None:
        logger.info("Iniciando bot interativo do Telegram...")
        try:
            await telegram_app.initialize()
            await telegram_app.start()
            await telegram_app.updater.start_polling()  # type: ignore
            logger.info("Bot do Telegram pronto para responder comandos multiusuário (/status, /check, /link, /pause, /resume).")

            # Wait for shutdown signal
            await stop_event.wait()
        except Exception as err:
            logger.error(f"Erro na execução do bot Telegram: {err}")
        finally:
            logger.info("Encerrando bot do Telegram...")
            if telegram_app.updater and telegram_app.updater.running:  # type: ignore
                await telegram_app.updater.stop()  # type: ignore
            if telegram_app.running:
                await telegram_app.stop()
            await telegram_app.shutdown()
    else:
        logger.warning(
            "Bot do Telegram não inicializado porque TELEGRAM_BOT_TOKEN não foi configurado no .env. "
            "O worker continuará executando as checagens periódicas em modo headless."
        )
        try:
            await stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            pass

    worker.stop_scheduler()
    if legacy_monitor is not None:
        legacy_monitor.stop_scheduler()
    logger.info("CursoRadar Worker finalizado com sucesso.")


def main() -> None:
    """Synchronous entry point."""
    try:
        asyncio.run(run_application())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Aplicação encerrada pelo usuário.")
        sys.exit(0)


if __name__ == "__main__":
    main()
