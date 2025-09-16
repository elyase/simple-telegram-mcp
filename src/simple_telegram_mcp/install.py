#!/usr/bin/env python3

import sys
import subprocess
from pathlib import Path
from typing import Any, Dict

from dotenv import dotenv_values

# Server metadata
SERVER_NAME = "simple-telegram-mcp"

# Clients supported by this installer
MCP_CLIENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "cursor": {"name": "Cursor", "method": "fastmcp"},
    "claude-desktop": {"name": "Claude Desktop", "method": "fastmcp"},
    "claude-code": {"name": "Claude Code", "method": "fastmcp"},
    "gemini-cli": {"name": "Gemini CLI", "method": "fastmcp"},
    "mcp-json": {"name": "MCP JSON (stdout)", "method": "fastmcp"},
    "codex-cli": {"name": "OpenAI Codex CLI", "method": "codex-toml"},
}


def _abs_server_file() -> str:
    return str((Path(__file__).parent / "mcp_app.py").resolve())


def _env_from_dotenv() -> Dict[str, str]:
    values = dotenv_values(dotenv_path=Path.cwd() / ".env")
    env: Dict[str, str] = {}
    for key in ("TG_API_ID", "TG_API_HASH", "TG_PHONE_NUMBER"):
        v = values.get(key)
        if isinstance(v, str) and v:
            env[key] = v
    return env


def _fastmcp_install(client_key: str) -> None:
    server_file = _abs_server_file()
    base = Path(sys.executable).with_name("fastmcp")
    if sys.platform.startswith("win"):
        base = base.with_suffix(".exe")
    if base.exists():
        runner = [str(base)]
    else:
        # fallback works even if the console script is missing from the virtualenv
        runner = [sys.executable, "-m", "fastmcp.cli"]

    cmd = runner + [
        "install",
        client_key,
        server_file,
        "--server-name",
        SERVER_NAME,
    ]
    # pass .env vars if present
    for k, v in _env_from_dotenv().items():
        cmd += ["--env", f"{k}={v}"]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


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
        "fastmcp",
        "run",
        _abs_server_file(),
    ]
    args_toml = "[\n  \"" + "\",\n  \"".join(args) + "\"\n]"

    lines = [header, 'command = "uv"\n', f"args = {args_toml}\n"]
    env_map = _env_from_dotenv()
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


def install_mcp_server(client_key: str) -> None:
    cfg = MCP_CLIENT_CONFIG.get(client_key)
    if not cfg:
        raise SystemExit(f"Invalid client key '{client_key}'. Choices: {', '.join(MCP_CLIENT_CONFIG)}")
    method = cfg["method"]
    if method == "fastmcp":
        _fastmcp_install(client_key)
    elif method == "codex-toml":
        _codex_cli_install()
    else:
        raise SystemExit(f"Unsupported method: {method}")
