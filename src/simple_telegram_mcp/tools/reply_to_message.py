import logging
import json
from typing import List, Dict, Any

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
from ..schemas import TelegramReplyToMessageInput, ReplyMessageOutput

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

TOOL_NAME = "telegram_reply_to_message"

tool_definition = Tool(
    name=TOOL_NAME,
    description="Replies to a specific message.",
    inputSchema=TelegramReplyToMessageInput.model_json_schema(),
)

# --- Prompt Definition ---

prompt_definition = Prompt(
    name=TOOL_NAME,
    description="Send a reply to a specific message in a Telegram chat.",
    arguments=[
        PromptArgument(
            name="chat_id",
            description="Target chat ID or username",
            required=True,
        ),
        PromptArgument(
            name="message_id",
            description="The ID of the message to reply to",
            required=True,
        ),
        PromptArgument(name="text", description="Reply text", required=True),
    ],
)

# --- Implementation ---


async def telegram_reply_to_message_impl(
    args: TelegramReplyToMessageInput,
) -> ReplyMessageOutput:
    """Replies to a specific message."""
    # Access the check_client function via the helpers module namespace
    if error := await helpers._check_client():
        raise error  # Raise McpError directly
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
        result_dict = await instance.reply_to_message(
            args.chat_id, args.message_id, args.text
        )
        return ReplyMessageOutput(**result_dict)
    except Exception as e:
        if isinstance(e, McpError):
            raise e
        logger.error(f"Error in telegram_reply_to_message_impl: {e}", exc_info=True)
        # Access via helpers namespace
        raise helpers._handle_error(TOOL_NAME, e)  # Convert other exceptions


# --- Handlers ---


async def handle_call_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handler for the call_tool request."""
    try:
        args = TelegramReplyToMessageInput(**arguments)
    except ValueError as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid arguments: {e}")
        )
    # McpError will be raised from impl if needed
    result = await telegram_reply_to_message_impl(args)
    return [TextContent(type="text", text=json.dumps(result.model_dump(), indent=2))]


async def handle_get_prompt(arguments: Dict[str, Any] | None) -> GetPromptResult:
    """Handler for the get_prompt request."""
    if (
        not arguments
        or "chat_id" not in arguments
        or "message_id" not in arguments
        or "text" not in arguments
    ):
        return GetPromptResult(
            description="Error",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="Missing required arguments: chat_id, message_id, text",
                    ),
                )
            ],
        )
    try:
        # Pydantic validation handles missing/invalid args automatically if called
        args = TelegramReplyToMessageInput(**arguments)
        # McpError will be raised from impl if needed
        result = await telegram_reply_to_message_impl(args)
        return GetPromptResult(
            description="Reply Result",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=json.dumps(result.model_dump(), indent=2),
                    ),
                )
            ],
        )
    except McpError as e:
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


# --- Resource Handler (Not applicable) ---
