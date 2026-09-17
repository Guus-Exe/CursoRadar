"""Cryptographic single-use token handling for Telegram account linking with Supabase persistence."""

from datetime import datetime, timedelta, timezone
import os
import secrets
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from app.utils.logger import logger


def parse_iso_datetime(dt_val: Any) -> datetime:
    """Safely parses ISO timestamp into a timezone-aware UTC datetime."""
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val.astimezone(timezone.utc)
    if isinstance(dt_val, str):
        cleaned = dt_val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raise ValueError(f"Formato de data inválido: {dt_val}")


class TelegramLinkToken(BaseModel):
    """Temporary linking token."""

    token: str
    user_id: str
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_valid(self) -> bool:
        """Token is valid only if not expired and not previously used."""
        return self.used_at is None and datetime.now(timezone.utc) < parse_iso_datetime(self.expires_at)


class TelegramLinkedAccount(BaseModel):
    """User account linked with Telegram chat ID."""

    user_id: str
    telegram_chat_id: str
    telegram_username: Optional[str] = None
    telegram_first_name: Optional[str] = None
    linked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True


class TelegramLinkManager:
    """Manages secure token generation, validation, and account binding with Supabase persistence."""

    def __init__(
        self,
        token_ttl_minutes: int = 15,
        supabase_url: Optional[str] = None,
        supabase_service_role_key: Optional[str] = None,
        supabase_client: Optional[Any] = None,
    ):
        self.token_ttl_minutes = token_ttl_minutes
        self.supabase: Optional[Any] = None

        if supabase_client is not None:
            self.supabase = supabase_client
        elif supabase_url and supabase_service_role_key:
            try:
                from supabase import create_client
                self.supabase = create_client(supabase_url, supabase_service_role_key)
                logger.info("TelegramLinkManager inicializado com cliente Supabase.")
            except Exception as err:
                logger.error(f"Falha ao inicializar cliente Supabase: {err}")
                self.supabase = None

        # Fallback / In-memory storage (used for isolated unit tests or when Supabase is not configured)
        self._tokens: Dict[str, TelegramLinkToken] = {}
        self._accounts_by_user: Dict[str, TelegramLinkedAccount] = {}
        self._accounts_by_chat: Dict[str, TelegramLinkedAccount] = {}

    def generate_token(self, user_id: str) -> TelegramLinkToken:
        """Generates a cryptographically secure, temporary, single-use token."""
        token_str = secrets.token_urlsafe(32)
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(minutes=self.token_ttl_minutes)

        token_obj = TelegramLinkToken(
            token=token_str,
            user_id=user_id,
            expires_at=expires_at,
            created_at=now_utc,
        )

        if self.supabase:
            try:
                payload = {
                    "user_id": user_id,
                    "token": token_str,
                    "expires_at": expires_at.isoformat(),
                }
                self.supabase.table("telegram_link_tokens").insert(payload).execute()
                logger.info(f"Token de vinculação gerado no Supabase para user {user_id} (expira em {self.token_ttl_minutes}m).")
                return token_obj
            except Exception as err:
                logger.error(f"Erro ao salvar token de vinculação no Supabase: {err}")

        # In-memory storage
        self._tokens[token_str] = token_obj
        logger.info(f"Token de vinculação gerado em memória para user {user_id} (expira em {self.token_ttl_minutes}m).")
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
        chat_id_str = str(telegram_chat_id)
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()

        # ----------------------------------------------------
        # Supabase Execution Path (Atomic RPC)
        # ----------------------------------------------------
        if self.supabase:
            try:
                logger.info(f"Invocando RPC link_telegram_account no Supabase para token {clean_token[:8]}...")
                rpc_params = {
                    "p_token": clean_token,
                    "p_telegram_chat_id": chat_id_str,
                    "p_telegram_username": telegram_username,
                    "p_telegram_first_name": telegram_first_name,
                }
                res = self.supabase.rpc("link_telegram_account", rpc_params).execute()

                data = res.data
                if not data or not isinstance(data, dict):
                    logger.error(f"Resposta inesperada da RPC link_telegram_account: {data}")
                    return False, "❌ Link de conexão inválido.", None

                success = data.get("success", False)
                message = data.get("message", "❌ Link de conexão inválido.")

                if not success:
                    logger.warning(f"RPC link_telegram_account rejeitou vinculação ({data.get('error_code')}): {message}")
                    return False, message, None

                user_id = str(data["user_id"])
                linked_at = parse_iso_datetime(data.get("linked_at") or now_utc)

                account = TelegramLinkedAccount(
                    user_id=user_id,
                    telegram_chat_id=chat_id_str,
                    telegram_username=data.get("telegram_username") or telegram_username,
                    telegram_first_name=data.get("telegram_first_name") or telegram_first_name,
                    linked_at=linked_at,
                    active=True,
                )

                logger.info(
                    f"Telegram vinculado com sucesso via RPC atômica do Supabase! User {user_id} <-> Chat ID {chat_id_str} "
                    f"(@{telegram_username or 'sem_username'})"
                )
                return True, message, account

            except Exception as err:
                logger.error(f"Erro ao executar RPC link_telegram_account no Supabase: {err}")
                return False, "❌ Link de conexão inválido.", None

        # ----------------------------------------------------
        # In-Memory Fallback Path (for local testing & dev)
        # ----------------------------------------------------
        token_obj = self._tokens.get(clean_token)

        if not token_obj:
            logger.warning(f"Tentativa de vinculação com token inexistente: {clean_token[:8]}...")
            return False, "❌ Link de conexão inválido.", None

        if token_obj.used_at is not None:
            logger.warning(f"Tentativa de reutilização de token já consumido: {clean_token[:8]}...")
            return False, "⚠️ Este link já foi utilizado. Gere um novo link se precisar reconectar.", None

        expires_at = parse_iso_datetime(token_obj.expires_at)
        if now_utc >= expires_at:
            logger.warning(f"Tentativa de vinculação com token expirado: {clean_token[:8]}...")
            return False, "⚠️ Este link expirou. Gere um novo link no CursoRadar.", None

        # Mark consumed
        token_obj.used_at = now_utc

        # Handle controlled reconnection: remove chat if was on another user
        old_acc = self._accounts_by_chat.get(chat_id_str)
        if old_acc and old_acc.user_id != token_obj.user_id:
            self._accounts_by_user.pop(old_acc.user_id, None)

        account = TelegramLinkedAccount(
            user_id=token_obj.user_id,
            telegram_chat_id=chat_id_str,
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
            linked_at=now_utc,
            active=True,
        )
        self._accounts_by_user[token_obj.user_id] = account
        self._accounts_by_chat[chat_id_str] = account

        logger.info(
            f"Telegram vinculado com sucesso em memória! User {token_obj.user_id} <-> Chat ID {chat_id_str} "
            f"(@{telegram_username or 'sem_username'})"
        )
        return True, "✅ Telegram conectado com sucesso ao CursoRadar.", account

    def get_account_by_user(self, user_id: str) -> Optional[TelegramLinkedAccount]:
        """Retrieves linked telegram account for a user."""
        if self.supabase:
            try:
                res = (
                    self.supabase.table("telegram_accounts")
                    .select("*")
                    .eq("user_id", user_id)
                    .eq("active", True)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    return TelegramLinkedAccount(
                        user_id=row["user_id"],
                        telegram_chat_id=row["telegram_chat_id"],
                        telegram_username=row.get("telegram_username"),
                        telegram_first_name=row.get("telegram_first_name"),
                        linked_at=parse_iso_datetime(row.get("verified_at") or row.get("created_at")),
                        active=row.get("active", True),
                    )
                return None
            except Exception as err:
                logger.error(f"Erro ao buscar conta Telegram para user {user_id}: {err}")
                return None
        return self._accounts_by_user.get(user_id)

    def get_account_by_chat(self, chat_id: str) -> Optional[TelegramLinkedAccount]:
        """Retrieves linked account by telegram chat ID."""
        chat_id_str = str(chat_id)
        if self.supabase:
            try:
                res = (
                    self.supabase.table("telegram_accounts")
                    .select("*")
                    .eq("telegram_chat_id", chat_id_str)
                    .eq("active", True)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    return TelegramLinkedAccount(
                        user_id=row["user_id"],
                        telegram_chat_id=row["telegram_chat_id"],
                        telegram_username=row.get("telegram_username"),
                        telegram_first_name=row.get("telegram_first_name"),
                        linked_at=parse_iso_datetime(row.get("verified_at") or row.get("created_at")),
                        active=row.get("active", True),
                    )
                return None
            except Exception as err:
                logger.error(f"Erro ao buscar conta Telegram para chat {chat_id_str}: {err}")
                return None
        return self._accounts_by_chat.get(chat_id_str)

    def get_chat_id_by_user(self, user_id: str) -> Optional[str]:
        """Retrieves active telegram chat ID for a given user ID."""
        account = self.get_account_by_user(user_id)
        return account.telegram_chat_id if account and account.active else None

    def list_active_accounts(self) -> List[TelegramLinkedAccount]:
        """Lists all active linked Telegram accounts."""
        if self.supabase:
            try:
                res = (
                    self.supabase.table("telegram_accounts")
                    .select("*")
                    .eq("active", True)
                    .execute()
                )
                accounts: List[TelegramLinkedAccount] = []
                for row in (res.data or []):
                    accounts.append(
                        TelegramLinkedAccount(
                            user_id=row["user_id"],
                            telegram_chat_id=row["telegram_chat_id"],
                            telegram_username=row.get("telegram_username"),
                            telegram_first_name=row.get("telegram_first_name"),
                            linked_at=parse_iso_datetime(row.get("verified_at") or row.get("created_at")),
                            active=row.get("active", True),
                        )
                    )
                return accounts
            except Exception as err:
                logger.error(f"Erro ao listar contas ativas no Supabase: {err}")
                return []
        return [acc for acc in self._accounts_by_user.values() if acc.active]

    def unlink_account(self, user_id: str) -> bool:
        """Unlinks telegram account from user."""
        if self.supabase:
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                res = (
                    self.supabase.table("telegram_accounts")
                    .update({"active": False, "updated_at": now_iso})
                    .eq("user_id", user_id)
                    .execute()
                )
                return bool(res.data and len(res.data) > 0)
            except Exception as err:
                logger.error(f"Erro ao desvincular conta Telegram no Supabase para user {user_id}: {err}")
                return False

        account = self._accounts_by_user.pop(user_id, None)
        if account:
            self._accounts_by_chat.pop(account.telegram_chat_id, None)
            logger.info(f"Conta Telegram desvinculada para user {user_id}.")
            return True
        return False
