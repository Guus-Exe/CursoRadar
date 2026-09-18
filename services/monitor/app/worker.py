"""Multi-User Course Worker Orchestrator with Heartbeat and Deduplication."""

import asyncio
from datetime import datetime
import time
from typing import Any, Dict, List, Optional, Set
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import Settings, get_settings
from app.database import Database
from app.matching import MatchingEngine, MatchResult, MonitorPreferences, OfferChangeEvent, UserMonitor
from app.models import DiscoveredOffer, OfferState, StateDiff
from app.monitors_repo import SupabaseMonitorRepository
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
        monitor_repo: Optional[SupabaseMonitorRepository] = None,
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
        self.monitor_repo = monitor_repo or SupabaseMonitorRepository(
            supabase_url=self.settings.supabase_url,
            supabase_service_role_key=self.settings.supabase_service_role_key,
            supabase_client=self.link_manager.supabase if self.link_manager else None,
        )
        self.matching_engine = matching_engine or MatchingEngine(registry=self.registry)
        self.scheduler = AsyncIOScheduler()
        self._lock = asyncio.Lock()
        self.consecutive_failures = 0
        self.active_monitors: List[UserMonitor] = []
        self._user_paused_ids: Dict[str, Set[str]] = {}

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

    async def sync_monitors_from_supabase(self) -> List[UserMonitor]:
        """Synchronizes active monitors from Supabase with a last-known-good cache strategy."""
        try:
            fresh_monitors = await self.monitor_repo.list_active_monitors()
            if self.link_manager:
                for m in fresh_monitors:
                    if not m.telegram_chat_id:
                        chat_id = self.link_manager.get_chat_id_by_user(m.user_id)
                        if chat_id:
                            m.telegram_chat_id = chat_id

            if fresh_monitors or self.monitor_repo.supabase is not None or not self.active_monitors:
                self.active_monitors = fresh_monitors

            logger.info(
                f"[{self.worker_id}] Sincronização Supabase concluída: "
                f"{len(self.active_monitors)} monitor(es) ativo(s) em memória."
            )
            return self.active_monitors
        except Exception as err:
            logger.error(
                f"[{self.worker_id}] Erro ao sincronizar monitores com Supabase: {err}. "
                f"Mantendo cache last-known-good ({len(self.active_monitors)} monitores)."
            )
            return self.active_monitors

    async def get_status_summary(self, chat_id: Optional[str] = None) -> str:
        """Constructs a personalized status summary for the requesting Telegram user."""
        if chat_id:
            if not self.link_manager:
                return "❌ Sistema de vinculação indisponível."
            account = self.link_manager.get_account_by_chat(chat_id)
            if not account:
                return (
                    "ℹ️ Sua conta do Telegram ainda não está vinculada ao CursoRadar.\n\n"
                    "Acesse o dashboard web, gere seu link e envie `/start <token>` para conectar."
                )

            monitors = await self.monitor_repo.get_user_monitors(account.user_id)
            if not monitors:
                return (
                    "📊 STATUS DOS SEUS MONITORES NO CURSORADAR\n\n"
                    "Você não possui nenhum monitor cadastrado no momento.\n"
                    "Acesse o dashboard web para cadastrar seus cursos de interesse!"
                )

            lines = ["📊 SEUS MONITORES NO CURSORADAR\n"]
            for idx, mon in enumerate(monitors, 1):
                status_icon = "▶️ Ativo" if mon.active else "⏸️ Pausado"
                query_name = mon.query_text or "Curso sem título"
                prov_str = "Todos os provedores" if mon.all_providers else (", ".join(mon.provider_slugs) or "Senac SP")
                shift_str = mon.shift or "Qualquer"
                modality_str = (mon.modality or "all").capitalize()
                lines.append(
                    f"[{idx}] {query_name}\n"
                    f"    • Status: {status_icon}\n"
                    f"    • Turno: {shift_str} | Modalidade: {modality_str}\n"
                    f"    • Provedores: {prov_str}\n"
                    f"    • ID: {mon.id[:8]}\n"
                )

            lines.append(
                "Comandos disponíveis:\n"
                "• /check — verifica seus cursos agora\n"
                "• /pause [número ou id] — pausa um monitor específico\n"
                "• /pause all — pausa todos os seus monitores\n"
                "• /resume [número ou id] — reativa um monitor específico\n"
                "• /resume all — reativa seus monitores pausados"
            )
            return "\n".join(lines)

        return (
            f"📊 STATUS DO WORKER CURSORADAR\n\n"
            f"ID: {self.worker_id}\n"
            f"Monitores ativos em memória: {len(self.active_monitors)}\n"
            f"Falhas recentes: {self.consecutive_failures}"
        )

    async def run_user_check(self, chat_id: Optional[str] = None) -> str:
        """Executes manual check cycle targeted specifically to the user's monitors."""
        if not chat_id or not self.link_manager:
            return "❌ Identificador de usuário não fornecido ou link manager indisponível."

        account = self.link_manager.get_account_by_chat(chat_id)
        if not account:
            return "ℹ️ Sua conta não está vinculada. Use /start <token> para conectar."

        user_monitors = [
            m for m in await self.monitor_repo.get_user_monitors(account.user_id)
            if m.active
        ]
        if not user_monitors:
            return "ℹ️ Você não possui nenhum monitor ativo para verificação. Crie ou reative seus monitores no dashboard."

        results_lines = [f"🔄 Verificação concluída para seu(s) {len(user_monitors)} monitor(es) ativo(s):\n"]
        active_providers = self.registry.get_active_providers()

        for idx, mon in enumerate(user_monitors, 1):
            q_name = mon.query_text or "Curso"
            found_any = False
            for p_slug, p_instance in active_providers.items():
                try:
                    offers = await p_instance.search_offers(q_name)
                    if offers:
                        found_any = True
                        results_lines.append(f"[{idx}] {q_name} ({p_instance.name}): {len(offers)} turma(s) encontrada(s).")
                except Exception:
                    pass
            if not found_any:
                results_lines.append(f"[{idx}] {q_name}: Nenhuma nova vaga aberta no momento.")

        return "\n".join(results_lines)

    async def pause_user(self, chat_id: Optional[str] = None, arg: Optional[str] = None) -> str:
        """Pauses user's monitor(s) in Supabase without affecting global worker."""
        if not chat_id or not self.link_manager:
            return "❌ Identificador de usuário não fornecido."

        account = self.link_manager.get_account_by_chat(chat_id)
        if not account:
            return "ℹ️ Sua conta não está vinculada. Use /start <token> para conectar."

        monitors = await self.monitor_repo.get_user_monitors(account.user_id)
        if not monitors:
            return "ℹ️ Você não possui monitores cadastrados."

        clean_arg = (arg or "").strip().lower()
        if clean_arg == "all":
            paused_ids = []
            for m in monitors:
                if m.active:
                    await self.monitor_repo.set_monitor_active(m.id, False, user_id=account.user_id)
                    paused_ids.append(m.id)
            self._user_paused_ids.setdefault(account.user_id, set()).update(paused_ids)
            await self.sync_monitors_from_supabase()
            return f"⏸️ {len(paused_ids)} monitor(es) pausado(s) com sucesso. Use /resume all para reativá-los."

        target_mon = None
        if clean_arg.isdigit():
            idx = int(clean_arg) - 1
            if 0 <= idx < len(monitors):
                target_mon = monitors[idx]
        elif clean_arg:
            for m in monitors:
                if m.id.startswith(clean_arg):
                    target_mon = m
                    break
        elif len(monitors) == 1:
            target_mon = monitors[0]
        else:
            return (
                f"ℹ️ Você possui {len(monitors)} monitores cadastrados.\n\n"
                f"Especifique qual monitor deseja pausar (ex: `/pause 1`) ou envie `/pause all` para pausar todos.\n"
                f"Consulte a lista com `/status`."
            )

        if not target_mon:
            return f"⚠️ Monitor '{clean_arg}' não encontrado. Use /status para conferir a numeração."

        await self.monitor_repo.set_monitor_active(target_mon.id, False, user_id=account.user_id)
        self._user_paused_ids.setdefault(account.user_id, set()).add(target_mon.id)
        await self.sync_monitors_from_supabase()
        return f"⏸️ Monitor '{target_mon.query_text or target_mon.id[:8]}' pausado com sucesso. Use /resume {clean_arg or '1'} para reativar."

    async def resume_user(self, chat_id: Optional[str] = None, arg: Optional[str] = None) -> str:
        """Resumes user's monitor(s) in Supabase."""
        if not chat_id or not self.link_manager:
            return "❌ Identificador de usuário não fornecido."

        account = self.link_manager.get_account_by_chat(chat_id)
        if not account:
            return "ℹ️ Sua conta não está vinculada. Use /start <token> para conectar."

        monitors = await self.monitor_repo.get_user_monitors(account.user_id)
        if not monitors:
            return "ℹ️ Você não possui monitores cadastrados."

        clean_arg = (arg or "").strip().lower()
        if clean_arg == "all":
            previously_paused = self._user_paused_ids.get(account.user_id, set())
            resumed_ids = []
            for m in monitors:
                if not m.active and (not previously_paused or m.id in previously_paused):
                    await self.monitor_repo.set_monitor_active(m.id, True, user_id=account.user_id)
                    resumed_ids.append(m.id)
            self._user_paused_ids.pop(account.user_id, None)
            await self.sync_monitors_from_supabase()
            return f"▶️ {len(resumed_ids)} monitor(es) reativado(s) com sucesso. As verificações periódicas estão ativas."

        target_mon = None
        if clean_arg.isdigit():
            idx = int(clean_arg) - 1
            if 0 <= idx < len(monitors):
                target_mon = monitors[idx]
        elif clean_arg:
            for m in monitors:
                if m.id.startswith(clean_arg):
                    target_mon = m
                    break
        else:
            inactive_monitors = [m for m in monitors if not m.active]
            if len(inactive_monitors) == 1:
                target_mon = inactive_monitors[0]
            elif len(inactive_monitors) == 0:
                return "ℹ️ Todos os seus monitores já estão ativos."
            else:
                return (
                    f"ℹ️ Você possui {len(inactive_monitors)} monitores pausados.\n\n"
                    f"Especifique qual monitor reativar (ex: `/resume 1`) ou envie `/resume all` para reativar todos.\n"
                    f"Consulte a lista com `/status`."
                )

        if not target_mon:
            return f"⚠️ Monitor '{clean_arg}' não encontrado. Use /status para conferir a numeração."

        await self.monitor_repo.set_monitor_active(target_mon.id, True, user_id=account.user_id)
        if account.user_id in self._user_paused_ids:
            self._user_paused_ids[account.user_id].discard(target_mon.id)
        await self.sync_monitors_from_supabase()
        return f"▶️ Monitor '{target_mon.query_text or target_mon.id[:8]}' reativado com sucesso. Verificações ativas."

    async def get_user_links(self, chat_id: Optional[str] = None) -> str:
        """Returns links relevant to the requesting user's monitors."""
        if not chat_id or not self.link_manager:
            return "https://cursoradar.com.br/dashboard"

        account = self.link_manager.get_account_by_chat(chat_id)
        if not account:
            return "https://cursoradar.com.br/dashboard"

        monitors = await self.monitor_repo.get_user_monitors(account.user_id, active_only=True)
        if not monitors:
            return "🔗 Painel do CursoRadar:\nhttps://cursoradar.com.br/dashboard"

        lines = [
            "🔗 SEUS LINKS NO CURSORADAR\n",
            "Dashboard: https://cursoradar.com.br/dashboard\n",
            "Cursos monitorados:",
        ]
        for idx, m in enumerate(monitors, 1):
            lines.append(f"• [{idx}] {m.query_text or m.id[:8]}")

        return "\n".join(lines)

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
            await self.sync_monitors_from_supabase()

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

        await self.sync_monitors_from_supabase()

        logger.info(f"[{self.worker_id}] Iniciando descoberta de novas ofertas multi-provider...")
        all_discovered: List[DiscoveredOffer] = []
        active_providers = self.registry.get_active_providers()

        # Gather queries from active monitors
        queries_to_search: List[Dict[str, Any]] = []
        if self.active_monitors:
            seen_queries = set()
            for m in self.active_monitors:
                q = m.query_text or (m.course_id if m.course_id else None)
                if q and q.strip() and q not in seen_queries:
                    seen_queries.add(q)
                    queries_to_search.append({
                        "course_name": q.strip(),
                        "unit_name": m.city or self.settings.unit_name,
                        "shift": m.shift,
                    })
        elif self.settings.enable_legacy_monitor:
            queries_to_search.append({
                "course_name": self.settings.course_name,
                "unit_name": self.settings.unit_name,
                "shift": self.settings.target_shift,
            })
        else:
            logger.info(f"[{self.worker_id}] Nenhum monitor ativo no Supabase para descoberta de novas ofertas.")
            return []

        for p_slug, p_instance in active_providers.items():
            for query_item in queries_to_search:
                try:
                    discovered = await p_instance.discover_offers(
                        course_name=query_item["course_name"],
                        unit_name=query_item["unit_name"],
                        shift=query_item.get("shift") or self.settings.target_shift,
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
            self.sync_monitors_from_supabase,
            "interval",
            minutes=2,
            id="worker_monitors_sync",
            replace_existing=True,
            next_run_time=datetime.now(),
        )

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
        logger.info(f"Agendador do Worker iniciado: sync=2m, checagem={check_interval}m, descoberta={discovery_interval}m")

    def stop_scheduler(self) -> None:
        """Stops background scheduling."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Agendador do Worker finalizado.")
