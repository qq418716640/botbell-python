"""Webhook signature verification utilities."""

from __future__ import annotations

import hashlib
import hmac
import time


class WebhookVerificationError(Exception):
    """Raised when webhook signature verification fails."""


def verify_webhook(
    body: str | bytes,
    signature_header: str,
    timestamp_header: str,
    secret: str,
    *,
    tolerance: int = 300,
) -> None:
    """Verify a BotBell webhook signature.

    Args:
        body: Raw request body (string or bytes).
        signature_header: Value of X-Webhook-Signature header.
        timestamp_header: Value of X-Webhook-Timestamp header.
        secret: Your bot's webhook secret.
        tolerance: Max allowed age in seconds (default 300 = 5 min).

    Raises:
        WebhookVerificationError: If signature is invalid or timestamp expired.
    """
    # Validate timestamp
    try:
        ts = int(timestamp_header)
    except (ValueError, TypeError):
        raise WebhookVerificationError("Invalid timestamp header")

    if abs(time.time() - ts) > tolerance:
        raise WebhookVerificationError("Timestamp outside tolerance window")

    # Compute expected signature
    if isinstance(body, str):
        body = body.encode("utf-8")

    payload = f"{ts}.".encode("utf-8") + body
    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Parse "sha256=..." from header
    sig = signature_header
    if sig.startswith("sha256="):
        sig = sig[7:]

    if not hmac.compare_digest(expected, sig):
        raise WebhookVerificationError("Signature mismatch")
