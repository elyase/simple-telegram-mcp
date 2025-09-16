#!/usr/bin/env python3

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import dotenv_values

from simple_telegram_mcp import __version__
from fastmcp.mcp_config import StdioMCPServer
from fastmcp.utilities.mcp_server_config.v1.environments.uv import UVEnvironment

# Server metadata
SERVER_NAME = "simple-telegram-mcp"
PACKAGE_DEP = f"simple-telegram-mcp=={__version__}"

# Clients supported by this installer
MCP_CLIENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "cursor": {"name": "Cursor", "method": "fastmcp"},
    "claude-desktop": {"name": "Claude Desktop", "method": "fastmcp"},
    "claude-code": {"name": "Claude Code", "method": "fastmcp"},
    "gemini-cli": {"name": "Gemini CLI", "method": "fastmcp"},
    "mcp-json": {"name": "MCP JSON (stdout)", "method": "fastmcp"},
    "vscode": {"name": "VS Code", "method": "vscode"},
    "codex-cli": {"name": "OpenAI Codex CLI", "method": "codex-toml"},
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


def _codex_cli_install() -> None:
    cfg_dir = Path.home() / ".codex"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.toml"

    existing = cfg_file.read_text(encoding="utf-8") if cfg_file.exists() else ""
    header = f"[mcp_servers.{SERVER_NAME}]\n"

    # args rendered as TOML array
    args = [
        "run",
        "--with",
        "fastmcp",
        "--with",
        PACKAGE_DEP,
        "fastmcp",
        "run",
        _server_spec(),
    ]
    args_toml = "[\n  \"" + "\",\n  \"".join(args) + "\"\n]"

    lines = [header, 'command = "uv"\n', f"args = {args_toml}\n"]
    env_map = _runtime_env()
    if env_map:
        env_items = ", ".join([f'"{k}" = "{v}"' for k, v in env_map.items()])
        lines.append(f"env = {{ {env_items} }}\n")
    block = "".join(lines)

    if header in existing:
        # replace current block
        before, _, tail = existing.partition(header)
        import re

        m = re.search(r"\n\[mcp_servers\.[^\]]+\]", "\n" + tail)
        new_content = before + block + (tail[m.start() + 1 :] if m else "")
    else:
        new_content = existing.rstrip() + ("\n\n" if existing else "") + block

    cfg_file.write_text(new_content, encoding="utf-8")
    print(f"Updated {cfg_file} with MCP server '{SERVER_NAME}'.")


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
