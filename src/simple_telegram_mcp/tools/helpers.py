import logging
from typing import Optional

from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INTERNAL_ERROR

# Import the client wrapper type for type hinting, but avoid circular import
# We'll likely need to pass the actual instance to functions needing it.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import TelegramClientWrapper

logger = logging.getLogger(__name__)

# Global Telegram client instance - managed in server.py
# Functions here might need access to it. Consider passing it as an argument.
telegram_wrapper_instance: Optional["TelegramClientWrapper"] = None


def set_telegram_instance(instance: Optional["TelegramClientWrapper"]):
    """Sets the global instance for helpers."""
    global telegram_wrapper_instance
    telegram_wrapper_instance = instance


def _handle_error(tool_name: str, e: Exception) -> McpError:
    """Logs an error and returns an McpError for the server."""
    logger.error(f"Error in {tool_name} tool: {e}", exc_info=True)
    return McpError(
        ErrorData(
            code=INTERNAL_ERROR,
            message=f"An unexpected error occurred in {tool_name}: {str(e)}",
        )
    )


async def _check_client() -> Optional[McpError]:
    """Checks if the global client instance is available, connected, and authorized."""
    global telegram_wrapper_instance
    if not telegram_wrapper_instance:
        return McpError(
            ErrorData(
                code=INTERNAL_ERROR, message="Telegram client wrapper not initialized."
            )
        )
    try:
        if (
            not telegram_wrapper_instance.client
            or not telegram_wrapper_instance.client.is_connected()
        ):
            return McpError(
                ErrorData(
                    code=INTERNAL_ERROR, message="Telegram client is not connected."
                )
            )
        if not await telegram_wrapper_instance.client.is_user_authorized():
            return McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message="Telegram client connected but not authorized.",
                )
            )
    except Exception as err:
        logger.error(
            f"Error checking client status in _check_client: {err}", exc_info=True
        )
        return McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Failed to check client status: {str(err)}",
            )
        )
    return None
