from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional, Union

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError
from fastmcp.prompts import Message
from mcp.types import PromptMessage
from pydantic import Field

from . import __version__
from .client import (
    TelegramServiceError,
    login_status,
    service_context,
)
from .schemas import (
    ChatSummary,
    DraftSummary,
    LoginStatus,
    MessageReceipt,
    MessageSummary,
    ReactionResult,
    UserProfile,
)

ChatId = Annotated[Union[int, str], Field(description="Telegram chat ID or @username")]
MessageText = Annotated[str, Field(min_length=1, description="Text to send to Telegram")]
MessageLimit = Annotated[int, Field(ge=1, le=200, description="Maximum number of messages to return")]

mcp = FastMCP(
    "Simple Telegram MCP",
    version=__version__,
    instructions="Interact with Telegram through a minimal, well-typed toolset.",
)


def _tool_error(exc: TelegramServiceError) -> ToolError:
    return ToolError(str(exc))


@mcp.tool(name="telegram_login_status", description="Report whether the current session is connected and authorized.", tags={"status", "telegram"})
async def tool_login_status() -> LoginStatus:
    return await login_status()


@mcp.tool(
    name="telegram_list_chats",
    description="List accessible Telegram dialogs for the authorized account.",
    tags={"telegram", "chats"},
)
async def tool_list_chats(limit: Annotated[int, Field(ge=1, le=400, description="Maximum chats to list")] = 100) -> list[ChatSummary]:
    try:
        async with service_context() as service:
            return await service.list_chats(limit=limit)
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.tool(
    name="telegram_search_chats",
    description="Search chats by partial name match.",
    tags={"telegram", "search"},
)
async def tool_search_chats(query: Annotated[str, Field(min_length=1, description="Text to match against chat titles")]) -> list[ChatSummary]:
    try:
        async with service_context() as service:
            return await service.search_chats(query=query)
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.tool(
    name="telegram_post_message",
    description="Post a new message in the target chat.",
    tags={"telegram", "messages"},
)
async def tool_post_message(chat_id: ChatId, text: MessageText) -> MessageReceipt:
    try:
        async with service_context() as service:
            return await service.post_message(chat_id=chat_id, text=text)
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.tool(
    name="telegram_reply_to_message",
    description="Reply to an existing message by message ID.",
    tags={"telegram", "messages"},
)
async def tool_reply_to_message(
    chat_id: ChatId,
    message_id: Annotated[int, Field(ge=1, description="Message ID to reply to")],
    text: MessageText,
) -> MessageReceipt:
    try:
        async with service_context() as service:
            return await service.reply_to_message(chat_id=chat_id, message_id=message_id, text=text)
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.tool(
    name="telegram_save_draft",
    description="Save (or update) a Telegram draft without sending it.",
    tags={"telegram", "messages"},
)
async def tool_save_draft(
    chat_id: ChatId,
    text: MessageText,
    reply_to_message_id: Annotated[Optional[int], Field(default=None, ge=1)] = None,
) -> MessageReceipt:
    try:
        async with service_context() as service:
            return await service.save_draft(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=reply_to_message_id,
            )
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.tool(
    name="telegram_add_reaction",
    description="Apply an emoji reaction to a Telegram message.",
    tags={"telegram", "messages"},
)
async def tool_add_reaction(
    chat_id: ChatId,
    message_id: Annotated[int, Field(ge=1, description="Message ID to react to")],
    emoji: Annotated[str, Field(min_length=1, max_length=48, description="Reaction emoji")],
) -> ReactionResult:
    try:
        async with service_context() as service:
            return await service.add_reaction(chat_id=chat_id, message_id=message_id, emoji=emoji)
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.tool(
    name="telegram_get_chat_history",
    description="Fetch recent messages for a chat without mutating state.",
    tags={"telegram", "messages"},
)
async def tool_get_chat_history(
    chat_id: ChatId,
    limit: MessageLimit = 20,
    max_id: Annotated[Optional[int], Field(default=None, ge=1, description="Return messages older than this ID")]=None,
) -> list[MessageSummary]:
    try:
        async with service_context() as service:
            return await service.get_chat_history(chat_id=chat_id, limit=limit, max_id=max_id)
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.tool(
    name="telegram_get_draft",
    description="Return the current draft for a chat, if one exists.",
    tags={"telegram", "messages"},
)
async def tool_get_draft(chat_id: ChatId) -> Optional[DraftSummary]:
    try:
        async with service_context() as service:
            return await service.get_draft(chat_id=chat_id)
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.tool(
    name="telegram_get_user_profile",
    description="Return public profile information for a Telegram user.",
    tags={"telegram", "profile"},
)
async def tool_get_user_profile(user_id: ChatId) -> UserProfile:
    try:
        async with service_context() as service:
            return await service.get_user_profile(user_id=user_id)
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.tool(
    name="search_telegram_messages",
    description="Search messages globally or inside a single chat.",
    tags={"telegram", "search"},
)
async def tool_search_messages(
    query: Annotated[str, Field(min_length=1, description="Text to search for")],
    chat_id: Annotated[Optional[ChatId], Field(default=None, description="Limit search to this chat")]=None,
    limit: MessageLimit = 20,
) -> list[MessageSummary]:
    try:
        async with service_context() as service:
            return await service.search_messages(query=query, chat_id=chat_id, limit=limit)
    except TelegramServiceError as exc:
        raise _tool_error(exc)


@mcp.resource(
    "telegram://session/status",
    description="Structured session status, useful for dashboards or health checks.",
    tags={"telegram", "status"},
)
async def resource_session_status() -> dict:
    status = await login_status()
    return status.model_dump()


_RECENT_CHAT_RESOURCE_LIMIT = 25
_UNREAD_RESOURCE_LIMIT = 30


@mcp.resource(
    "telegram://chats",
    description="Latest dialogs with unread counts for quick overview.",
    tags={"telegram", "chats"},
)
async def resource_recent_chats() -> dict:
    try:
        async with service_context() as service:
            chats = await service.list_chats(limit=_RECENT_CHAT_RESOURCE_LIMIT)
    except TelegramServiceError as exc:
        raise ResourceError(str(exc)) from exc

    return {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "limit": _RECENT_CHAT_RESOURCE_LIMIT,
        "chats": [chat.model_dump() for chat in chats],
    }


@mcp.resource(
    "telegram://chats/{chat_id}/unread",
    description="Unread incoming messages for a chat, oldest first.",
    tags={"telegram", "messages"},
)
async def resource_chat_unread(chat_id: ChatId) -> dict:
    try:
        async with service_context() as service:
            messages = await service.unread_messages(
                chat_id=chat_id, limit=_UNREAD_RESOURCE_LIMIT
            )
    except TelegramServiceError as exc:
        raise ResourceError(str(exc)) from exc

    return {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "chat_id": chat_id,
        "limit": _UNREAD_RESOURCE_LIMIT,
        "unread": [message.model_dump() for message in messages],
        "unread_count": len(messages),
    }


@mcp.resource(
    "telegram://chats/{chat_id}/history",
    description="Recent history for a Telegram chat as MessageSummary objects.",
    tags={"telegram", "messages"},
)
async def resource_chat_history(
    chat_id: ChatId,
    limit: Annotated[int, Field(ge=1, le=100, description="How many messages to include")] = 20,
) -> list[dict]:
    try:
        async with service_context() as service:
            messages = await service.get_chat_history(chat_id=chat_id, limit=limit)
    except TelegramServiceError as exc:
        raise ResourceError(str(exc)) from exc
    return [message.model_dump() for message in messages]


@mcp.prompt(
    "telegram/draft-reply",
    description="Produce a concise, friendly Telegram reply.",
    tags={"telegram", "draft"},
)
def prompt_draft_reply(
    topic: Annotated[str, Field(description="What the reply should cover")],
    tone: Annotated[str, Field(description="Optional tone hint", default="informal")]="informal",
) -> list[PromptMessage]:
    return [
        Message(
            "You are drafting end-user Telegram replies. Keep them short, clear, and aligned with the requested tone.",
            role="assistant",
        ),
        Message(
            f"Write a {tone} Telegram reply about: {topic}",
            role="user",
        ),
    ]


@mcp.prompt(
    "telegram/check-session",
    description="Ask the assistant to ensure Telegram session readiness before running tools.",
    tags={"telegram", "status"},
)
def prompt_check_session() -> list[PromptMessage]:
    return [
        Message(
            "Verify the Telegram MCP session is connected by calling the `telegram_login_status` tool before proceeding.",
            role="assistant",
        ),
        Message(
            "If the session is not authorized, instruct the user to run `simple-telegram-mcp --login`.",
            role="user",
        ),
    ]


def run_stdio() -> None:
    mcp.run()
