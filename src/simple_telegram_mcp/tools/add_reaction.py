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
from ..schemas import TelegramAddReactionInput, AddReactionOutput

# Assuming helpers are in the same directory
from . import helpers

# Import the client wrapper type for type hinting
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Avoid circular import if client uses helpers

logger = logging.getLogger(__name__)

# --- Tool Definition ---

TOOL_NAME = "telegram_add_reaction"

tool_definition = Tool(
    name=TOOL_NAME,
    description="Adds an emoji reaction to a specific message.",
    inputSchema=TelegramAddReactionInput.model_json_schema(),
)

# --- Prompt Definition ---

prompt_definition = Prompt(
    name=TOOL_NAME,
    description="Add an emoji reaction to a specific message in a Telegram chat.",
    arguments=[
        PromptArgument(
            name="chat_id",
            description="Target chat ID or username",
            required=True,
        ),
        PromptArgument(
            name="message_id",
            description="The ID of the message to react to",
            required=True,
        ),
        PromptArgument(
            name="reaction",
            description="Single emoji character for the reaction",
            required=True,
        ),
    ],
)

# --- Implementation ---


async def telegram_add_reaction_impl(
    args: TelegramAddReactionInput,
) -> AddReactionOutput:
    """Adds an emoji reaction to a specific message."""
    if error := await helpers._check_client():
        raise error  # Raise McpError directly
    try:
        instance = helpers.telegram_wrapper_instance
        if not instance:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message="Client instance became unavailable unexpectedly.",
                )
            )
        # The client method itself returns a dict with status/error
        result_dict = await instance.add_reaction(
            args.chat_id, args.message_id, args.reaction
        )
        # Check if the client method indicated an error internally
        if result_dict.get("status") == "failed":
            # Convert client-level error message to McpError if desired,
            # or just return the schema as is. Let's return schema for now.
            pass
        return AddReactionOutput(**result_dict)
    except Exception as e:
        if isinstance(e, McpError):
            raise e
        logger.error(f"Error in {TOOL_NAME}_impl: {e}", exc_info=True)
        raise helpers._handle_error(TOOL_NAME, e)  # Convert other exceptions


# --- Handlers ---


async def handle_call_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handler for the call_tool request."""
    try:
        args = TelegramAddReactionInput(**arguments)
    except ValueError as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid arguments: {e}")
        )
    # McpError will be raised from impl if needed
    result = await telegram_add_reaction_impl(args)
    return [TextContent(type="text", text=json.dumps(result.model_dump(), indent=2))]


async def handle_get_prompt(arguments: Dict[str, Any] | None) -> GetPromptResult:
    """Handler for the get_prompt request."""
    required_args = ["chat_id", "message_id", "reaction"]
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
        args = TelegramAddReactionInput(**arguments)
        result = await telegram_add_reaction_impl(args)
        return GetPromptResult(
            description="Add Reaction Result",
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
