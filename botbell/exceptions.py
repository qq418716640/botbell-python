"""BotBell exceptions."""

from __future__ import annotations

from typing import NoReturn


class BotBellError(Exception):
    """Base exception for BotBell SDK."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class AuthenticationError(BotBellError):
    """Invalid or expired token (40001)."""


class ForbiddenError(BotBellError):
    """Insufficient permissions (40003)."""


class NotFoundError(BotBellError):
    """Resource not found (40004)."""


class ValidationError(BotBellError):
    """Parameter validation failed (40010)."""


class RateLimitError(BotBellError):
    """Rate limit exceeded (40029)."""

    def __init__(
        self, message: str, code: int | None = None, retry_after: int | None = None
    ) -> None:
        super().__init__(message, code=code or 40029)
        self.retry_after = retry_after


class QuotaExceededError(BotBellError):
    """Monthly message quota exhausted (40030)."""


class BotPausedError(BotBellError):
    """Bot is paused (40033)."""


class ServerError(BotBellError):
    """Server-side error (50000)."""


# Error code → exception class mapping
_ERROR_MAP: dict[int, type[BotBellError]] = {
    40001: AuthenticationError,
    40003: ForbiddenError,
    40004: NotFoundError,
    40010: ValidationError,
    40029: RateLimitError,
    40030: QuotaExceededError,
    40033: BotPausedError,
    50000: ServerError,
}


def raise_for_error(code: int, message: str, cause: Exception | None = None) -> NoReturn:
    """Raise the appropriate exception for an error code."""
    exc_class = _ERROR_MAP.get(code, BotBellError)
    raise exc_class(message, code=code) from cause
