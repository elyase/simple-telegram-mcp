import logging
from typing import List, Dict, Any

from mcp.types import (
    Tool,
    Prompt,
    PromptMessage,
    TextContent,
    GetPromptResult,
    ErrorData,
    INVALID_PARAMS,
)
from mcp.shared.exceptions import McpError

# Assuming schemas are in the parent directory
from ..schemas import TelegramLoginStatusInput, LoginStatusOutput

# Assuming helpers are in the same directory
# Import the module itself to access its namespace directly
from . import helpers
# Keep specific imports if needed elsewhere, or access via helpers.

# Import the client wrapper type for type hinting
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)

# --- Tool Definition ---

TOOL_NAME = "telegram_login_status"

tool_definition = Tool(
    name=TOOL_NAME,
    description="Checks the current Telegram connection and authorization status.",
    inputSchema=TelegramLoginStatusInput.model_json_schema(),
)

# --- Prompt Definition ---

prompt_definition = Prompt(
    name=TOOL_NAME,
    description="Check the current Telegram connection and authorization status.",
    arguments=[],
)

# --- Implementation ---


async def telegram_login_status_impl(
    args: TelegramLoginStatusInput,
) -> LoginStatusOutput:
    """Checks the current connection and authorization status."""
    # Access the instance via the helpers module namespace
    # Access the instance via the helpers module namespace
    instance = helpers.telegram_wrapper_instance
    if not instance:
        return LoginStatusOutput(
            connected=False, authorized=False, message="Client instance not available."
        )
    # Use the local 'instance' variable now
    try:
        status = await instance.get_login_status()
        return LoginStatusOutput(**status)
    except Exception as e:
        logger.error(f"Error getting login status via tool: {e}", exc_info=True)
        connected = False
        # Check the local 'instance' variable
        if instance and instance.client:
            try:
                connected = instance.client.is_connected()
            except Exception:
                pass
        return LoginStatusOutput(
            connected=connected,
            authorized=False,
            message=f"Error checking status: {str(e)}",
        )


# --- Handlers ---


async def handle_call_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handler for the call_tool request."""
    try:
        args = TelegramLoginStatusInput(**arguments)
    except ValueError as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid arguments: {e}")
        )
    try:
        status = await telegram_login_status_impl(args)
        status_lines = [
            "Telegram Status:",
            f"  Connected: {status.connected}",
            f"  Authorized: {status.authorized}",
        ]
        if status.user:
            user = status.user
            status_lines.extend(
                [
                    f"  User ID: {user.id}",
                    f"  Username: @{user.username or 'N/A'}",
                    f"  Name: {f'{user.first_name or ""} {user.last_name or ""}'.strip()}",
                ]
            )
        if status.message:
            status_lines.append(f"  Message: {status.message}")
        return [TextContent(type="text", text="\n".join(status_lines))]
    except Exception as e:
        # Use the shared error handler
        # Use the shared error handler via helpers or direct import
        mcp_error = helpers._handle_error(
            TOOL_NAME, e
        )  # Access via helpers namespace for consistency
        # Re-raise the McpError for the server framework
        raise mcp_error


async def handle_get_prompt(arguments: Dict[str, Any] | None) -> GetPromptResult:
    """Handler for the get_prompt request."""
    try:
        # Arguments are ignored for this prompt, but we call impl anyway
        status = await telegram_login_status_impl(TelegramLoginStatusInput())
        status_lines = [
            "Telegram Status:",
            f"  Connected: {status.connected}",
            f"  Authorized: {status.authorized}",
        ]
        if status.user:
            user = status.user
            status_lines.extend(
                [
                    f"  User ID: {user.id}",
                    f"  Username: @{user.username or 'N/A'}",
                    f"  Name: {f'{user.first_name or ""} {user.last_name or ""}'.strip()}",
                ]
            )
        if status.message:
            status_lines.append(f"  Message: {status.message}")
        return GetPromptResult(
            description="Telegram Login Status",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text="\n".join(status_lines)),
                )
            ],
        )
    except McpError as e:
        # If _handle_error was used in impl and raised McpError
        return GetPromptResult(
            description="Error",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=e.data.message),
                )
            ],
        )
    except Exception as e:
        # Catch other unexpected errors during prompt generation
        logger.error(
            f"Unexpected error in get_prompt for {TOOL_NAME}: {e}", exc_info=True
        )
        return GetPromptResult(
            description="Error",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text", text=f"Unexpected error generating prompt: {e}"
                    ),
                )
            ],
        )


# --- Resource Handler (Not applicable for login_status) ---
# def handle_read_resource(uri_parts: Dict[str, Any]) -> str:
#     raise NotImplementedError
