# telegram_mcp/src/telegram_mcp/__main__.py
import asyncio
import logging
import argparse
import sys

# Assuming server.py defines the main async function 'serve'
from .server import serve
from .install import (
    install_mcp_server,
    MCP_CLIENT_CONFIG,
)  # Import install function and config

# Import the client wrapper for the login functionality
from .client import (
    run_initial_login,
)  # TelegramClientWrapper is used internally by run_initial_login

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Run the Simple Telegram MCP Server, perform initial login, or install client configuration."
    )
    # Make --login and --install mutually exclusive
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--login",
        action="store_true",
        help="Perform interactive login to create/update session file and exit.",
    )
    group.add_argument(
        "--install",
        dest="install_client",
        choices=MCP_CLIENT_CONFIG.keys(),
        metavar="CLIENT_NAME",
        help=f"Install/update MCP server configuration for a specific client and exit. Choices: {', '.join(MCP_CLIENT_CONFIG.keys())}",
    )

    args = parser.parse_args()

    if args.install_client:
        logger.info(f"Starting installation process for client: {args.install_client}")
        try:
            install_mcp_server(args.install_client)
            logger.info("Installation process finished.")
            sys.exit(0)  # Exit successfully after install
        except Exception as e:
            # Specific errors should be handled within install_mcp_server,
            # but catch any unexpected ones here.
            logger.exception(f"Installation failed: {e}")
            sys.exit(1)  # Exit with error code
    elif args.login:
        logger.info("Starting interactive login process...")
        try:
            # Run the initial login coroutine
            asyncio.run(run_initial_login())
            logger.info(
                "Login process completed. Session file should be created/updated."
            )
            sys.exit(0)  # Exit successfully after login
        except Exception as e:
            logger.exception(f"Interactive login failed: {e}")
            sys.exit(1)  # Exit with error code
    else:
        # Default action: Run the server normally
        logger.info("Starting Simple Telegram MCP Server...")
        try:
            asyncio.run(serve())
        except KeyboardInterrupt:
            logger.info("Server stopped by user.")
            sys.exit(0)  # Clean exit on Ctrl+C
        except Exception as e:
            logger.exception(f"Server encountered an error: {e}")
            sys.exit(1)  # Exit with error code if server crashes


if __name__ == "__main__":
    main()
