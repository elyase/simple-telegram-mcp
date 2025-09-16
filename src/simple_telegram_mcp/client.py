from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional, Union, cast

from telethon import TelegramClient, errors, types
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import SaveDraftRequest, SendReactionRequest
from telethon.tl.types import Channel, Chat, Message as TLMessage, User

from simple_telegram_mcp.config import load_settings
from simple_telegram_mcp.schemas import (
    ChatSummary,
    DraftSummary,
    LoginStatus,
    LoginStatusUser,
    MessageReceipt,
    MessageSummary,
    ReactionResult,
    UserProfile,
)

logger = logging.getLogger(__name__)

_SYSTEM_VERSION = "4.16.30-fastmcp"


class TelegramServiceError(RuntimeError):
    """Base error raised for Telegram service operations."""


class TelegramAuthorizationError(TelegramServiceError):
    """Raised when a session exists but is not authorized."""


class TelegramInteractionError(TelegramServiceError):
    """Raised for failures while calling Telegram APIs."""


class TelegramTwoFactorRequired(TelegramServiceError):
    """Raised when Telegram requires the 2FA password to continue."""


def _entity_type(entity: object) -> ChatSummary.model_fields["type"].annotation:  # type: ignore[index]
    if isinstance(entity, User):
        return "Bot" if entity.bot else "User"
    if isinstance(entity, Chat):
        return "Group"
    if isinstance(entity, Channel):
        return "Channel" if entity.broadcast else "Supergroup"
    return "Unknown"


def _utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


if TYPE_CHECKING:
    from telethon.tl.custom.message import Message as CustomMessage
else:  # pragma: no cover - runtime alias only
    CustomMessage = TLMessage  # type: ignore[misc]

MessageType = Union[CustomMessage, TLMessage, Any]


async def _sender_name(message: MessageType) -> Optional[str]:
    try:
        sender = await cast(Any, message).get_sender()
    except Exception:  # pragma: no cover - defensive logging only
        logger.debug(
            "Failed to resolve sender for message %s",
            getattr(message, "id", "<unknown>"),
            exc_info=True,
        )
        return None

    if not sender:
        return None
    for attr in ("username", "title", "first_name", "last_name"):
        value = getattr(sender, attr, None)
        if value:
            return str(value)
    if isinstance(sender, User):
        return f"User {sender.id}"
    return None


async def _message_to_summary(message: MessageType) -> MessageSummary:
    msg = cast(Any, message)
    return MessageSummary(
        id=msg.id,
        chat_id=getattr(msg, "chat_id", None),
        text=msg.text
        or (
            f"[Non-text content: {type(msg.media).__name__}]"
            if getattr(msg, "media", None)
            else None
        ),
        sender_id=getattr(msg, "sender_id", None),
        sender_name=await _sender_name(message),
        timestamp=_utc(getattr(msg, "date", None)),
        is_reply=getattr(msg, "is_reply", None),
        reply_to_msg_id=getattr(msg, "reply_to_msg_id", None)
        if getattr(msg, "is_reply", None)
        else None,
        is_outgoing=getattr(msg, "out", None),
    )


def _normalized_identifier(identifier: Union[int, str]) -> Union[int, str]:
    if isinstance(identifier, str):
        stripped = identifier.strip()
        if not stripped:
            return stripped
        try:
            return int(stripped)
        except ValueError:
            return stripped
    return identifier


class TelegramService:
    """Async context manager that manages a Telethon client session."""

    def __init__(self, *, require_authorized: bool = True):
        self._settings = load_settings()
        self._require_authorized = require_authorized
        self._client: TelegramClient | None = None
        self._connected = False
        self._authorized = False

    async def _resolve_entity(self, identifier: Union[int, str]) -> Any:
        client = cast(Any, self.client)
        target = _normalized_identifier(identifier)
        try:
            return await client.get_entity(target)
        except (ValueError, errors.RPCError) as exc:
            raise TelegramInteractionError(
                f"Could not resolve chat '{identifier}': {exc}"
            ) from exc

    async def _resolve_input_peer(self, identifier: Union[int, str]) -> Any:
        client = cast(Any, self.client)
        target = _normalized_identifier(identifier)
        try:
            return await client.get_input_entity(target)
        except (ValueError, errors.RPCError) as exc:
            raise TelegramInteractionError(
                f"Could not resolve chat '{identifier}'"
            ) from exc

    async def __aenter__(self) -> "TelegramService":
        settings = self._settings
        client = TelegramClient(
            str(settings.session_path),
            settings.api_id,
            settings.api_hash,
            system_version=_SYSTEM_VERSION,
        )
        client_any = cast(Any, client)
        await client_any.connect()
        self._client = client
        self._connected = client.is_connected()
        try:
            self._authorized = await client_any.is_user_authorized()
        except Exception as exc:  # pragma: no cover - defensive
            await client_any.disconnect()
            self._client = None
            raise TelegramInteractionError(f"Failed to check authorization: {exc}") from exc

        if self._require_authorized and not self._authorized:
            await client_any.disconnect()
            self._client = None
            raise TelegramAuthorizationError(
                "Telegram session is not authorized. Run `simple-telegram-mcp --login` and try again."
            )

        return self

    async def __aexit__(self, *_exc_info) -> None:
        if self._client and self._client.is_connected():
            await cast(Any, self._client).disconnect()
        self._client = None
        self._connected = False
        self._authorized = False

    @property
    def client(self) -> TelegramClient:
        if self._client is None:
            raise TelegramServiceError("Telegram client is not connected.")
        return self._client

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def authorized(self) -> bool:
        return self._authorized

    async def list_chats(self, limit: int) -> list[ChatSummary]:
        summaries: list[ChatSummary] = []
        client = cast(Any, self.client)
        async for dialog in client.iter_dialogs(limit=limit):
            summaries.append(
                ChatSummary(
                    id=dialog.id,
                    name=dialog.name,
                    type=_entity_type(dialog.entity),
                    unread_count=dialog.unread_count or 0,
                )
            )
        return summaries

    async def search_chats(self, query: str) -> list[ChatSummary]:
        lower = query.lower()
        matches: list[ChatSummary] = []
        client = cast(Any, self.client)
        async for dialog in client.iter_dialogs():
            if dialog.name and lower in dialog.name.lower():
                matches.append(
                    ChatSummary(
                        id=dialog.id,
                        name=dialog.name,
                        type=_entity_type(dialog.entity),
                        unread_count=dialog.unread_count or 0,
                    )
                )
        return matches

    async def post_message(self, chat_id: Union[int, str], text: str) -> MessageReceipt:
        client = cast(Any, self.client)
        target = _normalized_identifier(chat_id)
        try:
            message = await client.send_message(target, text)
        except errors.RPCError as exc:
            raise TelegramInteractionError(f"Failed to send message: {exc}") from exc
        return MessageReceipt(
            message_id=cast(Any, message).id,
            chat_id=getattr(message, "chat_id", None),
            text=getattr(message, "text", None),
            timestamp=_utc(getattr(message, "date", None)),
        )

    async def reply_to_message(
        self, chat_id: Union[int, str], message_id: int, text: str
    ) -> MessageReceipt:
        client = cast(Any, self.client)
        target = _normalized_identifier(chat_id)
        try:
            message = await client.send_message(
                target, text, reply_to=message_id
            )
        except errors.RPCError as exc:
            raise TelegramInteractionError(f"Failed to reply to message: {exc}") from exc
        return MessageReceipt(
            message_id=cast(Any, message).id,
            chat_id=getattr(message, "chat_id", None),
            text=getattr(message, "text", None),
            timestamp=_utc(getattr(message, "date", None)),
        )

    async def add_reaction(
        self, chat_id: Union[int, str], message_id: int, emoji: str
    ) -> ReactionResult:
        client = cast(Any, self.client)
        peer = await self._resolve_input_peer(chat_id)
        try:
            await client(
                SendReactionRequest(
                    peer=peer,
                    msg_id=message_id,
                    reaction=[types.ReactionEmoji(emoticon=emoji)],
                )
            )
        except errors.RPCError as exc:
            raise TelegramInteractionError(f"Failed to add reaction: {exc}") from exc

        peer_ref = cast(Any, peer)
        ref = (
            getattr(peer_ref, "channel_id", None)
            or getattr(peer_ref, "chat_id", None)
            or getattr(peer_ref, "user_id", None)
        )
        return ReactionResult(emoji=emoji, message_id=message_id, chat_id=ref)

    async def get_chat_history(
        self, chat_id: Union[int, str], limit: int, max_id: Optional[int] = None
    ) -> list[MessageSummary]:
        client = cast(Any, self.client)
        peer = await self._resolve_input_peer(chat_id)
        request_max_id = max_id or 0
        messages = await client.get_messages(entity=peer, limit=limit, max_id=request_max_id)
        summaries = []
        for message in messages:
            if isinstance(message, (TLMessage, CustomMessage)):
                summaries.append(await _message_to_summary(message))
        return summaries

    async def get_draft(
        self, chat_id: Union[int, str]
    ) -> Optional[DraftSummary]:
        client = cast(Any, self.client)
        entity = await self._resolve_entity(chat_id)

        try:
            drafts = await client.get_drafts()
        except errors.RPCError as exc:
            raise TelegramInteractionError(f"Failed to load draft: {exc}") from exc

        draft = None
        target_id = getattr(entity, "id", None)
        for item in drafts:
            item_entity = getattr(item, "entity", None)
            item_id = getattr(item_entity, "id", None)
            if target_id is not None and item_id == target_id:
                draft = item
                break

        draft_text = getattr(draft, "text", None) or getattr(draft, "raw_text", None)
        if not draft or not draft_text:
            return None

        reply_to_id = getattr(draft, "reply_to_msg_id", None)
        if reply_to_id is None:
            reply_to = getattr(draft, "reply_to", None)
            reply_to_id = getattr(reply_to, "reply_to_msg_id", None)

        return DraftSummary(
            text=draft_text,
            reply_to_message_id=reply_to_id,
            date=_utc(getattr(draft, "date", None)),
        )

    async def get_user_profile(self, user_id: Union[int, str]) -> UserProfile:
        client = cast(Any, self.client)
        entity = await self._resolve_entity(user_id)

        if not isinstance(entity, User):
            raise TelegramInteractionError(
                f"Resolved entity for '{user_id}' is not a user."
            )
        return UserProfile(
            id=entity.id,
            username=entity.username,
            first_name=entity.first_name,
            last_name=entity.last_name,
            phone=entity.phone,
            is_bot=entity.bot,
            is_contact=entity.contact,
            is_mutual_contact=entity.mutual_contact,
            status=str(entity.status) if entity.status else None,
        )

    async def send_login_code(
        self, phone_number: str, *, force_sms: bool = False
    ) -> str:
        client = cast(Any, self.client)
        try:
            result = await client.send_code_request(phone_number, force_sms=force_sms)
        except errors.PhoneNumberInvalidError as exc:
            raise TelegramInteractionError("The phone number appears to be invalid.") from exc
        except errors.RPCError as exc:
            raise TelegramInteractionError(f"Failed to request login code: {exc}") from exc
        return result.phone_code_hash

    async def sign_in_with_code(
        self,
        *,
        phone_number: str,
        code: str,
        phone_code_hash: str,
        password: Optional[str] = None,
    ) -> None:
        client = cast(Any, self.client)
        try:
            await client.sign_in(
                phone=phone_number,
                code=code,
                phone_code_hash=phone_code_hash,
            )
        except SessionPasswordNeededError as exc:
            if password is None:
                raise TelegramTwoFactorRequired(
                    "Two-factor password required to complete login."
                ) from exc
            try:
                await client.sign_in(password=password)
            except errors.RPCError as exc_pwd:
                raise TelegramInteractionError(
                    f"Failed to complete two-factor authentication: {exc_pwd}"
                ) from exc_pwd
        except errors.PhoneCodeInvalidError as exc:
            raise TelegramInteractionError("The verification code is invalid.") from exc
        except errors.RPCError as exc:
            raise TelegramInteractionError(f"Failed to sign in: {exc}") from exc

    async def search_messages(
        self, query: str, *, chat_id: Optional[Union[int, str]] = None, limit: int = 20
    ) -> list[MessageSummary]:
        client = cast(Any, self.client)
        entity: Any = None
        if chat_id is not None:
            entity = await self._resolve_entity(chat_id)

        summaries: list[MessageSummary] = []
        async for message in client.iter_messages(entity=entity, limit=limit, search=query):
            if isinstance(message, (TLMessage, CustomMessage)):
                summaries.append(await _message_to_summary(message))
        return summaries

    async def save_draft(
        self,
        chat_id: Union[int, str],
        text: str,
        reply_to_message_id: Optional[int] = None,
    ) -> MessageReceipt:
        client = cast(Any, self.client)
        try:
            peer = await client.get_input_entity(chat_id)
            reply_to = None
            if reply_to_message_id:
                reply_to = types.InputReplyToMessage(
                    reply_to_msg_id=reply_to_message_id
                )
            await client(
                SaveDraftRequest(
                    peer=peer,
                    message=text,
                    reply_to=reply_to,
                )
            )
        except errors.RPCError as exc:
            raise TelegramInteractionError(f"Failed to save draft: {exc}") from exc
        except ValueError as exc:
            raise TelegramInteractionError(
                f"Could not resolve chat '{chat_id}' for draft"
            ) from exc

        peer_ref = cast(Any, peer)
        ref = (
            getattr(peer_ref, "channel_id", None)
            or getattr(peer_ref, "chat_id", None)
            or getattr(peer_ref, "user_id", None)
        )
        return MessageReceipt(
            message_id=reply_to_message_id or 0,
            chat_id=ref,
            text=text,
            timestamp=datetime.now(timezone.utc),
        )

    async def unread_messages(
        self, chat_id: Union[int, str], limit: int
    ) -> list[MessageSummary]:
        client = cast(Any, self.client)
        try:
            entity = await client.get_entity(chat_id)
        except (ValueError, errors.RPCError) as exc:
            raise TelegramInteractionError(
                f"Could not resolve chat '{chat_id}': {exc}"
            ) from exc

        summaries: list[MessageSummary] = []
        async for message in client.iter_messages(entity=entity, limit=limit * 3):
            if not isinstance(message, (TLMessage, CustomMessage)):
                continue
            msg_any = cast(Any, message)
            is_outgoing = bool(getattr(msg_any, "out", False))
            is_read = bool(getattr(msg_any, "is_read", True))
            is_unread = (not is_outgoing) and (is_read is False)
            if not is_unread:
                continue
            summaries.append(await _message_to_summary(message))
            if len(summaries) >= limit:
                break
        summaries.reverse()
        return summaries


async def login_status() -> LoginStatus:
    try:
        settings = load_settings()
    except RuntimeError as exc:
        return LoginStatus(
            connected=False,
            authorized=False,
            session_path=None,
            message=str(exc),
        )

    session_path = settings.session_path
    session_path_str = str(session_path)
    session_exists = session_path.exists()

    try:
        async with TelegramService(require_authorized=False) as service:
            message = (
                "Session authorized and ready" if service.authorized else "Session found but not authorized"
            )
            user: Optional[LoginStatusUser] = None
            if service.authorized:
                try:
                    me = await cast(Any, service.client).get_me()
                except errors.RPCError as exc:  # pragma: no cover - unlikely but logged
                    logger.warning("Unable to fetch current user: %s", exc)
                    me = None
                if isinstance(me, User):
                    user = LoginStatusUser(
                        id=me.id,
                        username=me.username,
                        first_name=me.first_name,
                        last_name=me.last_name,
                    )
            return LoginStatus(
                connected=service.connected,
                authorized=service.authorized,
                session_path=session_path_str if session_exists else None,
                message=message,
                user=user,
            )
    except TelegramAuthorizationError:
        return LoginStatus(
            connected=True,
            authorized=False,
            session_path=session_path_str if session_exists else None,
            message="Session exists but is not authorized. Run `simple-telegram-mcp --login`.",
        )
    except TelegramServiceError as exc:
        return LoginStatus(
            connected=False,
            authorized=False,
            session_path=session_path_str if session_exists else None,
            message=str(exc),
        )


async def run_initial_login() -> bool:
    """Interactive login flow to create a persistent Telegram session."""

    try:
        settings = load_settings()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return False

    session_path = settings.session_path
    if session_path.exists():
        session_path.unlink()

    client = TelegramClient(
        str(session_path),
        settings.api_id,
        settings.api_hash,
        system_version=_SYSTEM_VERSION,
    )

    client_any = cast(Any, client)
    await client_any.connect()
    phone = settings.phone_number
    if not phone:
        try:
            phone = input("Enter your phone number (e.g. +1234567890): ").strip()
        except EOFError:
            print("[ERROR] Cannot prompt for phone number in the current environment.")
            await client_any.disconnect()
            return False

    try:
        code_request = await client_any.send_code_request(phone)
    except errors.PhoneNumberInvalidError:
        print("[ERROR] The phone number appears to be invalid.")
        await client_any.disconnect()
        return False
    except errors.RPCError as exc:
        print(f"[ERROR] Failed to request login code: {exc}")
        await client_any.disconnect()
        return False

    try:
        code = input("Enter the code you received: ").strip()
    except EOFError:
        print("[ERROR] Cannot prompt for login code in the current environment.")
        await client_any.disconnect()
        return False

    try:
        await client_any.sign_in(phone=phone, code=code, phone_code_hash=code_request.phone_code_hash)
    except SessionPasswordNeededError:
        try:
            password = input("Two-factor password: ").strip()
        except EOFError:
            print("[ERROR] Cannot prompt for two-factor password in the current environment.")
            await client_any.disconnect()
            return False
        try:
            await client_any.sign_in(password=password)
        except errors.RPCError as exc:
            print(f"[ERROR] Failed to complete 2FA login: {exc}")
            await client_any.disconnect()
            return False
    except errors.RPCError as exc:
        print(f"[ERROR] Failed to sign in: {exc}")
        await client_any.disconnect()
        return False
    finally:
        await client_any.disconnect()

    print(f"[SUCCESS] Session saved to {session_path}")
    return True


@asynccontextmanager
async def service_context(
    *, require_authorized: bool = True
) -> AsyncIterator[TelegramService]:
    service = TelegramService(require_authorized=require_authorized)
    async with service:
        yield service
