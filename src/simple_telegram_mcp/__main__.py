# telegram_mcp/src/telegram_mcp/__main__.py
import asyncio
import logging

# Assuming server.py defines the main async function 'serve'
from .server import serve

# Basic logging setup
logging.basicConfig(level=logging.INFO)


def main():
    # Add any necessary argument parsing here if needed in the future
    # For now, just run the server directly
    try:
        # Pass any required args to serve() if necessary
        asyncio.run(serve())
    except KeyboardInterrupt:
        logging.info("Server stopped by user.")
    except Exception as e:
        logging.exception(f"Server encountered an error: {e}")


if __name__ == "__main__":
    main()
