from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_DEFAULT_DIR_NAME = ".simple-telegram-mcp"
_DEFAULT_SESSION_FILENAME = "telegram.session"

_PUBLIC_API_ID = "3750314"
_PUBLIC_API_HASH = "58088655662eeb4c797477642e44ea54"


@dataclass(frozen=True, slots=True)
class TelegramSettings:
    """Resolved configuration needed to talk to Telegram."""

    api_id: int
    api_hash: str
    phone_number: Optional[str]
    session_path: Path


def _clean_env(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _resolve_session_path() -> Path:
    base_dir = _clean_env(os.getenv("SIMPLE_TELEGRAM_MCP_HOME"))
    if base_dir is None:
        base_path = Path.home() / _DEFAULT_DIR_NAME
    else:
        base_path = Path(base_dir).expanduser()

    filename = _clean_env(os.getenv("SIMPLE_TELEGRAM_MCP_SESSION"))
    if filename is None:
        filename = _DEFAULT_SESSION_FILENAME

    session_path = base_path / filename
    session_path.parent.mkdir(parents=True, exist_ok=True)
    return session_path


@lru_cache(maxsize=1)
def load_settings() -> TelegramSettings:
    """Load and cache Telegram credentials from the environment or .env."""

    # Load values from .env if present; respect already-set env vars.
    load_dotenv(override=False)

    api_id_raw = _clean_env(os.getenv("TG_API_ID")) or _PUBLIC_API_ID
    api_hash = _clean_env(os.getenv("TG_API_HASH")) or _PUBLIC_API_HASH
    phone_number = _clean_env(os.getenv("TG_PHONE_NUMBER"))

    try:
        api_id = int(api_id_raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise RuntimeError("TG_API_ID must be an integer.") from exc

    return TelegramSettings(
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number,
        session_path=_resolve_session_path(),
    )


def reset_settings_cache() -> None:
    """Helper for tests: clear cached settings so env changes take effect."""

    load_settings.cache_clear()


def get_session_path() -> Path:
    """Return the configured session path, creating directories if necessary."""

    load_dotenv(override=False)
    return _resolve_session_path()
