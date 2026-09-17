"""Matching Engine and Multi-User Alert Deduplication."""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional, Set
import unicodedata
from pydantic import BaseModel, Field
from app.models import OfferState, StateDiff
from app.utils.logger import logger


def normalize_text(text: Optional[str]) -> str:
    """Normalizes string removing accents and converting to lowercase for robust matching."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return without_accents.lower().strip()


class MonitorPreferences(BaseModel):
    """User preferences for alert triggers."""

    notify_scholarship: bool = True
    notify_paid: bool = True
    notify_enrollment_open: bool = True
    notify_new_offer: bool = True
    notify_new_class: bool = True
    notify_date_changes: bool = False


class UserMonitor(BaseModel):
    """Representation of an active user monitor."""

    id: str
    user_id: str
    institution_id: Optional[str] = None
    location_id: Optional[str] = None
    course_id: Optional[str] = None
    shift: Optional[str] = None  # None = any shift
    active: bool = True
    preferences: MonitorPreferences = Field(default_factory=MonitorPreferences)
    telegram_chat_id: Optional[str] = None

    # Multi-provider extensions
    all_providers: bool = False
    provider_slugs: List[str] = Field(default_factory=list)
    provider_ids: List[str] = Field(default_factory=list)
    query_text: Optional[str] = None
    city: Optional[str] = None
    state: str = "SP"
    modality: str = "all"
    opportunity_type: str = "all"


class OfferChangeEvent(BaseModel):
    """Event emitted when an offer changes state or a new offer is discovered."""

    offer_id: str
    institution_id: Optional[str] = None
    location_id: Optional[str] = None
    course_id: Optional[str] = None
    shift: str = ""
    change_type: str = "STATUS_CHANGE"  # 'ENROLLMENT_OPEN', 'SCHOLARSHIP_OPEN', 'NEW_OFFER', 'DATES_CHANGED', 'STATUS_CHANGE'
    reasons: List[str] = Field(default_factory=list)
    previous_state: Optional[OfferState] = None
    current_state: OfferState
    detected_at: datetime = Field(default_factory=datetime.now)
    url: str = ""

    # Multi-provider fields
    provider_slug: str = "senac_sp"
    provider_id: Optional[str] = None
    external_id: Optional[str] = None
    fingerprint: Optional[str] = None
    title: Optional[str] = None
    institution_name: Optional[str] = None
    city: Optional[str] = None
    modality: str = "presencial"
    is_free: bool = False
    has_scholarship: Optional[bool] = None
    bolsa_disponivel: Optional[bool] = None
    inscricao_disponivel: Optional[bool] = None

    @property
    def effective_title(self) -> str:
        return self.title or (self.current_state.curso if self.current_state else "")

    @property
    def effective_institution_name(self) -> str:
        return self.institution_name or "Senac São Paulo"

    @property
    def effective_city(self) -> str:
        return self.city or (self.current_state.unidade if self.current_state else "")

    @property
    def effective_shift(self) -> str:
        return self.shift or (self.current_state.turno if self.current_state else "")

    @property
    def effective_bolsa_disponivel(self) -> bool:
        if self.bolsa_disponivel is not None:
            return self.bolsa_disponivel
        return self.current_state.bolsa_disponivel if self.current_state else False

    @property
    def effective_inscricao_disponivel(self) -> bool:
        if self.inscricao_disponivel is not None:
            return self.inscricao_disponivel
        return self.current_state.inscricao_disponivel if self.current_state else False

    @property
    def effective_has_scholarship(self) -> bool:
        if self.has_scholarship is not None:
            return self.has_scholarship
        return self.effective_bolsa_disponivel


class MatchResult(BaseModel):
    """Result of matching an offer change against a user monitor."""

    user_id: str
    monitor_id: str
    offer_id: str
    telegram_chat_id: str
    change_type: str
    fingerprint: str
    message: str


def compute_alert_fingerprint(
    user_id: str,
    monitor_id: str,
    offer_id: str,
    change_type: str,
    state_hash: str,
) -> str:
    """Computes a deterministic SHA256 fingerprint for idempotency and deduplication."""
    payload = f"{user_id}:{monitor_id}:{offer_id}:{change_type}:{state_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class MatchingEngine:
    """Matches offer change events against active monitors and generates deduplicated alerts."""

    def __init__(
        self,
        existing_fingerprints: Optional[Set[str]] = None,
        registry: Optional[Any] = None,
    ):
        self.seen_fingerprints: Set[str] = set(existing_fingerprints or [])
        self.registry = registry

    def is_provider_enabled(self, provider_slug: str) -> bool:
        """Checks if provider is registered and enabled."""
        from app.providers.registry import get_provider_registry
        reg = self.registry or get_provider_registry()
        provider = reg.get(provider_slug)
        if provider is None:
            return False
        return getattr(provider, "enabled", True)

    def is_shift_compatible(self, monitor_shift: Optional[str], offer_shift: str) -> bool:
        """Checks whether monitor shift matches offer shift."""
        if not monitor_shift or not monitor_shift.strip():
            return True
        m_shift = monitor_shift.strip().lower()
        o_shift = offer_shift.strip().lower()
        if m_shift in o_shift or o_shift in m_shift:
            return True
        if m_shift == "qualquer":
            return True
        return False

    def matches_preferences(self, event: OfferChangeEvent, prefs: MonitorPreferences) -> bool:
        """Determines if the event satisfies user's specific notification preferences."""
        ctype = event.change_type.upper()

        if ctype == "SCHOLARSHIP_OPEN":
            return prefs.notify_scholarship

        if ctype == "ENROLLMENT_OPEN":
            return prefs.notify_enrollment_open or prefs.notify_paid

        if ctype == "NEW_OFFER":
            return prefs.notify_new_offer or prefs.notify_new_class

        if ctype == "DATES_CHANGED":
            return prefs.notify_date_changes

        if ctype == "STATUS_CHANGE":
            # Actionable status: check if bolsa or regular
            if event.effective_bolsa_disponivel and prefs.notify_scholarship:
                return True
            if event.effective_inscricao_disponivel and (prefs.notify_enrollment_open or prefs.notify_paid):
                return True
            return True

        return True

    def format_notification(self, event: OfferChangeEvent) -> str:
        """Formats alert message compatible with Telegram."""
        curr = event.current_state
        prev = event.previous_state
        inst_name = event.effective_institution_name

        header = f"🚨 VAGA ENCONTRADA — {inst_name.upper()}"
        if event.change_type == "NEW_OFFER":
            header = f"🆕 NOVA TURMA / OFERTA ENCONTRADA — {inst_name.upper()}"
        elif event.change_type == "SCHOLARSHIP_OPEN":
            header = f"🎓 BOLSA DE ESTUDO DISPONÍVEL — {inst_name.upper()}"

        prev_status = prev.status if prev else "Sem registro anterior"
        bolsa_str = "Disponível ✅" if event.effective_bolsa_disponivel else "Não disponível ❌"
        inscricao_str = "Aberta ✅" if event.effective_inscricao_disponivel else "Indisponível ❌"
        detected_time = event.detected_at.strftime("%d/%m/%Y às %H:%M")

        changes_section = ""
        if event.reasons:
            reasons_text = "\n".join(f"• {r}" for r in event.reasons)
            changes_section = f"\n\n🔍 O que mudou:\n{reasons_text}"

        buttons_section = ""
        if curr and curr.botoes:
            buttons_section = f"\n🔘 Botões disponíveis: {', '.join(curr.botoes)}"

        city_or_unit = event.effective_city
        modality_str = (event.modality or "presencial").capitalize()
        shift_str = event.effective_shift or "Não informado"
        title_str = event.effective_title
        url_str = event.url or (curr.url if curr else "")

        msg = (
            f"{header}\n\n"
            f"Curso: {title_str}\n"
            f"📍 Unidade: {city_or_unit}\n"
            f"🌐 Modalidade: {modality_str}\n"
            f"🌙 Período: {shift_str}\n\n"
            f"Status anterior:\n{prev_status}\n\n"
            f"Novo status:\n{curr.status if curr else event.change_type}\n\n"
            f"Inscrição: {inscricao_str}\n"
            f"🎓 Bolsa: {bolsa_str}\n"
            f"Detectado em: {detected_time}"
            f"{changes_section}"
            f"{buttons_section}\n\n"
            f"Link oficial:\n{url_str}"
        )
        return msg

    def match(
        self,
        event: OfferChangeEvent,
        monitors: List[UserMonitor],
    ) -> List[MatchResult]:
        """Matches an event against candidate monitors and returns deduplicated MatchResults."""
        results: List[MatchResult] = []
        state_hash = event.current_state.compute_alert_hash() if event.current_state else "hash"

        # Check if event provider is enabled
        if not self.is_provider_enabled(event.provider_slug):
            logger.debug(f"Provider {event.provider_slug} desabilitado ou inexistente.")
            return results

        event_modality = (event.modality or "presencial").lower().strip()
        if event.external_id:
            offer_ref = f"{event.provider_slug}:{event.external_id}"
        elif event.fingerprint:
            offer_ref = event.fingerprint
        else:
            offer_ref = f"{event.provider_slug}:{event.offer_id}"

        for mon in monitors:
            if not mon.active:
                continue

            # 1. Provider match
            if mon.all_providers:
                pass  # Accepted because event provider is enabled
            elif mon.provider_slugs or mon.provider_ids:
                slug_match = event.provider_slug in mon.provider_slugs
                id_match = bool(event.provider_id and event.provider_id in mon.provider_ids)
                if not (slug_match or id_match):
                    continue
            else:
                # Legacy monitor: check institution_id
                if mon.institution_id and event.institution_id:
                    if mon.institution_id != event.institution_id:
                        continue

            # 2. Query text / course match
            if mon.query_text and mon.query_text.strip():
                q_norm = normalize_text(mon.query_text)
                t_norm = normalize_text(event.effective_title)
                q_words = q_norm.split()
                if not all(w in t_norm for w in q_words):
                    continue
            elif mon.course_id and event.course_id:
                if mon.course_id != event.course_id:
                    continue

            # 3. Location & Modality match
            if mon.modality and mon.modality.lower().strip() != "all":
                if mon.modality.lower().strip() != event_modality:
                    continue

            # Online offers bypass city check
            if event_modality != "online":
                if mon.city and mon.city.strip():
                    mon_city = normalize_text(mon.city)
                    ev_city = normalize_text(event.effective_city)
                    if mon_city not in ev_city and ev_city not in mon_city:
                        continue
                elif mon.location_id and event.location_id:
                    if mon.location_id != event.location_id:
                        continue

            # 4. Opportunity type match
            op_type = (mon.opportunity_type or "all").lower().strip()
            if op_type == "bolsa":
                if not (event.effective_has_scholarship and event.effective_bolsa_disponivel):
                    continue
            elif op_type == "gratuito":
                if not event.is_free:
                    continue
            elif op_type == "pago":
                if not event.effective_inscricao_disponivel or event.is_free:
                    continue

            # 5. Check shift
            if not self.is_shift_compatible(mon.shift, event.effective_shift):
                continue

            # 6. Check user notification preferences
            if not self.matches_preferences(event, mon.preferences):
                continue

            # 7. Check if user has active telegram connection
            if not mon.telegram_chat_id:
                logger.debug(f"Monitor {mon.id} (user {mon.user_id}) compatível mas sem Telegram configurado.")
                continue

            # 8. Deduplication fingerprint (using external_id or fingerprint)
            fp = compute_alert_fingerprint(
                user_id=mon.user_id,
                monitor_id=mon.id,
                offer_id=offer_ref,
                change_type=event.change_type,
                state_hash=state_hash,
            )

            if fp in self.seen_fingerprints:
                logger.debug(f"Alerta descartado por deduplicação (fingerprint já processado para user {mon.user_id}).")
                continue

            # Record fingerprint
            self.seen_fingerprints.add(fp)

            msg = self.format_notification(event)
            results.append(
                MatchResult(
                    user_id=mon.user_id,
                    monitor_id=mon.id,
                    offer_id=event.offer_id,
                    telegram_chat_id=mon.telegram_chat_id,
                    change_type=event.change_type,
                    fingerprint=fp,
                    message=msg,
                )
            )

        logger.info(f"Matching concluído para oferta {event.offer_id}: {len(results)} alertas gerados de {len(monitors)} monitores.")
        return results
