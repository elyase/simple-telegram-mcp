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
from ..schemas import TelegramGetUserProfileInput

# Assuming helpers are in the same directory
from . import helpers

# Import the client wrapper type for type hinting
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Avoid circular import if client uses helpers

logger = logging.getLogger(__name__)

# --- Tool Definition ---

TOOL_NAME = "telegram_get_user_profile"

tool_definition = Tool(
    name=TOOL_NAME,
    description="Retrieves user profile information by user ID or username.",
    inputSchema=TelegramGetUserProfileInput.model_json_schema(),
)

# --- Prompt Definition ---

prompt_definition = Prompt(
    name=TOOL_NAME,
    description="Retrieve profile information for a specific Telegram user.",
    arguments=[
        PromptArgument(
            name="user_id",
            description="User ID or username (@username) to retrieve profile for",
            required=True,
        ),
    ],
)

# --- Implementation ---


async def telegram_get_user_profile_impl(
    args: TelegramGetUserProfileInput,
) -> Dict[str, Any]:  # Return type is Dict on success
    """Retrieves user profile information."""
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
        # The client method returns Dict or raises ConnectionError
        profile = await instance.get_user_profile(args.user_id)
        # Check if the client method indicated an error internally (e.g., user not found)
        if isinstance(profile, dict) and "error" in profile:
            # Convert this specific client-level error to McpError
            raise McpError(ErrorData(code=INVALID_PARAMS, message=profile["error"]))
        return profile
    except ConnectionError as e:  # Catch specific error from client method
        logger.error(f"ConnectionError in {TOOL_NAME}_impl: {e}", exc_info=False)
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
        args = TelegramGetUserProfileInput(**arguments)
    except ValueError as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid arguments: {e}")
        )
    # McpError will be raised from impl if needed
    results = await telegram_get_user_profile_impl(args)
    return [TextContent(type="text", text=json.dumps(results, indent=2))]


async def handle_get_prompt(arguments: Dict[str, Any] | None) -> GetPromptResult:
    """Handler for the get_prompt request."""
    required_args = ["user_id"]
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
        args = TelegramGetUserProfileInput(**arguments)
        results = await telegram_get_user_profile_impl(args)

        # Format the profile nicely for the prompt
        lines = [f"User Profile for '{args.user_id}':"]
        for key, value in results.items():
            lines.append(f"  {key.replace('_', ' ').title()}: {value}")
        output_text = "\n".join(lines)

        return GetPromptResult(
            description=f"User Profile: {args.user_id}",
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
