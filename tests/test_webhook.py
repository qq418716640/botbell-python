"""Tests for webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from botbell.webhook import WebhookVerificationError, verify_webhook

SECRET = "whsec_test_secret_123"


def _sign(body: str, ts: int, secret: str = SECRET) -> str:
    payload = f"{ts}.{body}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"sha256={sig}"


class TestVerifyWebhook:
    def test_valid_signature(self):
        body = '{"reply_id":"r_1","message":"Yes"}'
        ts = int(time.time())
        sig = _sign(body, ts)

        # Should not raise
        verify_webhook(body, sig, str(ts), SECRET)

    def test_valid_signature_bytes_body(self):
        body = '{"reply_id":"r_1","message":"Yes"}'
        ts = int(time.time())
        sig = _sign(body, ts)

        verify_webhook(body.encode("utf-8"), sig, str(ts), SECRET)

    def test_invalid_signature(self):
        body = '{"reply_id":"r_1"}'
        ts = int(time.time())

        with pytest.raises(WebhookVerificationError, match="Signature mismatch"):
            verify_webhook(body, "sha256=invalid_hex", str(ts), SECRET)

    def test_wrong_secret(self):
        body = '{"reply_id":"r_1"}'
        ts = int(time.time())
        sig = _sign(body, ts, secret="wrong_secret")

        with pytest.raises(WebhookVerificationError, match="Signature mismatch"):
            verify_webhook(body, sig, str(ts), SECRET)

    def test_tampered_body(self):
        body = '{"reply_id":"r_1"}'
        ts = int(time.time())
        sig = _sign(body, ts)

        with pytest.raises(WebhookVerificationError, match="Signature mismatch"):
            verify_webhook('{"reply_id":"r_TAMPERED"}', sig, str(ts), SECRET)

    def test_expired_timestamp(self):
        body = '{"reply_id":"r_1"}'
        ts = int(time.time()) - 600  # 10 minutes ago
        sig = _sign(body, ts)

        with pytest.raises(WebhookVerificationError, match="Timestamp outside tolerance"):
            verify_webhook(body, sig, str(ts), SECRET)

    def test_future_timestamp(self):
        body = '{"reply_id":"r_1"}'
        ts = int(time.time()) + 600  # 10 minutes in the future
        sig = _sign(body, ts)

        with pytest.raises(WebhookVerificationError, match="Timestamp outside tolerance"):
            verify_webhook(body, sig, str(ts), SECRET)

    def test_invalid_timestamp(self):
        with pytest.raises(WebhookVerificationError, match="Invalid timestamp"):
            verify_webhook("{}", "sha256=abc", "not_a_number", SECRET)

    def test_custom_tolerance(self):
        body = '{"reply_id":"r_1"}'
        ts = int(time.time()) - 10  # 10 seconds ago
        sig = _sign(body, ts)

        # Should fail with 5-second tolerance
        with pytest.raises(WebhookVerificationError, match="Timestamp outside tolerance"):
            verify_webhook(body, sig, str(ts), SECRET, tolerance=5)

        # Should pass with 30-second tolerance
        verify_webhook(body, sig, str(ts), SECRET, tolerance=30)

    def test_signature_without_prefix(self):
        """Signature without sha256= prefix should also work."""
        body = '{"reply_id":"r_1"}'
        ts = int(time.time())
        sig = _sign(body, ts)
        raw_sig = sig.removeprefix("sha256=")

        verify_webhook(body, raw_sig, str(ts), SECRET)
