"""Telegram notification provider and bot command handler."""

import asyncio
from datetime import datetime
import inspect
from typing import Any, Callable, Coroutine, Optional
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from app.config import get_settings
from app.models import DiscoveredOffer, StateDiff
from app.notifications.base import NotificationProvider
from app.utils.logger import logger


from app.telegram_link import TelegramLinkManager


class TelegramProvider(NotificationProvider):
    """Notification provider and command interface via Telegram."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        link_manager: Optional[TelegramLinkManager] = None,
    ):
        self.settings = get_settings()
        self.bot_token = bot_token or self.settings.telegram_bot_token
        self.chat_id = chat_id or self.settings.telegram_chat_id
        self.link_manager = link_manager
        self._bot: Optional[Bot] = None
        self._app: Optional[Application] = None

        if self.bot_token:
            self._bot = Bot(token=self.bot_token)

    def is_configured(self) -> bool:
        """Checks whether bot token is configured."""
        return bool(self.bot_token)

    async def send_to_user(self, recipient_id: str, text: str) -> bool:
        """Sends raw text message to a specific user chat ID."""
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN ausente. Mensagem não enviada.")
            return False

        try:
            assert self._bot is not None
            await self._bot.send_message(
                chat_id=recipient_id,
                text=text,
                disable_web_page_preview=False,
            )
            logger.info(f"Mensagem enviada com sucesso pelo Telegram para chat {recipient_id}.")
            return True
        except Exception as err:
            logger.error(f"Erro ao enviar mensagem pelo Telegram para chat {recipient_id}: {err}")
            return False

    async def send_message(self, text: str) -> bool:
        """Sends raw text message to default chat ID."""
        if not self.chat_id:
            logger.warning("Telegram TELEGRAM_CHAT_ID default não configurado.")
            return False
        return await self.send_to_user(self.chat_id, text)

    async def send_offer_alert(self, diff: StateDiff, url: str) -> bool:
        """Sends formatted alert when course availability or status changes."""
        curr = diff.current_state
        prev = diff.previous_state

        prev_status = prev.status if prev else "Sem informações anteriores"
        curr_status = curr.status
        bolsa_str = "Disponível ✅" if curr.bolsa_disponivel else "Não disponível ❌"
        detected_time = diff.detected_at.strftime("%d/%m/%Y %H:%M:%S")

        changes_section = ""
        if diff.reasons:
            reasons_text = "\n".join(f"• {r}" for r in diff.reasons)
            changes_section = f"\n\n🔍 O que mudou:\n{reasons_text}"

        buttons_section = ""
        if curr.botoes:
            buttons_section = f"\n🔘 Botões disponíveis: {', '.join(curr.botoes)}"

        msg = (
            f"🚨 VAGA ENCONTRADA — CURSORADAR\n\n"
            f"Curso: {curr.curso}\n"
            f"Unidade: {curr.unidade}\n"
            f"Período: {curr.turno}\n\n"
            f"Status anterior:\n{prev_status}\n\n"
            f"Novo status:\n{curr_status}\n\n"
            f"🎓 Bolsa: {bolsa_str}\n"
            f"Detectado em:\n{detected_time}\n"
            f"{changes_section}"
            f"{buttons_section}\n\n"
            f"Link:\n{url}"
        )

        sent_any = False
        if self.link_manager:
            for acc in self.link_manager.list_active_accounts():
                if await self.send_to_user(acc.telegram_chat_id, msg):
                    sent_any = True

        if self.chat_id:
            if await self.send_to_user(self.chat_id, msg):
                sent_any = True

        return sent_any

    async def send_new_offer_alert(self, offer: DiscoveredOffer) -> bool:
        """Sends formatted alert when a new offer is discovered for the course."""
        detected_time = offer.descoberto_em.strftime("%d/%m/%Y %H:%M:%S")
        bolsa_str = "Disponível ✅" if offer.bolsa_disponivel else "A verificar / Indisponível"

        msg = (
            f"🆕 NOVA OFERTA ENCONTRADA\n\n"
            f"Curso: {offer.curso}\n"
            f"Unidade: {offer.unidade}\n"
            f"Período: {offer.turno}\n"
            f"Código da Oferta: {offer.codigo_oferta}\n"
            f"Horário: {offer.horario or 'A consultar'}\n"
            f"Data início: {offer.data_inicio or 'A consultar'}\n"
            f"🎓 Bolsa: {bolsa_str}\n"
            f"Detectado em: {detected_time}\n\n"
            f"Link:\n{offer.url}"
        )

        sent_any = False
        if self.link_manager:
            for acc in self.link_manager.list_active_accounts():
                if await self.send_to_user(acc.telegram_chat_id, msg):
                    sent_any = True

        if self.chat_id:
            if await self.send_to_user(self.chat_id, msg):
                sent_any = True

        return sent_any

    async def send_health_alert(self, consecutive_failures: int, details: Optional[str] = None) -> bool:
        """Sends warning message about repeated connection failures."""
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        details_text = f"\nÚltimo erro: {details}" if details else ""

        msg = (
            f"⚠️ Monitor Senac com problema\n\n"
            f"Não foi possível verificar o curso nas últimas {consecutive_failures} tentativas.\n"
            f"Horário: {now_str}"
            f"{details_text}\n\n"
            f"O monitor continuará tentando se recuperar automaticamente."
        )

        sent_any = False
        if self.link_manager:
            for acc in self.link_manager.list_active_accounts():
                if await self.send_to_user(acc.telegram_chat_id, msg):
                    sent_any = True

        if self.chat_id:
            if await self.send_to_user(self.chat_id, msg):
                sent_any = True

        return sent_any

    def create_application(
        self,
        status_callback: Callable[[], Coroutine[Any, Any, str]],
        check_callback: Callable[[], Coroutine[Any, Any, str]],
        link_callback: Callable[[], str],
        pause_callback: Callable[[], str],
        resume_callback: Callable[[], str],
    ) -> Optional[Application]:
        """Creates Telegram Bot Application with interactive commands."""
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN ausente. Bot de comandos interativo não inicializado.")
            return None

        app = Application.builder().token(self.bot_token).build()

        async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.message:
                return

            # Check if token argument was passed: /start <TOKEN>
            if context.args and len(context.args) > 0:
                token_arg = context.args[0].strip()
                chat = update.effective_chat
                user = update.effective_user

                if not self.link_manager:
                    await update.message.reply_text("❌ Sistema de vinculação temporariamente indisponível.")
                    return

                if chat:
                    success, message, account = self.link_manager.validate_and_consume(
                        token_str=token_arg,
                        telegram_chat_id=str(chat.id),
                        telegram_username=user.username if user else None,
                        telegram_first_name=user.first_name if user else None,
                    )
                    if success:
                        resp = (
                            f"{message}\n\n"
                            f"Olá, {user.first_name or 'usuário'}! Você receberá aqui instantaneamente os alertas das oportunidades que cadastrar no CursoRadar.\n\n"
                            f"Comandos úteis:\n"
                            f"/status - Ver resumo de verificações\n"
                            f"/check - Executar verificação manual imediata\n"
                            f"/link - Ver página oficial do curso monitorado"
                        )
                        await update.message.reply_text(resp)
                        return
                    else:
                        await update.message.reply_text(message)
                        return

            text = (
                "👋 Olá! Sou o Bot do CursoRadar.\n\n"
                "Para vincular sua conta e receber alertas de vagas e bolsas:\n"
                "1. Acesse seu painel web do CursoRadar\n"
                "2. Vá em Configurações > Telegram\n"
                "3. Clique em 'Conectar Telegram'\n\n"
                "Comandos disponíveis:\n"
                "/status - Mostra a última verificação e o estado atual\n"
                "/check - Executa uma verificação manual imediata\n"
                "/link - Retorna o link monitorado\n"
                "/pause - Pausa o monitoramento periódico\n"
                "/resume - Retoma o monitoramento periódico"
            )
            await update.message.reply_text(text)

        async def _execute_callback(cb: Any, chat_id: Optional[str] = None, arg: Optional[str] = None) -> Any:
            try:
                sig = inspect.signature(cb)
                num_params = len(sig.parameters)
                if num_params >= 2:
                    res = cb(chat_id, arg)
                elif num_params == 1:
                    res = cb(chat_id)
                else:
                    res = cb()
                if asyncio.iscoroutine(res):
                    return await res
                return res
            except Exception as err:
                logger.error(f"Erro ao executar callback do comando Telegram: {err}")
                return f"❌ Erro ao processar comando: {err}"

        async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message:
                chat_id = str(update.effective_chat.id) if update.effective_chat else None
                msg = await _execute_callback(status_callback, chat_id=chat_id)
                await update.message.reply_text(msg)

        async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message:
                chat_id = str(update.effective_chat.id) if update.effective_chat else None
                await update.message.reply_text("🔄 Executando verificação agora...")
                msg = await _execute_callback(check_callback, chat_id=chat_id)
                await update.message.reply_text(msg)

        async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message:
                chat_id = str(update.effective_chat.id) if update.effective_chat else None
                url = await _execute_callback(link_callback, chat_id=chat_id)
                if isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
                    await update.message.reply_text(f"🔗 Link monitorado:\n{url}")
                else:
                    await update.message.reply_text(str(url))

        async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message:
                chat_id = str(update.effective_chat.id) if update.effective_chat else None
                arg = context.args[0] if context.args and len(context.args) > 0 else None
                msg = await _execute_callback(pause_callback, chat_id=chat_id, arg=arg)
                await update.message.reply_text(msg)

        async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message:
                chat_id = str(update.effective_chat.id) if update.effective_chat else None
                arg = context.args[0] if context.args and len(context.args) > 0 else None
                msg = await _execute_callback(resume_callback, chat_id=chat_id, arg=arg)
                await update.message.reply_text(msg)

        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("help", cmd_start))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("check", cmd_check))
        app.add_handler(CommandHandler("link", cmd_link))
        app.add_handler(CommandHandler("pause", cmd_pause))
        app.add_handler(CommandHandler("resume", cmd_resume))

        self._app = app
        return app
