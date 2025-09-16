import os

import pytest
from fastmcp import Client

from simple_telegram_mcp.config import get_session_path, load_settings
from simple_telegram_mcp.mcp_app import mcp


pytestmark = pytest.mark.integration


def _session_present() -> bool:
    session_path = get_session_path()
    return session_path.exists()


RUN_TELEGRAM_TESTS = os.getenv("RUN_TELEGRAM_TESTS") == "1"
TELEGRAM_TEST_CHAT_ID = os.getenv("TELEGRAM_TEST_CHAT_ID")


requires_session = pytest.mark.skipif(
    not RUN_TELEGRAM_TESTS,
    reason="Set RUN_TELEGRAM_TESTS=1 to enable Telegram integration tests",
)


@pytest.mark.asyncio
@requires_session
async def test_login_status_runs():
    try:
        load_settings()
    except RuntimeError as exc:
        pytest.skip(f"Missing Telegram configuration: {exc}")
    async with Client(mcp) as client:
        res = await client.call_tool("telegram_login_status", {})
    # Prefer structured data now that outputs are Pydantic
    payload = res.data or res.structured_content
    # Accept dict or object with attributes
    if isinstance(payload, dict):
        assert "connected" in payload and "authorized" in payload
    else:
        assert hasattr(payload, "connected") and hasattr(payload, "authorized")


@pytest.mark.asyncio
@requires_session
async def test_list_chats_smoke():
    try:
        load_settings()
    except RuntimeError as exc:
        pytest.skip(f"Missing Telegram configuration: {exc}")
    async with Client(mcp) as client:
        try:
            res = await client.call_tool("telegram_list_chats", {"limit": 1})
        except Exception as e:
            # If not authorized, this may fail; make the failure explicit
            pytest.skip(f"list_chats requires an authorized session: {e}")
    # Prefer structured data now that outputs are Pydantic
    payload = res.data or res.structured_content
    assert isinstance(payload, list)
    # don't assume non-empty


@pytest.mark.asyncio
@requires_session
async def test_get_chat_history_supergroup():
    if not TELEGRAM_TEST_CHAT_ID:
        pytest.skip("Set TELEGRAM_TEST_CHAT_ID to run chat history test")

    try:
        load_settings()
    except RuntimeError as exc:
        pytest.skip(f"Missing Telegram configuration: {exc}")

    async with Client(mcp) as client:
        res = await client.call_tool(
            "telegram_get_chat_history",
            {"chat_id": TELEGRAM_TEST_CHAT_ID, "limit": 1},
        )

    payload = res.data or res.structured_content
    assert isinstance(payload, list)
    if payload:
        item = payload[0]
        if isinstance(item, dict):
            assert "id" in item
        else:
            assert hasattr(item, "id")
