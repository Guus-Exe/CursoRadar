"""Cryptographic single-use token handling for Telegram account linking."""

from datetime import datetime, timedelta
import secrets
from typing import Dict, Optional, Tuple
from pydantic import BaseModel, Field
from app.utils.logger import logger


class TelegramLinkToken(BaseModel):
    """Temporary linking token."""

    token: str
    user_id: str
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def is_valid(self) -> bool:
        """Token is valid only if not expired and not previously used."""
        return self.used_at is None and datetime.now() < self.expires_at


class TelegramLinkedAccount(BaseModel):
    """User account linked with Telegram chat ID."""

    user_id: str
    telegram_chat_id: str
    telegram_username: Optional[str] = None
    telegram_first_name: Optional[str] = None
    linked_at: datetime = Field(default_factory=datetime.now)
    active: bool = True


class TelegramLinkManager:
    """Manages secure token generation, validation, and account binding."""

    def __init__(self, token_ttl_minutes: int = 15):
        self.token_ttl_minutes = token_ttl_minutes
        self._tokens: Dict[str, TelegramLinkToken] = {}
        self._accounts_by_user: Dict[str, TelegramLinkedAccount] = {}
        self._accounts_by_chat: Dict[str, TelegramLinkedAccount] = {}

    def generate_token(self, user_id: str) -> TelegramLinkToken:
        """Generates a cryptographically secure, temporary, single-use token."""
        # 32 bytes urlsafe token (43+ characters)
        token_str = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=self.token_ttl_minutes)

        token_obj = TelegramLinkToken(
            token=token_str,
            user_id=user_id,
            expires_at=expires_at,
        )
        self._tokens[token_str] = token_obj
        logger.info(f"Token de vinculação gerado para user {user_id} (expira em {self.token_ttl_minutes}m).")
        return token_obj

    def validate_and_consume(
        self,
        token_str: str,
        telegram_chat_id: str,
        telegram_username: Optional[str] = None,
        telegram_first_name: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[TelegramLinkedAccount]]:
        """Validates token, ensures single-use, and binds telegram_chat_id to user_id."""
        clean_token = token_str.strip()
        token_obj = self._tokens.get(clean_token)

        if not token_obj:
            logger.warning(f"Tentativa de vinculação com token inexistente: {clean_token[:8]}...")
            return False, "Token não encontrado ou inválido.", None

        if token_obj.used_at is not None:
            logger.warning(f"Tentativa de reutilização de token já consumido: {clean_token[:8]}...")
            return False, "Este link de vinculação já foi utilizado anteriormente.", None

        if datetime.now() >= token_obj.expires_at:
            logger.warning(f"Tentativa de vinculação com token expirado: {clean_token[:8]}...")
            return False, "Este link de vinculação expirou. Gere um novo link no painel.", None

        # Mark as consumed immediately to prevent race condition / replay
        token_obj.used_at = datetime.now()

        # Create or update linked account
        account = TelegramLinkedAccount(
            user_id=token_obj.user_id,
            telegram_chat_id=str(telegram_chat_id),
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
            linked_at=datetime.now(),
            active=True,
        )
        self._accounts_by_user[token_obj.user_id] = account
        self._accounts_by_chat[str(telegram_chat_id)] = account

        logger.info(
            f"Telegram vinculado com sucesso! User {token_obj.user_id} <-> Chat ID {telegram_chat_id} "
            f"(@{telegram_username or 'sem_username'})"
        )
        return True, "Conta vinculada com sucesso!", account

    def get_account_by_user(self, user_id: str) -> Optional[TelegramLinkedAccount]:
        """Retrieves linked telegram account for a user."""
        return self._accounts_by_user.get(user_id)

    def get_account_by_chat(self, chat_id: str) -> Optional[TelegramLinkedAccount]:
        """Retrieves linked account by telegram chat ID."""
        return self._accounts_by_chat.get(str(chat_id))

    def unlink_account(self, user_id: str) -> bool:
        """Unlinks telegram account from user."""
        account = self._accounts_by_user.pop(user_id, None)
        if account:
            self._accounts_by_chat.pop(account.telegram_chat_id, None)
            logger.info(f"Conta Telegram desvinculada para user {user_id}.")
            return True
        return False
