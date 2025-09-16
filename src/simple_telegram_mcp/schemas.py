from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


class LoginStatusUser(BaseModel):
    """Minimal Telegram user profile information."""

    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class LoginStatus(BaseModel):
    """Overall connection status for the stored Telegram session."""

    connected: bool = Field(description="Whether the client connected to Telegram.")
    authorized: bool = Field(description="Whether the saved session is authorized.")
    session_path: Optional[str] = Field(
        default=None, description="Absolute path to the saved session file, when known."
    )
    message: Optional[str] = Field(
        default=None, description="Human-friendly explanation of the status."
    )
    user: Optional[LoginStatusUser] = None


class ChatSummary(BaseModel):
    """Summary of an available chat/dialog."""

    id: int
    name: Optional[str] = Field(default=None, description="Title or username for the chat")
    type: Literal["User", "Group", "Channel", "Supergroup", "Bot", "Unknown"] = Field(
        default="Unknown", description="Telegram entity classification"
    )
    unread_count: int = Field(default=0, description="Unread messages reported by Telegram")


class MessageSummary(BaseModel):
    """Compact representation of a Telegram message."""

    id: int
    chat_id: Optional[int] = None
    text: Optional[str] = None
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="UTC timestamp of the message",
    )
    is_reply: Optional[bool] = None
    reply_to_msg_id: Optional[int] = None
    is_outgoing: Optional[bool] = None


class MessageReceipt(BaseModel):
    """Metadata returned after posting or replying to a message."""

    message_id: int
    chat_id: Optional[int] = None
    timestamp: datetime = Field(description="UTC timestamp for the sent message")
    text: Optional[str] = None


class ReactionResult(BaseModel):
    """Confirmation that a reaction was applied."""

    emoji: str
    message_id: int
    chat_id: Optional[int] = None


class DraftSummary(BaseModel):
    """Details about a saved Telegram draft."""

    text: str
    date: datetime
    reply_to_message_id: Optional[int] = None


class UserProfile(BaseModel):
    """Public information for a Telegram user."""

    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_bot: Optional[bool] = None
    is_contact: Optional[bool] = None
    is_mutual_contact: Optional[bool] = None
    status: Optional[str] = None
