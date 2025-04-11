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
from ..schemas import TelegramGetChatHistoryInput

# Assuming helpers are in the same directory
from . import helpers

# Import the client wrapper type for type hinting
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Avoid circular import if client uses helpers

logger = logging.getLogger(__name__)

# --- Tool Definition ---

TOOL_NAME = "telegram_get_chat_history"

tool_definition = Tool(
    name=TOOL_NAME,
    description="Retrieves recent messages from a specific chat.",
    inputSchema=TelegramGetChatHistoryInput.model_json_schema(),
)

# --- Prompt Definition ---

prompt_definition = Prompt(
    name=TOOL_NAME,
    description="Retrieve recent messages from a specific Telegram chat.",
    arguments=[
        PromptArgument(
            name="chat_id",
            description="Target chat ID or username",
            required=True,
        ),
        PromptArgument(
            name="limit",
            description="Maximum number of messages to retrieve (default 20, max 100)",
            required=False,
        ),
        PromptArgument(
            name="max_id",
            description="Retrieve messages older than this message ID",
            required=False,
        ),
    ],
)

# --- Implementation ---


async def telegram_get_chat_history_impl(
    args: TelegramGetChatHistoryInput,
) -> List[Dict[str, Any]]:  # Return type is List[Dict] on success
    """Retrieves recent messages from a specific chat."""
    if error := await helpers._check_client():
        # _check_client returns ErrorOutput, need to convert to McpError
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=error.error))
    try:
        instance = helpers.telegram_wrapper_instance
        if not instance:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message="Client instance became unavailable unexpectedly.",
                )
            )
        # The client method itself returns List[Dict] or raises ConnectionError
        messages = await instance.get_chat_history(
            args.chat_id, args.limit, args.max_id
        )
        return messages
    except ConnectionError as e:  # Catch specific error from client method
        logger.error(f"ConnectionError in {TOOL_NAME}_impl: {e}", exc_info=False)
        # Convert to McpError for the server framework
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(e)))
    except Exception as e:
        if isinstance(e, McpError):
            raise e
        logger.error(f"Error in {TOOL_NAME}_impl: {e}", exc_info=True)
        raise helpers._handle_error(TOOL_NAME, e)  # Convert other exceptions


# --- Handlers ---


async def handle_call_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handler for the call_tool request."""
    try:
        args = TelegramGetChatHistoryInput(**arguments)
    except ValueError as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid arguments: {e}")
        )
    # McpError will be raised from impl if needed
    results = await telegram_get_chat_history_impl(args)
    return [TextContent(type="text", text=json.dumps(results, indent=2))]


async def handle_get_prompt(arguments: Dict[str, Any] | None) -> GetPromptResult:
    """Handler for the get_prompt request."""
    required_args = ["chat_id"]
    if not arguments or not all(arg in arguments for arg in required_args):
        missing = [
            arg for arg in required_args if not arguments or arg not in arguments
        ]
        return GetPromptResult(
            description="Error",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"Missing required arguments: {', '.join(missing)}",
                    ),
                )
            ],
        )
    try:
        # Use default limit/max_id if not provided in prompt args
        args = TelegramGetChatHistoryInput(**arguments)
        results = await telegram_get_chat_history_impl(args)

        if not results:
            output_text = f"No messages found in chat {args.chat_id}."
        else:
            lines = [f"Recent messages from chat {args.chat_id}:"]
            for msg in results:
                lines.append(
                    f"- ID: {msg.get('id')} | From: {msg.get('sender_name', 'N/A')} | Out: {msg.get('is_outgoing', '?')} | Time: {msg.get('timestamp', '?')}"
                )
                lines.append(
                    f"  Text: {msg.get('text', '')[:100]}{'...' if len(msg.get('text', '')) > 100 else ''}"
                )  # Truncate long messages
                if msg.get("is_reply"):
                    lines.append(f"  (Reply to: {msg.get('reply_to_msg_id')})")
            output_text = "\n".join(lines)

        return GetPromptResult(
            description=f"Chat History for {args.chat_id}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=output_text),
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
