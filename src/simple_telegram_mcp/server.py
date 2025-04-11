import logging
from typing import Optional
from urllib.parse import urlparse

from mcp.shared.exceptions import McpError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    ErrorData,
    GetPromptResult,
    Prompt,
    PromptMessage,
    TextContent,
    Tool,
    INVALID_PARAMS,  # Correct constant
    INTERNAL_ERROR,
    # NOT_FOUND, # Removed
)

# Telegram specific imports remain
from .client import TelegramClientWrapper
# Schemas might still be needed if server directly interacts with them, but likely not
# from .schemas import (...)

# Import the registration and access functions from the new tools package
from .tools import (
    register_tools,
    get_all_tools,
    get_all_prompts,
    get_tool_handler,
    get_prompt_handler,
    get_resource_handler,
)

# Import the function to set the client instance in helpers
from .tools.helpers import set_telegram_instance

# Logger
logger = logging.getLogger(__name__)

# Global Telegram client instance - remains here as it's managed by the server lifecycle
telegram_wrapper_instance: Optional[TelegramClientWrapper] = None


# --- Server Setup and Run ---


async def serve() -> None:
    """Run the MCP server for Telegram."""
    global telegram_wrapper_instance

    # --- Initialize and Register Tools ---
    server = Server("simple-telegram-mcp")
    # Perform registration *after* server instance is created but before running
    register_tools()
    logger.info(
        f"Registered {len(get_all_tools())} tools and {len(get_all_prompts())} prompts."
    )

    # --- Telegram Client Initialization ---
    logger.info("Initializing Telegram client wrapper...")
    logging.info("Attempting to create TelegramClientWrapper...")
    wrapper = TelegramClientWrapper()
    logging.info("TelegramClientWrapper created.")
    connected_successfully = False
    try:
        logger.info("Connecting Telegram client using existing session...")
        # Attempt to connect using existing session data
        logging.info("Attempting to connect client...")
        await wrapper.connect(perform_login_if_needed=False)
        logging.info("Client connection attempt finished.")

        # Check authorization status *after* connection attempt
        is_auth = await wrapper.client.is_user_authorized()

        if is_auth:
            telegram_wrapper_instance = wrapper
            connected_successfully = True
            logging.info("Attempting to set client instance in helpers...")
            set_telegram_instance(telegram_wrapper_instance)  # Set instance in helpers
            logging.info("Client instance set in helpers.")
            logger.info("Telegram client connected and authorized using session.")
        else:
            # Client connected but not authorized (session invalid/expired/missing)
            telegram_wrapper_instance = wrapper  # Keep instance for status checks etc.
            logging.info("Attempting to set client instance in helpers...")
            set_telegram_instance(telegram_wrapper_instance)  # Set instance in helpers
            logging.info("Client instance set in helpers.")
            connected_successfully = False
            logger.warning(
                "Telegram client connected but is NOT authorized. "
                "Session may be invalid or missing. "
                "Run with --login to perform interactive login."
            )
            # Server continues, but tools requiring authorization will fail.
    except Exception:
        logging.exception("Error during Telegram client initialization/connection:")
        # Ensure instance is None and set in helpers if connection fails
        telegram_wrapper_instance = None
        set_telegram_instance(None)
        # Depending on desired behavior, we might exit or continue without a client

    # --- MCP Server Method Implementations ---

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Returns the list of dynamically registered tools."""
        return get_all_tools()

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """Returns the list of dynamically registered prompts."""
        return get_all_prompts()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Calls the appropriate registered tool handler."""
        handler = get_tool_handler(name)
        if not handler:
            logger.error(f"No handler found for tool: {name}")
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS, message=f"Unknown or unsupported tool: {name}"
                )
            )
            # Removed extra parentheses
        try:
            # The handler itself is now responsible for argument parsing and execution
            return await handler(arguments)
        except McpError as e:
            # Re-raise known MCP errors
            raise e
        except Exception as e:
            # Catch unexpected errors during handler execution
            logger.error(f"Unexpected error calling tool '{name}': {e}", exc_info=True)
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message=f"Internal server error calling tool {name}: {str(e)}",
                )
            )

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
        """Calls the appropriate registered prompt handler."""
        handler = get_prompt_handler(name)
        if not handler:
            logger.error(f"No handler found for prompt: {name}")
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=f"Unknown or unsupported prompt: {name}",
                )
            )
            # Removed extra parentheses
        try:
            # The handler itself is now responsible for argument parsing and execution
            return await handler(arguments)
        except McpError as e:
            # Re-raise known MCP errors
            raise e
        except Exception as e:
            # Catch unexpected errors during handler execution
            logger.error(
                f"Unexpected error getting prompt '{name}': {e}", exc_info=True
            )
            # Return an error GetPromptResult as per MCP spec for get_prompt failures
            return GetPromptResult(
                description="Internal Server Error",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Internal server error getting prompt {name}: {str(e)}",
                        ),
                    )
                ],
            )

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        """Calls the appropriate registered resource handler based on URI."""
        parsed_uri = urlparse(uri)
        scheme = parsed_uri.scheme
        netloc = parsed_uri.netloc

        handler = get_resource_handler(scheme, netloc)
        if not handler:
            logger.error(
                f"No resource handler found for scheme='{scheme}', netloc='{netloc}' (URI: {uri})"
            )
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,  # Correct constant
                    message=f"Unknown or unsupported resource URI: {uri}",
                )
            )
        try:
            # The handler itself is now responsible for parsing the rest of the URI and execution
            return await handler(uri)
        except McpError as e:
            # Re-raise known MCP errors
            raise e
        except Exception as e:
            # Catch unexpected errors during handler execution
            logger.error(
                f"Unexpected error reading resource '{uri}': {e}", exc_info=True
            )
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message=f"Internal server error reading resource {uri}: {str(e)}",
                )
            )

    # --- Run Server and Cleanup ---
    try:
        options = server.create_initialization_options()
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, options, raise_exceptions=True)
    finally:
        logger.info("MCP Server shutting down...")
        if telegram_wrapper_instance and connected_successfully:
            logger.info("Disconnecting Telegram client during shutdown...")
            try:
                await telegram_wrapper_instance.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting Telegram client: {e}", exc_info=True)
        # Clear the instance in helpers as well
        set_telegram_instance(None)
        telegram_wrapper_instance = None
        logger.info("Telegram client disconnected.")


# Note: The old helper functions (_handle_error, _check_client) and
# the old implementation functions (_impl) have been removed from this file
# as they now reside in the respective 'tools' modules or 'tools/helpers.py'.
