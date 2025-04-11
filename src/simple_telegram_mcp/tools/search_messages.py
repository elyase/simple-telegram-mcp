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
from ..schemas import TelegramSearchMessagesInput

# Assuming helpers are in the same directory
from . import helpers

# Import the client wrapper type for type hinting
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Avoid circular import if client uses helpers

logger = logging.getLogger(__name__)

# --- Tool Definition ---

TOOL_NAME = "search_telegram_messages"

tool_definition = Tool(
    name=TOOL_NAME,
    description="Searches messages globally or within a specific chat using the Telegram API.",
    inputSchema=TelegramSearchMessagesInput.model_json_schema(),
)

# --- Prompt Definition ---

prompt_definition = Prompt(
    name=TOOL_NAME,
    description="Search for messages containing specific text, optionally within a chat.",
    arguments=[
        PromptArgument(
            name="query",
            description="Text to search for in messages",
            required=True,
        ),
        PromptArgument(
            name="chat_id",
            description="Optional chat ID or username to limit search scope",
            required=False,
        ),
        PromptArgument(
            name="limit",
            description="Maximum number of messages to return (default 20, max 100)",
            required=False,
        ),
    ],
)

# --- Implementation ---


async def telegram_search_messages_impl(
    args: TelegramSearchMessagesInput,
) -> List[Dict[str, Any]]:  # Return type is List[Dict] on success
    """Searches messages globally or within a specific chat."""
    if error := await helpers._check_client():
        # Convert ErrorOutput to McpError
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
        # The client method itself returns List[Dict] or raises ConnectionError/ValueError
        messages = await instance.search_messages(
            query=args.query, chat_id=args.chat_id, limit=args.limit
        )
        return messages
    except (
        ConnectionError,
        ValueError,
    ) as e:  # Catch specific errors from client method
        logger.error(f"Error in {TOOL_NAME}_impl: {e}", exc_info=False)
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
        args = TelegramSearchMessagesInput(**arguments)
    except ValueError as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid arguments: {e}")
        )
    # McpError will be raised from impl if needed
    results = await telegram_search_messages_impl(args)
    return [TextContent(type="text", text=json.dumps(results, indent=2))]


async def handle_get_prompt(arguments: Dict[str, Any] | None) -> GetPromptResult:
    """Handler for the get_prompt request."""
    required_args = ["query"]
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
        # Use default limit/chat_id if not provided in prompt args
        args = TelegramSearchMessagesInput(**arguments)
        results = await telegram_search_messages_impl(args)

        search_scope = f"in chat {args.chat_id}" if args.chat_id else "globally"
        if not results:
            output_text = f"No messages found matching '{args.query}' {search_scope}."
        else:
            lines = [f"Messages matching '{args.query}' {search_scope}:"]
            for msg in results:
                lines.append(
                    f"- ID: {msg.get('id')} | Chat: {msg.get('chat_id')} | From: {msg.get('sender_name', 'N/A')} | Time: {msg.get('timestamp', '?')}"
                )
                lines.append(
                    f"  Text: {msg.get('text', '')[:100]}{'...' if len(msg.get('text', '')) > 100 else ''}"
                )  # Truncate
            output_text = "\n".join(lines)

        return GetPromptResult(
            description=f"Message Search Results for '{args.query}'",
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
