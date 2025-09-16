import argparse
import asyncio
import sys

from simple_telegram_mcp.client import run_initial_login
from simple_telegram_mcp.install import MCP_CLIENT_CONFIG, install_mcp_server
from simple_telegram_mcp.mcp_app import run_stdio


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Simple Telegram MCP server, perform the initial login flow, or install client configuration.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--login",
        action="store_true",
        help="Perform interactive login to create or refresh the Telegram session file and exit.",
    )
    group.add_argument(
        "--install",
        dest="install_client",
        choices=sorted(MCP_CLIENT_CONFIG.keys()),
        metavar="CLIENT_NAME",
        help="Install FastMCP configuration for a supported client and exit.",
    )
    return parser.parse_args()


def _install(client_key: str) -> None:
    install_mcp_server(client_key)
    sys.exit(0)


def _login() -> None:
    success = asyncio.run(run_initial_login())
    sys.exit(0 if success else 1)


def main() -> None:
    args = _parse_args()
    if args.install_client:
        _install(args.install_client)
    if args.login:
        _login()

    run_stdio()
    sys.exit(0)


if __name__ == "__main__":
    main()
