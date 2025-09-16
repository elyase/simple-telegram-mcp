from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

PENDING_TTL = timedelta(minutes=10)


@dataclass
class PendingLogin:
    phone_number: str
    phone_code_hash: str
    sent_at: datetime
    requires_password: bool = False

    def expired(self) -> bool:
        return datetime.now(timezone.utc) - self.sent_at > PENDING_TTL


class AuthManager:
    def __init__(self) -> None:
        self._pending: dict[str, PendingLogin] = {}

    def start(self, client_id: str, *, phone_number: str, phone_code_hash: str) -> None:
        self._pending[client_id] = PendingLogin(
            phone_number=phone_number,
            phone_code_hash=phone_code_hash,
            sent_at=datetime.now(timezone.utc),
        )

    def mark_requires_password(self, client_id: str) -> None:
        pending = self._pending.get(client_id)
        if pending:
            pending.requires_password = True

    def get(self, client_id: str) -> Optional[PendingLogin]:
        pending = self._pending.get(client_id)
        if not pending:
            return None
        if pending.expired():
            self._pending.pop(client_id, None)
            return None
        return pending

    def clear(self, client_id: str) -> None:
        self._pending.pop(client_id, None)


auth_manager = AuthManager()
