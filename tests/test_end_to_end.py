import os
from typing import Any, cast
from uuid import uuid4

import pytest

from fastmcp import Client

from simple_telegram_mcp.client import TelegramServiceError, service_context

RUN_TELEGRAM_TESTS = os.getenv("RUN_TELEGRAM_TESTS") == "1"
RUN_STDIO_TESTS = os.getenv("RUN_STDIO_TESTS") == "1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_telegram_round_trip_message():
    if not RUN_TELEGRAM_TESTS:
        pytest.skip("Set RUN_TELEGRAM_TESTS=1 to enable Telegram integration tests")

    message_text = f"pytest telegram roundtrip {uuid4()}"
    try:
        async with service_context() as service:
            client_any = cast(Any, service.client)
            me = await client_any.get_me()
            if not me:
                pytest.skip("Telegram get_me returned None")

            target = getattr(me, "id", "me")
            receipt = await service.post_message(target, message_text)
            assert receipt.message_id > 0

            history = await service.search_messages(
                message_text,
                chat_id=target,
                limit=5,
            )
            assert any(msg.text == message_text for msg in history)
    except TelegramServiceError as exc:
        pytest.skip(f"Telegram service unavailable: {exc}")


@pytest.mark.client_process
@pytest.mark.asyncio
async def test_stdio_transport_login_status():
    if not RUN_STDIO_TESTS:
        pytest.skip("Set RUN_STDIO_TESTS=1 to enable STDIO client-process tests")

    async with Client(["uv", "run", "simple-telegram-mcp"]) as client:  # type: ignore[arg-type]
        response = await client.call_tool("telegram_login_status", {})

    payload = response.data or response.structured_content
    if isinstance(payload, dict):
        assert "connected" in payload and "authorized" in payload
    else:
        assert hasattr(payload, "connected") and hasattr(payload, "authorized")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_draft_round_trip():
    if not RUN_TELEGRAM_TESTS:
        pytest.skip("Set RUN_TELEGRAM_TESTS=1 to enable Telegram integration tests")

    draft_text = f"pytest draft refresh {uuid4()}"
    cleanup_done = False

    prior_draft = None
    async with service_context() as service:
        prior_draft = await service.get_draft("me")

    try:
        async with service_context() as service:
            receipt = await service.save_draft("me", draft_text)
            assert receipt.text == draft_text

            draft = await service.get_draft("me")
            assert draft is not None
            assert draft.text == draft_text
    finally:
        async with service_context() as service:
            if prior_draft:
                await service.save_draft(
                    "me",
                    prior_draft.text,
                    reply_to_message_id=prior_draft.reply_to_message_id,
                )
            else:
                await service.save_draft("me", "")
            cleanup_done = True

    assert cleanup_done
