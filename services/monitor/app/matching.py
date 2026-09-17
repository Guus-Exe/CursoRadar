"""Matching Engine and Multi-User Alert Deduplication."""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field
from app.models import OfferState, StateDiff
from app.utils.logger import logger


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
    institution_id: str
    location_id: str
    course_id: str
    shift: Optional[str] = None  # None = any shift
    active: bool = True
    preferences: MonitorPreferences = Field(default_factory=MonitorPreferences)
    telegram_chat_id: Optional[str] = None


class OfferChangeEvent(BaseModel):
    """Event emitted when an offer changes state or a new offer is discovered."""

    offer_id: str
    institution_id: str
    location_id: str
    course_id: str
    shift: str
    change_type: str  # 'ENROLLMENT_OPEN', 'SCHOLARSHIP_OPEN', 'NEW_OFFER', 'DATES_CHANGED', 'STATUS_CHANGE'
    reasons: List[str] = Field(default_factory=list)
    previous_state: Optional[OfferState] = None
    current_state: OfferState
    detected_at: datetime = Field(default_factory=datetime.now)
    url: str


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

    def __init__(self, existing_fingerprints: Optional[Set[str]] = None):
        self.seen_fingerprints: Set[str] = set(existing_fingerprints or [])

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
            if event.current_state.bolsa_disponivel and prefs.notify_scholarship:
                return True
            if event.current_state.inscricao_disponivel and (prefs.notify_enrollment_open or prefs.notify_paid):
                return True
            return True

        return True

    def format_notification(self, event: OfferChangeEvent) -> str:
        """Formats alert message compatible with Telegram."""
        curr = event.current_state
        prev = event.previous_state

        header = "🚨 VAGA ENCONTRADA — SENAC"
        if event.change_type == "NEW_OFFER":
            header = "🆕 NOVA TURMA / OFERTA ENCONTRADA"
        elif event.change_type == "SCHOLARSHIP_OPEN":
            header = "🎓 BOLSA DE ESTUDO DISPONÍVEL"

        prev_status = prev.status if prev else "Sem registro anterior"
        bolsa_str = "Disponível ✅" if curr.bolsa_disponivel else "Não disponível ❌"
        inscricao_str = "Aberta ✅" if curr.inscricao_disponivel else "Indisponível ❌"
        detected_time = event.detected_at.strftime("%d/%m/%Y às %H:%M")

        changes_section = ""
        if event.reasons:
            reasons_text = "\n".join(f"• {r}" for r in event.reasons)
            changes_section = f"\n\n🔍 O que mudou:\n{reasons_text}"

        buttons_section = ""
        if curr.botoes:
            buttons_section = f"\n🔘 Botões disponíveis: {', '.join(curr.botoes)}"

        msg = (
            f"{header}\n\n"
            f"Curso: {curr.curso}\n"
            f"📍 Unidade: {curr.unidade}\n"
            f"🌙 Período: {curr.turno}\n\n"
            f"Status anterior:\n{prev_status}\n\n"
            f"Novo status:\n{curr.status}\n\n"
            f"Inscrição: {inscricao_str}\n"
            f"🎓 Bolsa: {bolsa_str}\n"
            f"Detectado em: {detected_time}"
            f"{changes_section}"
            f"{buttons_section}\n\n"
            f"Link oficial:\n{event.url}"
        )
        return msg

    def match(
        self,
        event: OfferChangeEvent,
        monitors: List[UserMonitor],
    ) -> List[MatchResult]:
        """Matches an event against candidate monitors and returns deduplicated MatchResults."""
        results: List[MatchResult] = []
        state_hash = event.current_state.compute_alert_hash()

        for mon in monitors:
            if not mon.active:
                continue

            # Check entity relations
            if mon.institution_id != event.institution_id:
                continue
            if mon.location_id != event.location_id:
                continue
            if mon.course_id != event.course_id:
                continue

            # Check shift
            if not self.is_shift_compatible(mon.shift, event.shift):
                continue

            # Check user notification preferences
            if not self.matches_preferences(event, mon.preferences):
                continue

            # Check if user has active telegram connection
            if not mon.telegram_chat_id:
                logger.debug(f"Monitor {mon.id} (user {mon.user_id}) compatível mas sem Telegram configurado.")
                continue

            # Calculate fingerprint for deduplication
            fp = compute_alert_fingerprint(
                user_id=mon.user_id,
                monitor_id=mon.id,
                offer_id=event.offer_id,
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
