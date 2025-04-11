import logging
import json
from typing import List, Dict, Any
from urllib.parse import urlparse, parse_qs

from mcp.types import (
    Tool,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    GetPromptResult,
    ErrorData,
    INTERNAL_ERROR,
    INVALID_PARAMS,
)
from mcp.shared.exceptions import McpError

# Assuming schemas are in the parent directory
from ..schemas import TelegramListChatsInput, ErrorOutput

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

TOOL_NAME = "telegram_list_chats"
RESOURCE_URI_SCHEME = "telegram"
RESOURCE_URI_NETLOC = "dialogs"

tool_definition = Tool(
    name=TOOL_NAME,
    description="Lists recent chats, channels, and conversations.",
    inputSchema=TelegramListChatsInput.model_json_schema(),
)

# --- Prompt Definition ---

prompt_definition = Prompt(
    name=TOOL_NAME,
    description="List recent Telegram chats, channels, and conversations.",
    arguments=[
        PromptArgument(
            name="limit",
            description="Maximum number of chats to retrieve (default 100)",
            required=False,
        )
    ],
)

# --- Implementation ---


async def telegram_list_chats_impl(
    args: TelegramListChatsInput,
) -> list[dict] | ErrorOutput:
    """Lists recent chats, channels, and conversations."""
    # Access the check_client function via the helpers module namespace
    if error := await helpers._check_client():
        # Raise McpError directly if client check fails
        raise error
    try:
        # Access the instance via the helpers module namespace
        instance = helpers.telegram_wrapper_instance
        if not instance:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message="Client instance became unavailable unexpectedly.",
                )
            )
        # Use the local 'instance' variable
        results = await instance.list_chats(limit=args.limit)
        return results
    except Exception as e:
        # Catch specific McpErrors or handle other exceptions
        if isinstance(e, McpError):
            raise e  # Re-raise if it's already an McpError
        logger.error(f"Error in telegram_list_chats_impl: {e}", exc_info=True)
        # Access via helpers namespace
        raise helpers._handle_error(TOOL_NAME, e)  # Convert other exceptions


# --- Handlers ---


async def handle_call_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handler for the call_tool request."""
    try:
        args = TelegramListChatsInput(**arguments)
    except ValueError as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid arguments: {e}")
        )
    # Implementation logic is now within telegram_list_chats_impl
    # McpError will be raised from impl if needed
    results = await telegram_list_chats_impl(args)
    return [TextContent(type="text", text=json.dumps(results, indent=2))]


async def handle_get_prompt(arguments: Dict[str, Any] | None) -> GetPromptResult:
    """Handler for the get_prompt request."""
    try:
        args = TelegramListChatsInput(**(arguments or {}))
        # Implementation logic is now within telegram_list_chats_impl
        results = await telegram_list_chats_impl(args)
        if not results:
            output_text = "No chats found."
        else:
            lines = ["Recent Chats:"] + [
                f"- ID: {c.get('id')}, Name: {c.get('name', 'N/A')}, Type: {c.get('type', '?')}, Unread: {c.get('unread_count', 0)}"
                for c in results
            ]
            output_text = "\n".join(lines)
        return GetPromptResult(
            description="Recent Chats",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=output_text),
                )
            ],
        )
    except McpError as e:
        # Handle errors raised from telegram_list_chats_impl
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


# --- Resource Handler ---


async def handle_read_resource(uri: str) -> str:
    """Handles reading the telegram://dialogs resource."""
    parsed_uri = urlparse(uri)
    if (
        parsed_uri.scheme != RESOURCE_URI_SCHEME
        or parsed_uri.netloc != RESOURCE_URI_NETLOC
    ):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"Unsupported resource URI for this handler: {uri}",
            )
        )

    limit = 100
    if parsed_uri.query:
        try:
            # Use parse_qs for robust query parameter handling
            query_params = parse_qs(parsed_uri.query)
            limit_list = query_params.get("limit")
            if limit_list:
                limit = int(limit_list[0])  # parse_qs returns lists
        except (ValueError, TypeError):
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message="Invalid 'limit' parameter in resource URI",
                )
            )

    # Implementation logic is now within telegram_list_chats_impl
    # McpError will be raised from impl if needed
    args = TelegramListChatsInput(limit=limit)
    results = await telegram_list_chats_impl(args)
    return json.dumps(results, indent=2)
