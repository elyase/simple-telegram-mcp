from pathlib import Path

import pytest

from simple_telegram_mcp import config


@pytest.fixture(autouse=True)
def clear_cache():
    config.reset_settings_cache()
    yield
    config.reset_settings_cache()


def test_load_settings_reads_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TG_API_ID", "123456")
    monkeypatch.setenv("TG_API_HASH", "hash")
    monkeypatch.setenv("TG_PHONE_NUMBER", "+15555555555")
    monkeypatch.setenv("SIMPLE_TELEGRAM_MCP_HOME", str(tmp_path))

    settings = config.load_settings()

    assert settings.api_id == 123456
    assert settings.api_hash == "hash"
    assert settings.phone_number == "+15555555555"
    expected_session = tmp_path / "telegram.session"
    assert settings.session_path == expected_session
    assert expected_session.parent.exists()


def test_load_settings_uses_public_defaults(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("TG_API_ID", raising=False)
    monkeypatch.delenv("TG_API_HASH", raising=False)
    monkeypatch.setenv("SIMPLE_TELEGRAM_MCP_HOME", str(tmp_path))

    settings = config.load_settings()

    assert settings.api_id == 3750314
    assert settings.api_hash == "58088655662eeb4c797477642e44ea54"
    assert settings.session_path.parent == tmp_path
