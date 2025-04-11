# telegram_mcp/src/telegram_mcp/__main__.py
import asyncio
import logging
import argparse
import sys

# Assuming server.py defines the main async function 'serve'
from .server import serve

# Import the client wrapper for the login functionality
from .client import TelegramClientWrapper, run_initial_login

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Run the Simple Telegram MCP Server or perform initial login."
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Perform interactive login to create/update session file and exit.",
    )
    args = parser.parse_args()

    if args.login:
        logger.info("Starting interactive login process...")
        try:
            client_wrapper = TelegramClientWrapper()
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
        # Run the server normally
        logger.info("Starting Simple Telegram MCP Server...")
        try:
            asyncio.run(serve())
        except KeyboardInterrupt:
            logger.info("Server stopped by user.")
        except Exception as e:
            logger.exception(f"Server encountered an error: {e}")
            sys.exit(1)  # Exit with error code if server crashes


if __name__ == "__main__":
    main()
