"""Main application entry point."""

import asyncio
import signal
import sys
from typing import Optional
from app.config import get_settings
from app.database import Database
from app.monitor import CourseMonitor
from app.notifications.telegram import TelegramProvider
from app.notifications.whatsapp import WhatsAppProvider
from app.scrapers.senac import SenacScraper
from app.utils.logger import logger


async def run_application() -> None:
    """Initializes and runs the Senac course monitor."""
    settings = get_settings()
    logger.info("==================================================")
    logger.info("       INICIANDO SENAC MONITOR — SP               ")
    logger.info("==================================================")
    logger.info(f"Curso alvo: {settings.course_name}")
    logger.info(f"Unidade alvo: {settings.unit_name} | Turno: {settings.target_shift}")
    logger.info(f"Intervalo de checagem: {settings.check_interval_minutes} minuto(s)")
    logger.info(f"URL: {settings.senac_offer_url}")

    # Database
    db = Database(settings.database_url)

    # Scraper
    scraper = SenacScraper()

    # Providers
    telegram_provider = TelegramProvider(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )
    whatsapp_provider = WhatsAppProvider()

    providers = [telegram_provider, whatsapp_provider]

    # Monitor
    monitor = CourseMonitor(
        settings=settings,
        database=db,
        scraper=scraper,
        providers=providers,
    )

    # Callbacks for Telegram bot commands
    async def cmd_status_callback() -> str:
        return await monitor.get_status_summary()

    async def cmd_check_callback() -> str:
        diff = await monitor.run_check_cycle()
        if diff is None:
            return "⚠️ A verificação encontrou um erro ou o monitor está pausado. Verifique os logs."
        curr = diff.current_state
        return (
            f"✅ Verificação concluída!\n\n"
            f"Curso: {curr.curso}\n"
            f"Status: {curr.status}\n"
            f"Inscrição: {'Aberta' if curr.inscricao_disponivel else 'Indisponível'}\n"
            f"Bolsa: {'Disponível' if curr.bolsa_disponivel else 'Indisponível'}\n"
            f"Mudanças: {diff.summary()}"
        )

    def cmd_link_callback() -> str:
        return settings.senac_offer_url

    def cmd_pause_callback() -> str:
        return monitor.pause()

    def cmd_resume_callback() -> str:
        return monitor.resume()

    # Telegram bot app
    telegram_app = telegram_provider.create_application(
        status_callback=cmd_status_callback,
        check_callback=cmd_check_callback,
        link_callback=cmd_link_callback,
        pause_callback=cmd_pause_callback,
        resume_callback=cmd_resume_callback,
    )

    # Start APScheduler
    monitor.start_scheduler()

    # Graceful shutdown event
    stop_event = asyncio.Event()

    def request_shutdown() -> None:
        logger.info("Recebido sinal de encerramento. Finalizando monitor...")
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
            logger.info("Bot do Telegram pronto para responder comandos (/status, /check, /link, /pause, /resume).")

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
            "O monitor continuará executando as checagens periódicas em modo headless."
        )
        try:
            await stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            pass

    monitor.stop_scheduler()
    logger.info("Senac Monitor finalizado com sucesso.")


def main() -> None:
    """Synchronous entry point."""
    try:
        asyncio.run(run_application())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Aplicação encerrada pelo usuário.")
        sys.exit(0)


if __name__ == "__main__":
    main()
