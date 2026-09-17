"""Central monitoring orchestrator and scheduler."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import Settings, get_settings
from app.database import Database
from app.models import DiscoveredOffer, OfferState, StateDiff
from app.notifications.base import NotificationProvider
from app.notifications.telegram import TelegramProvider
from app.notifications.whatsapp import WhatsAppProvider
from app.scrapers.base import BaseScraper
from app.scrapers.senac import SenacScraper
from app.utils.diff import compute_offer_diff
from app.utils.logger import logger


class CourseMonitor:
    """Coordinates checking course status, diff calculation, persistence and alerting."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        database: Optional[Database] = None,
        scraper: Optional[BaseScraper] = None,
        providers: Optional[List[NotificationProvider]] = None,
    ):
        self.settings = settings or get_settings()
        self.db = database or Database(self.settings.database_url)
        self.scraper = scraper or SenacScraper()

        # Notification providers
        if providers is not None:
            self.providers = providers
        else:
            self.providers = [
                TelegramProvider(),
                WhatsAppProvider(),
            ]

        self.scheduler = AsyncIOScheduler()
        self.consecutive_failures = 0
        self.health_alert_sent = False
        self._lock = asyncio.Lock()

    @property
    def is_paused(self) -> bool:
        """Checks if monitoring is currently paused."""
        val = self.db.get_setting("is_paused", "false")
        return val.lower() in ("true", "1", "yes")

    def pause(self) -> str:
        """Pauses periodic monitoring."""
        self.db.set_setting("is_paused", "true")
        logger.info("Monitoramento pausado pelo usuário.")
        return "⏸️ Monitoramento pausado com sucesso. Use /resume para retomar."

    def resume(self) -> str:
        """Resumes periodic monitoring."""
        self.db.set_setting("is_paused", "false")
        logger.info("Monitoramento retomado pelo usuário.")
        return "▶️ Monitoramento retomado. As verificações periódicas estão ativas."

    async def run_check_cycle(self) -> Optional[StateDiff]:
        """Executes a single check cycle for the target course offer."""
        if self.is_paused:
            logger.info("Verificação ignorada: monitoramento está em pausa.")
            return None

        async with self._lock:
            offer_id = self.settings.target_offer_id or "9900357333"
            logger.info(f"Verificando oferta {offer_id}")

            try:
                # 1. Fetch current state
                current_state = await self.scraper.get_offer_state(self.settings.senac_offer_url)
                logger.info("Página carregada")
                logger.info(f"Status: {current_state.status}")

                # 2. Get previous state from database
                previous_state = self.db.get_last_state(offer_id)

                # 3. Compute diff
                diff = compute_offer_diff(previous_state, current_state)

                if not diff.has_changed:
                    logger.info("Nenhuma mudança encontrada")
                else:
                    logger.info("ALTERAÇÃO DETECTADA")
                    for reason in diff.reasons:
                        logger.info(reason)

                    # 4. If actionable or status changed, notify
                    if diff.is_actionable or (previous_state and previous_state.status != current_state.status):
                        alert_hash = current_state.compute_alert_hash()
                        is_duplicate = self.db.is_duplicate_alert(
                            alert_type="VAGA_ENCONTRADA",
                            offer_id=offer_id,
                            state_hash=alert_hash,
                            cooldown_hours=6,
                        )

                        if is_duplicate:
                            logger.info("Alerta já enviado recentemente para este estado (prevenção de duplicatas ativa).")
                        else:
                            for provider in self.providers:
                                sent = await provider.send_offer_alert(diff, self.settings.senac_offer_url)
                                if sent:
                                    logger.info(f"Alerta enviado por {provider.__class__.__name__}")
                                    self.db.record_alert(
                                        alert_type="VAGA_ENCONTRADA",
                                        offer_id=offer_id,
                                        state_hash=alert_hash,
                                        message_content=diff.summary(),
                                        channel=provider.__class__.__name__.lower(),
                                    )

                # 5. Persist state and check history
                self.db.upsert_offer(
                    offer_id=offer_id,
                    curso=current_state.curso,
                    unidade=current_state.unidade,
                    turno=current_state.turno,
                    url=self.settings.senac_offer_url,
                    state=current_state,
                )
                self.db.record_check(
                    offer_id=offer_id,
                    is_success=True,
                    status_code=200,
                    state=current_state,
                    diff=diff,
                )

                # Reset consecutive failures
                if self.consecutive_failures > 0:
                    if self.health_alert_sent:
                        for provider in self.providers:
                            await provider.send_message("✅ Conexão com o Senac restabelecida com sucesso!")
                        self.health_alert_sent = False
                    self.consecutive_failures = 0

                return diff

            except Exception as err:
                self.consecutive_failures += 1
                error_msg = f"{type(err).__name__}: {str(err)}"
                logger.error(f"Erro na verificação da oferta {offer_id}: {error_msg}")

                self.db.record_check(
                    offer_id=offer_id,
                    is_success=False,
                    status_code=500,
                    error_message=error_msg,
                )

                # Send health alert if consecutive failures threshold reached
                if (
                    self.consecutive_failures >= self.settings.consecutive_failures_alert_threshold
                    and not self.health_alert_sent
                ):
                    logger.warning(
                        f"Limite de falhas consecutivas ({self.consecutive_failures}) atingido. Enviando alerta de saúde..."
                    )
                    for provider in self.providers:
                        await provider.send_health_alert(self.consecutive_failures, error_msg)
                    self.health_alert_sent = True

                return None

    async def run_discovery_cycle(self) -> List[DiscoveredOffer]:
        """Searches for new offers in the target course and unit."""
        if self.is_paused:
            return []

        logger.info(f"Iniciando ciclo de descoberta de novas ofertas para {self.settings.course_name}...")
        try:
            discovered = await self.scraper.discover_new_offers(
                course_name=self.settings.course_name,
                unit_name=self.settings.unit_name,
                shift=self.settings.target_shift,
            )

            for offer in discovered:
                # Check if this offer is already registered in DB
                existing = self.db.get_offer(offer.codigo_oferta)
                if not existing:
                    logger.info(f"🆕 NOVA OFERTA DETECTADA: {offer.codigo_oferta} ({offer.turno})")
                    # Save in DB
                    self.db.upsert_offer(
                        offer_id=offer.codigo_oferta,
                        curso=offer.curso,
                        unidade=offer.unidade,
                        turno=offer.turno,
                        url=offer.url,
                    )
                    # Alert
                    for provider in self.providers:
                        sent = await provider.send_new_offer_alert(offer)
                        if sent:
                            logger.info(f"Alerta de nova oferta enviado por {provider.__class__.__name__}")
                            self.db.record_alert(
                                alert_type="NOVA_OFERTA",
                                offer_id=offer.codigo_oferta,
                                state_hash=None,
                                message_content=offer.url,
                                channel=provider.__class__.__name__.lower(),
                            )

            return discovered
        except Exception as err:
            logger.error(f"Erro no ciclo de descoberta de ofertas: {err}")
            return []

    async def get_status_summary(self) -> str:
        """Constructs a status text summary for the /status command."""
        offer_id = self.settings.target_offer_id or "9900357333"
        last_check = self.db.get_last_check(offer_id)
        last_state = self.db.get_last_state(offer_id)

        pause_status = "⏸️ Pausado" if self.is_paused else "▶️ Ativo"
        check_time_str = (
            last_check.checked_at.strftime("%d/%m/%Y às %H:%M:%S")
            if last_check
            else "Nenhuma verificação realizada ainda"
        )

        if not last_state:
            return (
                f"📊 STATUS DO MONITOR SENAC\n\n"
                f"Estado: {pause_status}\n"
                f"Última verificação: {check_time_str}\n"
                f"Curso: {self.settings.course_name}\n"
                f"Unidade: {self.settings.unit_name}\n"
                f"Nenhum dado consolidado no momento."
            )

        bolsa_str = "Disponível ✅" if last_state.bolsa_disponivel else "Não disponível ❌"
        inscricao_str = "Aberta ✅" if last_state.inscricao_disponivel else "Fechada / Esgotada ❌"
        horario_str = last_state.horarios[0] if last_state.horarios else "Não informado"
        datas_str = ", ".join(last_state.datas) if last_state.datas else "Não informadas"

        return (
            f"📊 STATUS DO MONITOR SENAC\n\n"
            f"Modo: {pause_status}\n"
            f"Última checagem: {check_time_str}\n"
            f"Curso: {last_state.curso}\n"
            f"Unidade: {last_state.unidade}\n"
            f"Período: {last_state.turno}\n"
            f"Horário: {horario_str}\n"
            f"Datas: {datas_str}\n"
            f"Status atual: {last_state.status}\n"
            f"Inscrição: {inscricao_str}\n"
            f"🎓 Bolsa: {bolsa_str}\n"
            f"Falhas recentes: {self.consecutive_failures}"
        )

    def start_scheduler(self) -> None:
        """Starts the APScheduler background jobs."""
        check_interval = max(1, self.settings.check_interval_minutes)
        discovery_interval = max(5, self.settings.discovery_interval_minutes)

        self.scheduler.add_job(
            self.run_check_cycle,
            "interval",
            minutes=check_interval,
            id="senac_course_check",
            replace_existing=True,
            next_run_time=datetime.now(),
        )

        self.scheduler.add_job(
            self.run_discovery_cycle,
            "interval",
            minutes=discovery_interval,
            id="senac_offer_discovery",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(
            f"Agendador iniciado: checagem a cada {check_interval} min, "
            f"descoberta a cada {discovery_interval} min."
        )

    def stop_scheduler(self) -> None:
        """Stops the APScheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Agendador de tarefas finalizado.")
