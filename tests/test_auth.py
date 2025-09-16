from datetime import datetime, timedelta, timezone

from simple_telegram_mcp.auth import AuthManager, PENDING_TTL


def test_auth_manager_start_and_get():
    manager = AuthManager()
    manager.start("client-1", phone_number="+123", phone_code_hash="hash")
    pending = manager.get("client-1")
    assert pending is not None
    assert pending.phone_number == "+123"
    assert pending.phone_code_hash == "hash"


def test_auth_manager_mark_requires_password():
    manager = AuthManager()
    manager.start("client-1", phone_number="+123", phone_code_hash="hash")
    manager.mark_requires_password("client-1")
    pending = manager.get("client-1")
    assert pending is not None
    assert pending.requires_password is True


def test_auth_manager_clear():
    manager = AuthManager()
    manager.start("client-1", phone_number="+123", phone_code_hash="hash")
    manager.clear("client-1")
    assert manager.get("client-1") is None


def test_auth_manager_expired_entry():
    manager = AuthManager()
    manager.start("client-1", phone_number="+123", phone_code_hash="hash")
    pending = manager.get("client-1")
    assert pending is not None
    pending.sent_at = datetime.now(timezone.utc) - (PENDING_TTL + timedelta(minutes=1))
    assert manager.get("client-1") is None
