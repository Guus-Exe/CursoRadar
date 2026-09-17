"""Multi-User Course Worker Orchestrator with Heartbeat and Deduplication."""

import asyncio
from datetime import datetime
import time
from typing import Any, Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import Settings, get_settings
from app.database import Database
from app.matching import MatchingEngine, MatchResult, MonitorPreferences, OfferChangeEvent, UserMonitor
from app.models import DiscoveredOffer, OfferState, StateDiff
from app.notifications.telegram import TelegramProvider
from app.providers.base import EducationProvider
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.providers.senac import SenacSPProvider
from app.telegram_link import TelegramLinkManager
from app.utils.diff import compute_offer_diff
from app.utils.logger import logger


class CourseWorker:
    """Orchestrates multi-user monitoring cycles, discovery, matching, and health tracking."""

    def __init__(
        self,
        worker_id: str = "worker-default-1",
        settings: Optional[Settings] = None,
        database: Optional[Database] = None,
        provider: Optional[EducationProvider] = None,
        registry: Optional[ProviderRegistry] = None,
        telegram_provider: Optional[TelegramProvider] = None,
        link_manager: Optional[TelegramLinkManager] = None,
        matching_engine: Optional[MatchingEngine] = None,
    ):
        self.worker_id = worker_id
        self.settings = settings or get_settings()
        self.db = database or Database(self.settings.database_url)
        self.registry = registry or ProviderRegistry()
        if provider:
            self.provider = provider
            self.registry.register(provider)
        elif not self.registry.list_providers():
            default_senac = SenacSPProvider(settings=self.settings)
            self.provider = default_senac
            self.registry.register(default_senac)
        else:
            self.provider = next(iter(self.registry.list_providers()), None)

        self.link_manager = link_manager or TelegramLinkManager(
            supabase_url=self.settings.supabase_url,
            supabase_service_role_key=self.settings.supabase_service_role_key,
        )
        self.telegram_provider = telegram_provider or TelegramProvider(
            bot_token=self.settings.telegram_bot_token,
            chat_id=self.settings.telegram_chat_id,
            link_manager=self.link_manager,
        )
        self.matching_engine = matching_engine or MatchingEngine(registry=self.registry)
        self.scheduler = AsyncIOScheduler()
        self._lock = asyncio.Lock()
        self.consecutive_failures = 0
        self.active_monitors: List[UserMonitor] = []

    @property
    def is_paused(self) -> bool:
        """Checks if monitoring is globally paused."""
        val = self.db.get_setting("is_paused", "false")
        return val.lower() in ("true", "1", "yes")

    def register_monitor(self, monitor: UserMonitor) -> None:
        """Registers or updates a user monitor in memory."""
        self.active_monitors = [m for m in self.active_monitors if m.id != monitor.id]
        if not monitor.telegram_chat_id and self.link_manager:
            chat_id = self.link_manager.get_chat_id_by_user(monitor.user_id)
            if chat_id:
                monitor.telegram_chat_id = chat_id
        if monitor.active:
            self.active_monitors.append(monitor)
            logger.info(f"Monitor {monitor.id} registrado para usuário {monitor.user_id}.")

    def _ensure_monitors_telegram(self) -> None:
        """Hydrates telegram_chat_id from Supabase for any active monitors lacking it."""
        if self.link_manager:
            for mon in self.active_monitors:
                if not mon.telegram_chat_id:
                    chat_id = self.link_manager.get_chat_id_by_user(mon.user_id)
                    if chat_id:
                        mon.telegram_chat_id = chat_id

    async def run_check_cycle(self) -> Dict[str, Any]:
        """Executes a full verification cycle across all tracked offers and active providers."""
        if self.is_paused:
            logger.info("Ciclo de verificação ignorado: worker em pausa.")
            return {"status": "paused", "offers_checked": 0}

        start_time = time.time()
        offers_checked = 0
        offers_succeeded = 0
        offers_failed = 0
        alerts_sent = 0

        async with self._lock:
            target_offer_id = self.settings.target_offer_id or "9900357333"
            target_url = self.settings.senac_offer_url

            logger.info(f"[{self.worker_id}] Iniciando ciclo de checagem multi-provider.")

            active_providers = self.registry.get_active_providers()
            if not active_providers:
                logger.warning(f"[{self.worker_id}] Nenhum provedor ativo encontrado no registry.")

            for p_slug, p_instance in active_providers.items():
                logger.info(f"[{self.worker_id}] Verificando provider '{p_slug}' ({p_instance.name})")
                try:
                    offers_checked += 1
                    current_state = await p_instance.get_offer_state(target_url)
                    offers_succeeded += 1

                    # Retrieve previous state
                    previous_state = self.db.get_last_state(target_offer_id)

                    # Compute state diff
                    diff = compute_offer_diff(previous_state, current_state)

                    # Handle detected changes and matching
                    if diff.has_changed:
                        logger.info(f"[{self.worker_id}] Mudança detectada na oferta {target_offer_id} pelo provider {p_slug}!")
                        for reason in diff.reasons:
                            logger.info(f"  • {reason}")

                        change_type = "STATUS_CHANGE"
                        if not (previous_state and previous_state.inscricao_disponivel) and current_state.inscricao_disponivel:
                            change_type = "ENROLLMENT_OPEN"
                        elif not (previous_state and previous_state.bolsa_disponivel) and current_state.bolsa_disponivel:
                            change_type = "SCHOLARSHIP_OPEN"

                        event = OfferChangeEvent(
                            offer_id=target_offer_id,
                            provider_slug=p_slug,
                            institution_name=p_instance.name,
                            institution_id="11111111-1111-1111-1111-111111111111",
                            location_id="22222222-2222-2222-2222-222222222221",
                            course_id="33333333-3333-3333-3333-333333333331",
                            shift=current_state.turno,
                            change_type=change_type,
                            reasons=diff.reasons,
                            previous_state=previous_state,
                            current_state=current_state,
                            url=target_url,
                        )

                        # Execute matching against all active user monitors
                        self._ensure_monitors_telegram()
                        matches = self.matching_engine.match(event, self.active_monitors)

                        # Dispatch personalized alerts
                        for match in matches:
                            if self.db.is_duplicate_alert(
                                alert_type=match.change_type,
                                offer_id=match.offer_id,
                                state_hash=match.fingerprint,
                                channel="telegram",
                                fingerprint=match.fingerprint,
                            ):
                                logger.debug(f"Alerta já enviado no banco para {match.fingerprint}")
                                continue

                            sent = await self.telegram_provider.send_to_user(
                                recipient_id=match.telegram_chat_id,
                                text=match.message,
                            )
                            if sent:
                                alerts_sent += 1
                                self.db.record_alert(
                                    alert_type=match.change_type,
                                    offer_id=match.offer_id,
                                    state_hash=match.fingerprint,
                                    message_content=match.message,
                                    channel="telegram",
                                    user_id=match.user_id,
                                    monitor_id=match.monitor_id,
                                    fingerprint=match.fingerprint,
                                )

                    # Persist offer state and check entry
                    self.db.upsert_offer(
                        offer_id=target_offer_id,
                        curso=current_state.curso,
                        unidade=current_state.unidade,
                        turno=current_state.turno,
                        url=target_url,
                        state=current_state,
                    )
                    self.db.record_check(
                        offer_id=target_offer_id,
                        is_success=True,
                        status_code=200,
                        state=current_state,
                        diff=diff,
                    )
                    self.consecutive_failures = 0

                except Exception as err:
                    offers_failed += 1
                    self.consecutive_failures += 1
                    error_msg = f"{type(err).__name__}: {str(err)}"
                    logger.error(f"[{self.worker_id}] Falha ao verificar provider {p_slug}: {error_msg}")

                    self.db.record_check(
                        offer_id=target_offer_id,
                        is_success=False,
                        status_code=500,
                        error_message=error_msg,
                    )
                    self.db.record_system_error(
                        source=f"worker:{self.worker_id}:{p_slug}",
                        error_type=type(err).__name__,
                        message=str(err),
                    )

            # Record heartbeat & operational observability
            duration = time.time() - start_time
            self.db.record_worker_heartbeat(
                worker_id=self.worker_id,
                duration_seconds=duration,
                offers_checked=offers_checked,
                offers_succeeded=offers_succeeded,
                offers_failed=offers_failed,
                status="healthy" if offers_failed == 0 else "degraded",
                metadata={"alerts_sent": alerts_sent, "monitors_count": len(self.active_monitors)},
            )

            return {
                "worker_id": self.worker_id,
                "status": "completed",
                "duration": duration,
                "offers_checked": offers_checked,
                "offers_succeeded": offers_succeeded,
                "offers_failed": offers_failed,
                "alerts_sent": alerts_sent,
            }

    async def run_discovery_cycle(self) -> List[DiscoveredOffer]:
        """Discovers new course offers and matches with monitors across all active providers."""
        if self.is_paused:
            return []

        logger.info(f"[{self.worker_id}] Iniciando descoberta de novas ofertas multi-provider...")
        all_discovered: List[DiscoveredOffer] = []
        active_providers = self.registry.get_active_providers()

        for p_slug, p_instance in active_providers.items():
            try:
                discovered = await p_instance.discover_offers(
                    course_name=self.settings.course_name,
                    unit_name=self.settings.unit_name,
                    shift=self.settings.target_shift,
                )

                for offer in discovered:
                    existing = self.db.get_offer(offer.codigo_oferta)
                    if not existing:
                        logger.info(f"[{self.worker_id}][{p_slug}] Nova oferta descoberta: {offer.codigo_oferta} ({offer.turno})")
                        self.db.upsert_offer(
                            offer_id=offer.codigo_oferta,
                            curso=offer.curso,
                            unidade=offer.unidade,
                            turno=offer.turno,
                            url=offer.url,
                        )
                        state = OfferState(
                            curso=offer.curso,
                            unidade=offer.unidade,
                            turno=offer.turno,
                            status="Nova oferta aberta",
                            codigo_oferta=offer.codigo_oferta,
                            inscricao_disponivel=offer.vagas_disponiveis,
                            bolsa_disponivel=offer.bolsa_disponivel,
                        )
                        event = OfferChangeEvent(
                            offer_id=offer.codigo_oferta,
                            provider_slug=p_slug,
                            institution_name=p_instance.name,
                            institution_id="11111111-1111-1111-1111-111111111111",
                            location_id="22222222-2222-2222-2222-222222222221",
                            course_id="33333333-3333-3333-3333-333333333331",
                            shift=offer.turno,
                            change_type="NEW_OFFER",
                            reasons=["Nova turma aberta pela instituição!"],
                            current_state=state,
                            url=offer.url,
                        )
                        self._ensure_monitors_telegram()
                        matches = self.matching_engine.match(event, self.active_monitors)
                        for match in matches:
                            if self.db.is_duplicate_alert(
                                alert_type=match.change_type,
                                offer_id=match.offer_id,
                                state_hash=match.fingerprint,
                                channel="telegram",
                                fingerprint=match.fingerprint,
                            ):
                                continue
                            sent = await self.telegram_provider.send_to_user(
                                recipient_id=match.telegram_chat_id,
                                text=match.message,
                            )
                            if sent:
                                self.db.record_alert(
                                    alert_type=match.change_type,
                                    offer_id=match.offer_id,
                                    state_hash=match.fingerprint,
                                    message_content=match.message,
                                    channel="telegram",
                                    user_id=match.user_id,
                                    monitor_id=match.monitor_id,
                                    fingerprint=match.fingerprint,
                                )

                all_discovered.extend(discovered)
            except Exception as err:
                logger.error(f"[{self.worker_id}] Erro no ciclo de descoberta para provider '{p_slug}': {err}")
                self.db.record_system_error(
                    source=f"worker:{self.worker_id}:{p_slug}:discovery",
                    error_type=type(err).__name__,
                    message=str(err),
                )

        return all_discovered

    def start_scheduler(self) -> None:
        """Starts background scheduling."""
        check_interval = max(1, self.settings.check_interval_minutes)
        discovery_interval = max(5, self.settings.discovery_interval_minutes)

        self.scheduler.add_job(
            self.run_check_cycle,
            "interval",
            minutes=check_interval,
            id="worker_course_check",
            replace_existing=True,
            next_run_time=datetime.now(),
        )
        self.scheduler.add_job(
            self.run_discovery_cycle,
            "interval",
            minutes=discovery_interval,
            id="worker_discovery",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(f"Agendador do Worker iniciado: checagem={check_interval}m, descoberta={discovery_interval}m")

    def stop_scheduler(self) -> None:
        """Stops background scheduling."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Agendador do Worker finalizado.")
