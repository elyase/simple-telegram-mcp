import pytest

from fastmcp import Client

from simple_telegram_mcp.mcp_app import mcp


async def _list_tools() -> list:
    async with Client(mcp) as client:
        return await client.list_tools()


async def _list_resource_templates() -> list:
    async with Client(mcp) as client:
        return await client.list_resource_templates()


async def _list_resources() -> list:
    async with Client(mcp) as client:
        return await client.list_resources()


async def _list_prompts() -> list:
    async with Client(mcp) as client:
        return await client.list_prompts()


@pytest.mark.asyncio
async def test_tools_registered_names():
    tools = await _list_tools()
    names = {t.name for t in tools}
    expected = {
        "telegram_login_status",
        "telegram_list_chats",
        "telegram_search_chats",
        "telegram_post_message",
        "telegram_reply_to_message",
        "telegram_save_draft",
        "telegram_get_draft",
        "telegram_add_reaction",
        "telegram_get_chat_history",
        "telegram_get_user_profile",
        "search_telegram_messages",
    }
    assert expected.issubset(names)


@pytest.mark.asyncio
async def test_resource_templates_registered():
    resource_templates = await _list_resource_templates()
    names = {r.name for r in resource_templates}
    assert {"resource_chat_unread", "resource_chat_history"}.issubset(names)


@pytest.mark.asyncio
async def test_resources_registered():
    resources = await _list_resources()
    uris = {str(r.uri) for r in resources}
    assert {"telegram://session/status", "telegram://chats"}.issubset(uris)


@pytest.mark.asyncio
async def test_prompts_registered():
    prompts = await _list_prompts()
    names = {p.name for p in prompts}
    assert {"telegram/draft-reply", "telegram/check-session"}.issubset(names)
