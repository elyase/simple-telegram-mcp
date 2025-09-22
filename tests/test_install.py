from __future__ import annotations

from pathlib import Path

import pytest

from simple_telegram_mcp import install

try:  # Python < 3.11 fallback for tests
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


@pytest.fixture(autouse=True)
def reset_runtime_env(monkeypatch):
    monkeypatch.setattr(install, "_runtime_env", lambda: {"PATH": "/tmp"})
    yield


def _read_codex_config(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_codex_install_creates_config(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.toml"
    monkeypatch.setenv("SIMPLE_TELEGRAM_MCP_CODEX_CONFIG", str(config_path))

    install._codex_cli_install()

    data = _read_codex_config(config_path)
    server = data["mcp_servers"][install.SERVER_NAME]
    assert server["command"] == "uv"
    assert server["env"] == {"PATH": "/tmp"}
    assert server["transport"] == "stdio"
    assert "fastmcp" in server["args"]


def test_codex_install_merges_existing_config(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.toml"
    existing = """
[mcp_servers.other]
command = "python"
args = ["-m", "other-server"]

[profiles.default]
model = "gpt"
""".strip()
    config_path.write_text(existing + "\n", encoding="utf-8")
    monkeypatch.setenv("SIMPLE_TELEGRAM_MCP_CODEX_CONFIG", str(config_path))

    install._codex_cli_install()

    data = _read_codex_config(config_path)
    servers = data["mcp_servers"]
    assert "other" in servers
    assert install.SERVER_NAME in servers
    assert data["profiles"]["default"]["model"] == "gpt"


def test_codex_install_fallback_appends_block(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.toml"
    existing = """
[profiles.default]
model = "o4"
""".strip()
    config_path.write_text(existing + "\n", encoding="utf-8")
    monkeypatch.setenv("SIMPLE_TELEGRAM_MCP_CODEX_CONFIG", str(config_path))

    monkeypatch.setattr(install, "tomllib", None)

    install._codex_cli_install()

    text = config_path.read_text(encoding="utf-8")
    assert f"[mcp_servers.{install.SERVER_NAME}]" in text

    data = tomllib.loads(text)
    assert install.SERVER_NAME in data["mcp_servers"]
