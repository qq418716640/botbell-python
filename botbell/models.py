"""BotBell data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Action:
    """A reply action button or input field."""

    key: str
    label: str
    type: str = "button"
    placeholder: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"key": self.key, "label": self.label}
        if self.type != "button":
            d["type"] = self.type
        if self.placeholder is not None:
            d["placeholder"] = self.placeholder
        return d


@dataclass(frozen=True)
class Reply:
    """A user reply to a message."""

    reply_id: str
    bot_id: str
    message: str
    timestamp: int = 0
    action: str | None = None
    reply_to: str | None = None


@dataclass(frozen=True)
class Bot:
    """A bot resource."""

    bot_id: str
    name: str
    token: str | None = field(default=None, repr=False)
    push_url: str | None = None
    reply_url: str | None = None
    status: str | None = None
    created_at: int = 0

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True)
class Quota:
    """User's message quota information."""

    plan: str
    monthly_limit: int | None = None
    monthly_used: int = 0
    bot_limit: int = 3
    bot_used: int = 0

    @property
    def messages_remaining(self) -> int | None:
        if self.monthly_limit is None:
            return None  # unlimited
        return max(0, self.monthly_limit - self.monthly_used)


@dataclass
class SendResult:
    """Result of sending a message."""

    message_id: str
    _client: Any = field(repr=False, default=None)
    _bot_id: str | None = field(repr=False, default=None)

    def wait_for_reply(self, timeout: int = 300, poll_interval: int = 3) -> Reply | None:
        """Block until a reply is received or timeout.

        Args:
            timeout: Max seconds to wait (default 300).
            poll_interval: Seconds between poll requests (default 3).

        Returns:
            The first reply to this message, or None on timeout.
        """
        if self._client is None:
            raise RuntimeError("wait_for_reply requires a client reference")
        return self._client._wait_for_reply(
            bot_id=self._bot_id,
            message_id=self.message_id,
            timeout=timeout,
            poll_interval=poll_interval,
        )
