import os
from pathlib import Path

# --- Configuration ---

# Use hardcoded keys as fallback if environment variables are not set
DEFAULT_API_ID = 611335
DEFAULT_API_HASH = "d524b414d21f4d37f08684c1df41ac9c"

# Standard data directory in user's home
DATA_DIR_NAME = ".telegram_mcp_data"
HOME_DATA_DIR = Path.home() / DATA_DIR_NAME
SESSION_FILENAME = "telegram.session"
QR_CODE_FILENAME = "login_qr.png"  # Will be removed when switching to phone login

# Load optional overrides from .env in CWD if it exists for API keys/phone
# This allows placing .env next to the runner script or in the CWD when running
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path.cwd() / ".env")

# Get values from environment or use defaults
TG_API_ID: int = int(os.getenv("TG_API_ID", DEFAULT_API_ID))
TG_API_HASH: str = os.getenv("TG_API_HASH", DEFAULT_API_HASH)
TG_PHONE_NUMBER: str | None = os.getenv("TG_PHONE_NUMBER")

# Ensure data directory exists
HOME_DATA_DIR.mkdir(parents=True, exist_ok=True)
