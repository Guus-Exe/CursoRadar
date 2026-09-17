"""WhatsApp notification provider ready for future integration."""

from typing import Optional
import httpx
from app.config import get_settings
from app.models import DiscoveredOffer, StateDiff
from app.notifications.base import NotificationProvider
from app.utils.logger import logger


class WhatsAppProvider(NotificationProvider):
    """Notification provider prepared for WhatsApp API (Evolution API, Twilio, Z-API, Meta Cloud API)."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_token: Optional[str] = None,
        phone_number: Optional[str] = None,
    ):
        self.settings = get_settings()
        self.api_url = api_url or self.settings.whatsapp_api_url
        self.api_token = api_token or self.settings.whatsapp_api_token
        self.phone_number = phone_number or self.settings.whatsapp_phone_number
        self.enabled = self.settings.whatsapp_enabled

    def is_configured(self) -> bool:
        """Verifies whether WhatsApp provider parameters are supplied."""
        return bool(self.enabled and self.api_url and self.api_token and self.phone_number)

    async def send_message(self, text: str) -> bool:
        """Sends message via configured WhatsApp gateway."""
        if not self.is_configured():
            logger.debug("WhatsAppProvider não habilitado ou parâmetros incompletos no .env. Ignorando envio.")
            return False

        logger.info(f"Enviando notificação WhatsApp para {self.phone_number}...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "number": self.phone_number,
                    "text": text,
                }
                headers = {
                    "Authorization": f"Bearer {self.api_token}",
                    "apikey": self.api_token,
                    "Content-Type": "application/json",
                }
                response = await client.post(
                    self.api_url,  # type: ignore
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                logger.info("Notificação enviada com sucesso pelo WhatsApp.")
                return True
        except Exception as err:
            logger.error(f"Erro ao enviar notificação WhatsApp: {err}")
            return False

    async def send_offer_alert(self, diff: StateDiff, url: str) -> bool:
        """Formats and sends offer alert to WhatsApp."""
        curr = diff.current_state
        prev = diff.previous_state
        prev_status = prev.status if prev else "Sem informações anteriores"
        bolsa_str = "Disponível ✅" if curr.bolsa_disponivel else "Não disponível ❌"
        detected_time = diff.detected_at.strftime("%d/%m/%Y %H:%M:%S")

        changes_section = ""
        if diff.reasons:
            reasons_text = "\n".join(f"• {r}" for r in diff.reasons)
            changes_section = f"\n\n*O que mudou:*\n{reasons_text}"

        msg = (
            f"🚨 *VAGA ENCONTRADA — SENAC*\n\n"
            f"*Curso:* {curr.curso}\n"
            f"*Unidade:* {curr.unidade}\n"
            f"*Período:* {curr.turno}\n\n"
            f"*Status anterior:*\n{prev_status}\n\n"
            f"*Novo status:*\n{curr.status}\n\n"
            f"🎓 *Bolsa:* {bolsa_str}\n"
            f"*Detectado em:* {detected_time}\n"
            f"{changes_section}\n\n"
            f"*Link:*\n{url}"
        )

        return await self.send_message(msg)

    async def send_new_offer_alert(self, offer: DiscoveredOffer) -> bool:
        """Formats and sends new offer alert to WhatsApp."""
        detected_time = offer.descoberto_em.strftime("%d/%m/%Y %H:%M:%S")
        msg = (
            f"🆕 *NOVA OFERTA ENCONTRADA*\n\n"
            f"*Curso:* {offer.curso}\n"
            f"*Unidade:* {offer.unidade}\n"
            f"*Período:* {offer.turno}\n"
            f"*Horário:* {offer.horario or 'A consultar'}\n"
            f"*Detectado em:* {detected_time}\n\n"
            f"*Link:*\n{offer.url}"
        )
        return await self.send_message(msg)

    async def send_health_alert(self, consecutive_failures: int, details: Optional[str] = None) -> bool:
        """Formats and sends health warning alert to WhatsApp."""
        msg = (
            f"⚠️ *Monitor Senac com problema*\n\n"
            f"Não foi possível verificar o curso nas últimas {consecutive_failures} tentativas.\n"
            f"Detalhes: {details or 'Falha de conexão'}"
        )
        return await self.send_message(msg)
