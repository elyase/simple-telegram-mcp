#!/usr/bin/env python3

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Sequence, cast

from dotenv import dotenv_values
import tomli_w

from simple_telegram_mcp import __version__
from fastmcp.mcp_config import StdioMCPServer
from fastmcp.utilities.mcp_server_config.v1.environments.uv import UVEnvironment

try:  # Python < 3.11 fallback
    if sys.version_info >= (3, 11):  # pragma: no branch
        import tomllib  # type: ignore
    else:  # pragma: no cover
        import tomli as tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - tomli missing only in misconfigured envs
    tomllib = None  # type: ignore

# Server metadata
SERVER_NAME = "simple-telegram-mcp"
PACKAGE_DEP = f"simple-telegram-mcp=={__version__}"

# Clients supported by this installer
_CODEX_CLIENT_INFO: Dict[str, Any] = {"name": "OpenAI Codex CLI", "method": "codex-toml"}

MCP_CLIENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "cursor": {"name": "Cursor", "method": "fastmcp"},
    "claude-desktop": {"name": "Claude Desktop", "method": "fastmcp"},
    "claude-code": {"name": "Claude Code", "method": "fastmcp"},
    "gemini-cli": {"name": "Gemini CLI", "method": "fastmcp"},
    "mcp-json": {"name": "MCP JSON (stdout)", "method": "fastmcp"},
    "vscode": {"name": "VS Code", "method": "vscode"},
    "codex": _CODEX_CLIENT_INFO,
    "codex-cli": _CODEX_CLIENT_INFO,
}

def _env_from_dotenv() -> Dict[str, str]:
    values = dotenv_values(dotenv_path=Path.cwd() / ".env")
    env: Dict[str, str] = {}
    for key in ("TG_API_ID", "TG_API_HASH", "TG_PHONE_NUMBER"):
        v = values.get(key)
        if isinstance(v, str) and v:
            env[key] = v
    return env


def _runtime_env() -> Dict[str, str]:
    """Collect default environment values for installed clients."""

    env = _env_from_dotenv()

    uv_exe = shutil.which("uv")
    if uv_exe:
        uv_dir = str(Path(uv_exe).parent)
        path_value = env.get("PATH") or os.environ.get("PATH", "")
        parts = [p for p in path_value.split(os.pathsep) if p]
        if uv_dir not in parts:
            parts.insert(0, uv_dir)
        env["PATH"] = os.pathsep.join(parts)

    return env


def _fastmcp_runner() -> list[str]:
    base = Path(sys.executable).with_name("fastmcp")
    if sys.platform.startswith("win"):
        base = base.with_suffix(".exe")
    if base.exists():
        return [str(base)]
    return [sys.executable, "-m", "fastmcp.cli"]


def _server_spec() -> str:
    return f"{(Path(__file__).parent / 'mcp_app.py').resolve()}:mcp"


def _fastmcp_install(client_key: str) -> None:
    runner = _fastmcp_runner()
    cmd = runner + [
        "install",
        client_key,
        "--server-spec",
        _server_spec(),
        "--name",
        SERVER_NAME,
        "--with",
        PACKAGE_DEP,
    ]
    # pass .env vars if present
    for k, v in _runtime_env().items():
        cmd += ["--env", f"{k}={v}"]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _build_stdio_server_config() -> StdioMCPServer:
    env_config = UVEnvironment(
        dependencies=["fastmcp", PACKAGE_DEP],
    )
    full_command = env_config.build_command(["fastmcp", "run", _server_spec()])
    return StdioMCPServer(
        command=full_command[0],
        args=full_command[1:],
        env=_runtime_env(),
    )


def _generate_fastmcp_server_block() -> Dict[str, Any]:
    server = _build_stdio_server_config()
    return server.model_dump(exclude_none=True)


def _codex_config_path() -> Path:
    override = os.environ.get("SIMPLE_TELEGRAM_MCP_CODEX_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".codex" / "config.toml"


def _load_toml_document(text: str) -> Dict[str, Any] | None:
    if not text.strip():
        return {}
    if tomllib is None:  # pragma: no cover - misconfigured environment
        return None
    try:
        data = tomllib.loads(text)
    except Exception:  # pragma: no cover - invalid TOML
        return None
    if not isinstance(data, dict):  # pragma: no cover - tomllib should return dict
        return None
    return cast(Dict[str, Any], data)


def _ensure_table(root: MutableMapping[str, Any], key: str) -> MutableMapping[str, Any]:
    value = root.get(key)
    if isinstance(value, MutableMapping):
        return value
    table: Dict[str, Any] = {}
    root[key] = table
    return table


def _format_toml_value(value: Any) -> str:
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
        return f'"{escaped}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        inner = ", ".join(_format_toml_value(item) for item in value)
        return f"[{inner}]"
    if isinstance(value, Mapping):
        inner = ", ".join(
            f'"{key}" = {_format_toml_value(val)}' for key, val in value.items()
        )
        return "{ " + inner + " }"
    raise TypeError(f"Unsupported value type: {type(value)!r}")


def _render_codex_block(server_block: Mapping[str, Any]) -> str:
    lines = [f"[mcp_servers.{SERVER_NAME}]"]
    for key, value in server_block.items():
        lines.append(f"{key} = {_format_toml_value(value)}")
    return "\n".join(lines) + "\n"


def _merge_codex_server_block(existing: str, server_block: Mapping[str, Any]) -> str:
    block = _render_codex_block(server_block)
    if not existing.strip():
        return block if block.endswith("\n") else block + "\n"

    pattern = re.compile(
        rf"(?ms)^\[mcp_servers\.{re.escape(SERVER_NAME)}\]\n.*?(?=^\[|\Z)"
    )
    match = pattern.search(existing)
    if match:
        new_content = existing[: match.start()] + block + existing[match.end():]
    else:
        trimmed = existing.rstrip()
        separator = "\n\n" if trimmed else ""
        new_content = trimmed + separator + block

    if not new_content.endswith("\n"):
        new_content += "\n"
    return new_content


def _codex_cli_install() -> None:
    config_path = _codex_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    existing_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    server_block = _generate_fastmcp_server_block()

    document = _load_toml_document(existing_text)
    if document is not None:
        mcp_servers = _ensure_table(document, "mcp_servers")
        mcp_servers[SERVER_NAME] = server_block
        config_path.write_text(tomli_w.dumps(document), encoding="utf-8")
        print(f"Updated Codex MCP config at {config_path}")
        return

    merged = _merge_codex_server_block(existing_text, server_block)
    config_path.write_text(merged, encoding="utf-8")
    print(f"Updated Codex MCP config at {config_path}")


def _vscode_config_path() -> Path:
    override = os.environ.get("SIMPLE_TELEGRAM_MCP_VSCODE_CONFIG")
    if override:
        return Path(override).expanduser()

    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "Code"
    elif system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Code"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "Code"
    return base / "User" / "mcp.json"


def _vscode_install() -> None:
    config_path = _vscode_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    server_block = _generate_fastmcp_server_block()

    if config_path.exists() and config_path.read_text().strip():
        try:
            existing = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    if not isinstance(existing, dict):
        existing = {}

    servers = existing.get("servers")
    if not isinstance(servers, dict):
        servers = {}
        existing["servers"] = servers

    servers[SERVER_NAME] = server_block

    config_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(f"Updated VS Code MCP config at {config_path}")


def install_mcp_server(client_key: str) -> None:
    cfg = MCP_CLIENT_CONFIG.get(client_key)
    if not cfg:
        raise SystemExit(f"Invalid client key '{client_key}'. Choices: {', '.join(MCP_CLIENT_CONFIG)}")
    method = cfg["method"]
    if method == "fastmcp":
        _fastmcp_install(client_key)
    elif method == "codex-toml":
        _codex_cli_install()
    elif method == "vscode":
        _vscode_install()
    else:
        raise SystemExit(f"Unsupported method: {method}")
