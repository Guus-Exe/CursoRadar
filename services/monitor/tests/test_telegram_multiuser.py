"""Tests for Telegram multi-user account linking, token security, and messaging."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.notifications.telegram import TelegramProvider
from app.telegram_link import TelegramLinkManager, TelegramLinkToken


def test_valid_token_linking():
    """Validates successful linking of a Telegram account to a user ID with valid token."""
    manager = TelegramLinkManager(token_ttl_minutes=15)
    user_id = "11111111-2222-3333-4444-555555555555"

    token = manager.generate_token(user_id)
    assert token.is_valid is True

    success, message, account = manager.validate_and_consume(
        token_str=token.token,
        telegram_chat_id="12345678",
        telegram_username="student_user",
        telegram_first_name="Estudante",
    )

    assert success is True
    assert message == "✅ Telegram conectado com sucesso ao CursoRadar."
    assert account is not None
    assert account.user_id == user_id
    assert account.telegram_chat_id == "12345678"
    assert account.telegram_username == "student_user"
    assert account.telegram_first_name == "Estudante"

    # Verify lookup
    assert manager.get_chat_id_by_user(user_id) == "12345678"
    acc = manager.get_account_by_chat("12345678")
    assert acc is not None and acc.user_id == user_id


def test_nonexistent_token():
    """Rejects arbitrary / fake / nonexistent tokens."""
    manager = TelegramLinkManager()
    ok, message, account = manager.validate_and_consume("fake_non_existent_token_xyz", "12345678")
    assert ok is False
    assert message == "❌ Link de conexão inválido."
    assert account is None


def test_expired_token():
    """Rejects expired tokens."""
    manager = TelegramLinkManager(token_ttl_minutes=15)
    token = manager.generate_token("user-expired")

    # Set expiration in the past
    token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    ok, message, account = manager.validate_and_consume(token.token, "12345678")
    assert ok is False
    assert message == "⚠️ Este link expirou. Gere um novo link no CursoRadar."
    assert account is None


def test_already_used_token_and_single_use():
    """Ensures a token cannot be reused after first consumption."""
    manager = TelegramLinkManager(token_ttl_minutes=15)
    token = manager.generate_token("user-single-use")

    # First consumption: success
    ok1, msg1, acc1 = manager.validate_and_consume(token.token, "chat-100")
    assert ok1 is True
    assert msg1 == "✅ Telegram conectado com sucesso ao CursoRadar."

    # Second consumption attempt: must be rejected as already used
    ok2, msg2, acc2 = manager.validate_and_consume(token.token, "chat-100")
    assert ok2 is False
    assert msg2 == "⚠️ Este link já foi utilizado. Gere um novo link se precisar reconectar."
    assert acc2 is None


def test_attempt_to_reuse_token_by_another_party():
    """Security: prevents another party/attacker from using an already consumed token."""
    manager = TelegramLinkManager(token_ttl_minutes=15)
    token = manager.generate_token("legit-user")

    # Legit user binds
    ok1, _, _ = manager.validate_and_consume(token.token, "legit-chat-id")
    assert ok1 is True

    # Attacker tries to consume the same token
    ok2, msg2, acc2 = manager.validate_and_consume(token.token, "attacker-chat-id")
    assert ok2 is False
    assert msg2 == "⚠️ Este link já foi utilizado. Gere um novo link se precisar reconectar."
    assert acc2 is None


def test_telegram_chat_id_binding_and_unlinking():
    """Validates binding persistence and clean unlinking."""
    manager = TelegramLinkManager()
    user_id = "user-bind-test"
    token = manager.generate_token(user_id)
    manager.validate_and_consume(token.token, "chat-999")

    assert manager.get_chat_id_by_user(user_id) == "chat-999"
    assert manager.get_account_by_user(user_id) is not None

    unlinked = manager.unlink_account(user_id)
    assert unlinked is True
    assert manager.get_chat_id_by_user(user_id) is None
    assert manager.get_account_by_user(user_id) is None
    assert manager.get_account_by_chat("chat-999") is None


def test_controlled_reconnection():
    """Handles controlled reconnection when user generates a new link token."""
    manager = TelegramLinkManager()
    user_id = "user-reconnect"

    # 1. First connection with Chat A
    token1 = manager.generate_token(user_id)
    ok1, _, _ = manager.validate_and_consume(token1.token, "chat-A")
    assert ok1 is True
    assert manager.get_chat_id_by_user(user_id) == "chat-A"

    # 2. Reconnection with Chat B (e.g. user changed Telegram account)
    token2 = manager.generate_token(user_id)
    ok2, _, _ = manager.validate_and_consume(token2.token, "chat-B")
    assert ok2 is True
    assert manager.get_chat_id_by_user(user_id) == "chat-B"
    assert manager.get_account_by_chat("chat-B").user_id == user_id


def test_two_different_users_isolated():
    """Validates that two distinct users are linked to distinct chat IDs without collision."""
    manager = TelegramLinkManager()
    user1 = "user-alpha"
    user2 = "user-beta"

    t1 = manager.generate_token(user1)
    t2 = manager.generate_token(user2)

    ok1, _, _ = manager.validate_and_consume(t1.token, "chat-alpha")
    ok2, _, _ = manager.validate_and_consume(t2.token, "chat-beta")

    assert ok1 is True and ok2 is True
    assert manager.get_chat_id_by_user(user1) == "chat-alpha"
    assert manager.get_chat_id_by_user(user2) == "chat-beta"

    active_accounts = manager.list_active_accounts()
    assert len(active_accounts) == 2


@pytest.mark.asyncio
async def test_cmd_start_no_args():
    """Validates /start without arguments returns welcome instructions."""
    manager = TelegramLinkManager()
    provider = TelegramProvider(bot_token="123456789:MOCK_TOKEN", link_manager=manager)

    # Mock Telegram Update and Context
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []

    app = provider.create_application(
        status_callback=AsyncMock(return_value="status"),
        check_callback=AsyncMock(return_value="check"),
        link_callback=lambda: "http://example.com",
        pause_callback=lambda: "paused",
        resume_callback=lambda: "resumed",
    )

    # Retrieve cmd_start handler from registered handlers
    start_handler = None
    for handler in app.handlers[0]:
        if hasattr(handler, "commands") and "start" in handler.commands:
            start_handler = handler
            break

    assert start_handler is not None
    await start_handler.callback(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "👋 Olá! Sou o Bot do CursoRadar." in call_text
    assert "/status" in call_text


@pytest.mark.asyncio
async def test_cmd_start_with_valid_and_invalid_tokens():
    """Validates /start <token> for valid and invalid tokens."""
    manager = TelegramLinkManager()
    provider = TelegramProvider(bot_token="123456789:MOCK_TOKEN", link_manager=manager)
    token = manager.generate_token("user-start-test")

    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock(id=555444333)
    update.effective_user = MagicMock(first_name="Carlos", username="carlos_dev")

    context = MagicMock()
    context.args = [token.token]

    app = provider.create_application(
        status_callback=AsyncMock(return_value="status"),
        check_callback=AsyncMock(return_value="check"),
        link_callback=lambda: "http://example.com",
        pause_callback=lambda: "paused",
        resume_callback=lambda: "resumed",
    )

    start_handler = next(h for h in app.handlers[0] if hasattr(h, "commands") and "start" in h.commands)

    # 1. Valid token
    await start_handler.callback(update, context)
    update.message.reply_text.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "✅ Telegram conectado com sucesso ao CursoRadar." in reply

    # 2. Reusing token (already consumed)
    update.message.reply_text.reset_mock()
    await start_handler.callback(update, context)
    update.message.reply_text.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "⚠️ Este link já foi utilizado. Gere um novo link se precisar reconectar." in reply

    # 3. Invalid token
    context.args = ["completely_fake_token"]
    update.message.reply_text.reset_mock()
    await start_handler.callback(update, context)
    update.message.reply_text.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "❌ Link de conexão inválido." in reply


def test_supabase_rpc_success():
    """Validates successful linking via Supabase RPC."""
    mock_supabase = MagicMock()
    manager = TelegramLinkManager(supabase_client=mock_supabase)

    rpc_mock = MagicMock()
    mock_supabase.rpc.return_value = rpc_mock
    rpc_mock.execute.return_value = MagicMock(
        data={
            "success": True,
            "message": "✅ Telegram conectado com sucesso ao CursoRadar.",
            "user_id": "user-uuid-1234",
            "telegram_chat_id": "999888777",
            "telegram_username": "mock_user",
            "telegram_first_name": "Mock",
            "linked_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    ok, msg, account = manager.validate_and_consume(
        token_str="valid-token-rpc",
        telegram_chat_id="999888777",
        telegram_username="mock_user",
        telegram_first_name="Mock",
    )

    assert ok is True
    assert msg == "✅ Telegram conectado com sucesso ao CursoRadar."
    assert account is not None
    assert account.user_id == "user-uuid-1234"
    assert account.telegram_chat_id == "999888777"
    mock_supabase.rpc.assert_called_once_with(
        "link_telegram_account",
        {
            "p_token": "valid-token-rpc",
            "p_telegram_chat_id": "999888777",
            "p_telegram_username": "mock_user",
            "p_telegram_first_name": "Mock",
        },
    )


def test_supabase_rpc_invalid_token():
    """Validates handling of invalid token rejection from RPC."""
    mock_supabase = MagicMock()
    manager = TelegramLinkManager(supabase_client=mock_supabase)

    rpc_mock = MagicMock()
    mock_supabase.rpc.return_value = rpc_mock
    rpc_mock.execute.return_value = MagicMock(
        data={
            "success": False,
            "error_code": "TOKEN_NOT_FOUND",
            "message": "❌ Link de conexão inválido.",
        }
    )

    ok, msg, account = manager.validate_and_consume("fake-token", "12345")
    assert ok is False
    assert msg == "❌ Link de conexão inválido."
    assert account is None


def test_supabase_rpc_expired_token():
    """Validates handling of expired token rejection from RPC."""
    mock_supabase = MagicMock()
    manager = TelegramLinkManager(supabase_client=mock_supabase)

    rpc_mock = MagicMock()
    mock_supabase.rpc.return_value = rpc_mock
    rpc_mock.execute.return_value = MagicMock(
        data={
            "success": False,
            "error_code": "TOKEN_EXPIRED",
            "message": "⚠️ Este link expirou. Gere um novo link no CursoRadar.",
        }
    )

    ok, msg, account = manager.validate_and_consume("expired-token", "12345")
    assert ok is False
    assert msg == "⚠️ Este link expirou. Gere um novo link no CursoRadar."
    assert account is None


def test_supabase_rpc_already_used_token():
    """Validates handling of already used token rejection from RPC."""
    mock_supabase = MagicMock()
    manager = TelegramLinkManager(supabase_client=mock_supabase)

    rpc_mock = MagicMock()
    mock_supabase.rpc.return_value = rpc_mock
    rpc_mock.execute.return_value = MagicMock(
        data={
            "success": False,
            "error_code": "TOKEN_ALREADY_USED",
            "message": "⚠️ Este link já foi utilizado. Gere um novo link se precisar reconectar.",
        }
    )

    ok, msg, account = manager.validate_and_consume("used-token", "12345")
    assert ok is False
    assert msg == "⚠️ Este link já foi utilizado. Gere um novo link se precisar reconectar."
    assert account is None


def test_concurrency_race_condition():
    """Validates that concurrent consumption allows only one winner."""
    mock_supabase = MagicMock()
    manager = TelegramLinkManager(supabase_client=mock_supabase)

    # First call succeeds, second call gets already used
    rpc_mock_1 = MagicMock()
    rpc_mock_1.execute.return_value = MagicMock(
        data={
            "success": True,
            "message": "✅ Telegram conectado com sucesso ao CursoRadar.",
            "user_id": "winner-user",
            "telegram_chat_id": "111",
        }
    )
    rpc_mock_2 = MagicMock()
    rpc_mock_2.execute.return_value = MagicMock(
        data={
            "success": False,
            "error_code": "TOKEN_ALREADY_USED",
            "message": "⚠️ Este link já foi utilizado. Gere um novo link se precisar reconectar.",
        }
    )

    mock_supabase.rpc.side_effect = [rpc_mock_1, rpc_mock_2]

    # Worker 1 consumes token
    ok1, msg1, acc1 = manager.validate_and_consume("race-token", "111")
    assert ok1 is True
    assert acc1 is not None and acc1.user_id == "winner-user"

    # Worker 2 attempts concurrent consumption on the locked/consumed row
    ok2, msg2, acc2 = manager.validate_and_consume("race-token", "222")
    assert ok2 is False
    assert msg2 == "⚠️ Este link já foi utilizado. Gere um novo link se precisar reconectar."
    assert acc2 is None


def test_simulated_failure_does_not_consume_token():
    """Validates that if an exception occurs during the database transaction, the operation fails safely."""
    mock_supabase = MagicMock()
    manager = TelegramLinkManager(supabase_client=mock_supabase)

    # Simulate database transaction failure (e.g. connection drop / DB exception)
    rpc_mock = MagicMock()
    mock_supabase.rpc.return_value = rpc_mock
    rpc_mock.execute.side_effect = RuntimeError("Database connection aborted during transaction")

    ok, msg, account = manager.validate_and_consume("unstable-token", "999")
    assert ok is False
    assert msg == "❌ Link de conexão inválido."
    assert account is None


def test_chat_id_collision_transfer():
    """Validates that when user 2 binds a chat ID previously held by user 1, it transfers cleanly."""
    manager = TelegramLinkManager()
    user1 = "user-previous-owner"
    user2 = "user-new-owner"
    chat_id = "shared-telegram-chat"

    # User 1 claims chat
    t1 = manager.generate_token(user1)
    ok1, _, _ = manager.validate_and_consume(t1.token, chat_id)
    assert ok1 is True
    assert manager.get_chat_id_by_user(user1) == chat_id

    # User 2 claims the same chat (e.g. phone transferred or account reset)
    t2 = manager.generate_token(user2)
    ok2, _, acc2 = manager.validate_and_consume(t2.token, chat_id)
    assert ok2 is True
    assert acc2.user_id == user2

    # User 2 is the active owner; User 1 has lost the binding
    assert manager.get_chat_id_by_user(user2) == chat_id
    assert manager.get_chat_id_by_user(user1) is None

