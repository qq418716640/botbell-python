"""BotBell — Push notifications for AI agents and scripts."""

from botbell._version import __version__
from botbell.client import BotBell
from botbell.exceptions import (
    AuthenticationError,
    BotBellError,
    BotPausedError,
    ForbiddenError,
    NotFoundError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from botbell.models import Action, Bot, Quota, Reply, SendResult
from botbell.webhook import WebhookVerificationError, verify_webhook

__all__ = [
    "__version__",
    "BotBell",
    "Action",
    "Bot",
    "Quota",
    "Reply",
    "SendResult",
    "BotBellError",
    "AuthenticationError",
    "ForbiddenError",
    "NotFoundError",
    "RateLimitError",
    "QuotaExceededError",
    "BotPausedError",
    "ServerError",
    "ValidationError",
    "verify_webhook",
    "WebhookVerificationError",
]
