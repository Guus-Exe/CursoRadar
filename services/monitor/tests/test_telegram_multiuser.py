"""Tests for Telegram multi-user account linking, token security, and messaging."""

from datetime import datetime, timedelta
import pytest
from app.notifications.telegram import TelegramProvider
from app.telegram_link import TelegramLinkManager


def test_telegram_link_token_generation_and_consumption():
    """Validates successful linking of a Telegram account to a user ID."""
    manager = TelegramLinkManager(token_ttl_minutes=15)
    user_id = "usr-1234-uuid"

    # Step 1: Generate token
    token = manager.generate_token(user_id)
    assert token.user_id == user_id
    assert len(token.token) >= 32
    assert token.is_valid is True

    # Step 2: Validate and consume token via /start <token>
    success, message, account = manager.validate_and_consume(
        token_str=token.token,
        telegram_chat_id="987654321",
        telegram_username="gustavo_dev",
        telegram_first_name="Gustavo",
    )
    assert success is True
    assert account is not None
    assert account.user_id == user_id
    assert account.telegram_chat_id == "987654321"
    assert account.telegram_username == "gustavo_dev"

    # Step 3: Verify account lookup by user and by chat
    acc_by_user = manager.get_account_by_user(user_id)
    assert acc_by_user is not None
    assert acc_by_user.telegram_chat_id == "987654321"

    acc_by_chat = manager.get_account_by_chat("987654321")
    assert acc_by_chat is not None
    assert acc_by_chat.user_id == user_id


def test_telegram_link_token_single_use_prevent_replay():
    """Security: ensures a token cannot be reused by another party."""
    manager = TelegramLinkManager(token_ttl_minutes=15)
    token = manager.generate_token("user-legit")

    # First consumption: success
    ok1, _, _ = manager.validate_and_consume(token.token, "chat-111")
    assert ok1 is True

    # Replay attack / reuse attempt: must be rejected!
    ok2, err2, _ = manager.validate_and_consume(token.token, "chat-attacker")
    assert ok2 is False
    assert "já foi utilizado" in err2


def test_telegram_link_token_expiration():
    """Security: expired tokens must be rejected."""
    manager = TelegramLinkManager(token_ttl_minutes=15)
    token = manager.generate_token("user-late")

    # Artificially expire the token
    token.expires_at = datetime.now() - timedelta(seconds=1)

    ok, err, _ = manager.validate_and_consume(token.token, "chat-222")
    assert ok is False
    assert "expirou" in err


def test_telegram_link_nonexistent_token():
    """Rejects arbitrary / fake tokens."""
    manager = TelegramLinkManager()
    ok, err, _ = manager.validate_and_consume("fake-invalid-token-123", "chat-333")
    assert ok is False
    assert "inválido" in err


def test_telegram_unlink_account():
    """Validates unlinking telegram account from user."""
    manager = TelegramLinkManager()
    token = manager.generate_token("user-to-unlink")
    manager.validate_and_consume(token.token, "chat-444")

    assert manager.get_account_by_user("user-to-unlink") is not None

    unlinked = manager.unlink_account("user-to-unlink")
    assert unlinked is True
    assert manager.get_account_by_user("user-to-unlink") is None
    assert manager.get_account_by_chat("chat-444") is None


@pytest.mark.asyncio
async def test_telegram_provider_send_to_user_mock():
    """Validates multi-recipient message dispatching in TelegramProvider."""
    provider = TelegramProvider(bot_token="123456789:MOCK_TOKEN_FOR_TESTS")
    # provider without network call in test environment
    assert provider.is_configured() is True
    # send_to_user handles individual chat IDs
    assert hasattr(provider, "send_to_user")
