"""Tests for the BotBell client."""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from botbell import BotBell
from botbell.exceptions import (
    AuthenticationError,
    BotBellError,
    BotPausedError,
    QuotaExceededError,
    RateLimitError,
    ValidationError,
)
from botbell.models import Action, Quota, SendResult

# ── Helpers ───────────────────────────────────────────────────────────


def _mock_response(data: dict, code: int = 200) -> MagicMock:
    body = json.dumps(data).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = code
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_http_error(data: dict, code: int = 400) -> urllib.error.HTTPError:
    body = json.dumps(data).encode()
    err = urllib.error.HTTPError(
        url="https://api.botbell.app/v1/test",
        code=code,
        msg="error",
        hdrs={},
        fp=BytesIO(body),
    )
    return err


# ── Init ──────────────────────────────────────────────────────────────


class TestInit:
    def test_bot_token_mode(self):
        client = BotBell("bt_test123")
        assert client.mode == "bot_token"

    def test_pat_mode(self):
        client = BotBell(pat="pak_test123")
        assert client.mode == "pat"

    def test_no_token_raises(self):
        with pytest.raises(ValueError, match="Provide a bot token or PAT"):
            BotBell()

    def test_both_tokens_raises(self):
        with pytest.raises(ValueError, match="not both"):
            BotBell("bt_x", pat="pak_y")

    def test_invalid_bot_token_prefix(self):
        with pytest.raises(ValueError, match="bt_"):
            BotBell("invalid_token")

    def test_invalid_pat_prefix(self):
        with pytest.raises(ValueError, match="pak_"):
            BotBell(pat="invalid_pat")

    def test_custom_base_url(self):
        client = BotBell("bt_test", base_url="http://localhost:8090/v1/")
        assert client._base_url == "http://localhost:8090/v1"


# ── Send ──────────────────────────────────────────────────────────────


class TestSend:
    @patch("botbell.client.urllib.request.urlopen")
    def test_send_bot_token(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"code": 0, "data": {"message_id": "msg_1", "bot_id": "bot_1"}}
        )
        client = BotBell("bt_test123")
        result = client.send("Hello")

        assert isinstance(result, SendResult)
        assert result.message_id == "msg_1"

        # Verify request
        req = mock_urlopen.call_args[0][0]
        assert "/push/bt_test123" in req.full_url
        assert req.method == "POST"
        body = json.loads(req.data)
        assert body["message"] == "Hello"

    @patch("botbell.client.urllib.request.urlopen")
    def test_send_pat_mode(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"code": 0, "data": {"message_id": "msg_2"}}
        )
        client = BotBell(pat="pak_test123")
        result = client.send("Hello", bot_id="bot_99")

        assert result.message_id == "msg_2"
        req = mock_urlopen.call_args[0][0]
        assert "/bots/bot_99/push" in req.full_url
        assert req.get_header("Authorization") == "Bearer pak_test123"

    def test_send_pat_requires_bot_id(self):
        client = BotBell(pat="pak_test123")
        with pytest.raises(ValueError, match="bot_id is required"):
            client.send("Hello")

    @patch("botbell.client.urllib.request.urlopen")
    def test_send_with_all_options(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"code": 0, "data": {"message_id": "msg_3", "bot_id": "bot_1"}}
        )
        client = BotBell("bt_test123")
        client.send(
            "Deploy to prod?",
            title="Deploy",
            url="https://example.com",
            image_url="https://example.com/img.png",
            summary="Deployment request",
            format="markdown",
            actions=[
                Action(key="yes", label="Approve"),
                {"key": "no", "label": "Reject"},
            ],
            actions_description="Choose an action",
            reply_mode="actions_only",
        )

        body = json.loads(mock_urlopen.call_args[0][0].data)
        assert body["title"] == "Deploy"
        assert body["url"] == "https://example.com"
        assert body["image_url"] == "https://example.com/img.png"
        assert body["summary"] == "Deployment request"
        assert body["format"] == "markdown"
        assert body["actions_description"] == "Choose an action"
        assert body["reply_mode"] == "actions_only"
        assert len(body["actions"]) == 2
        assert body["actions"][0] == {"key": "yes", "label": "Approve"}
        assert body["actions"][1] == {"key": "no", "label": "Reject"}

    @patch("botbell.client.urllib.request.urlopen")
    def test_send_bot_token_no_auth_header(self, mock_urlopen):
        """Bot token in URL mode should not send auth headers."""
        mock_urlopen.return_value = _mock_response(
            {"code": 0, "data": {"message_id": "msg_4", "bot_id": "bot_1"}}
        )
        client = BotBell("bt_test123")
        client.send("Hello")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") is None
        assert req.get_header("X-bot-token") is None


# ── Replies ───────────────────────────────────────────────────────────


class TestGetReplies:
    @patch("botbell.client.urllib.request.urlopen")
    def test_get_replies_bot_token(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {
                "code": 0,
                "data": {
                    "messages": [
                        {
                            "message_id": "r_1",
                            "content": "Yes",
                            "timestamp": 1700000000,
                            "action": "approve",
                            "reply_to": "msg_1",
                        }
                    ],
                    "has_more": False,
                },
            }
        )
        client = BotBell("bt_test123")
        replies = client.get_replies()

        assert len(replies) == 1
        assert replies[0].reply_id == "r_1"
        assert replies[0].message == "Yes"
        assert replies[0].action == "approve"
        assert replies[0].reply_to == "msg_1"

        req = mock_urlopen.call_args[0][0]
        assert "/messages/poll" in req.full_url
        assert req.get_header("X-bot-token") == "bt_test123"

    @patch("botbell.client.urllib.request.urlopen")
    def test_get_replies_pat(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"code": 0, "data": {"messages": [], "has_more": False}}
        )
        client = BotBell(pat="pak_test123")
        replies = client.get_replies(bot_id="bot_1")

        assert replies == []
        req = mock_urlopen.call_args[0][0]
        assert "/bots/bot_1/replies" in req.full_url

    def test_get_replies_pat_requires_bot_id(self):
        client = BotBell(pat="pak_test123")
        with pytest.raises(ValueError, match="bot_id is required"):
            client.get_replies()

    @patch("botbell.client.urllib.request.urlopen")
    def test_get_replies_empty(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"code": 0, "data": {"messages": [], "has_more": False}}
        )
        client = BotBell("bt_test123")
        assert client.get_replies() == []


# ── Bot management ────────────────────────────────────────────────────


class TestBotManagement:
    @patch("botbell.client.urllib.request.urlopen")
    def test_list_bots(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {
                "code": 0,
                "data": {
                    "bots": [
                        {
                            "bot_id": "bot_1",
                            "name": "Test Bot",
                            "description": "A test bot",
                            "status": "active",
                            "created_at": 1700000000,
                        }
                    ],
                    "total": 1,
                    "limit": 50,
                },
            }
        )
        client = BotBell(pat="pak_test123")
        bots = client.list_bots()

        assert len(bots) == 1
        assert bots[0].bot_id == "bot_1"
        assert bots[0].name == "Test Bot"
        assert bots[0].description == "A test bot"
        assert bots[0].is_active

    @patch("botbell.client.urllib.request.urlopen")
    def test_create_bot(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {
                "code": 0,
                "data": {
                    "bot_id": "bot_new",
                    "name": "My Bot",
                    "api_token": "bt_new123",
                    "push_url": "https://api.botbell.app/v1/push/bt_new123",
                    "webhook_secret": "whsec_abc123",
                },
            }
        )
        client = BotBell(pat="pak_test123")
        bot = client.create_bot("My Bot")

        assert bot.bot_id == "bot_new"
        assert bot.token == "bt_new123"
        assert bot.webhook_secret == "whsec_abc123"
        assert bot.push_url is not None

    @patch("botbell.client.urllib.request.urlopen")
    def test_create_bot_with_options(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"code": 0, "data": {"bot_id": "bot_new", "name": "My Bot"}}
        )
        client = BotBell(pat="pak_test123")
        client.create_bot("My Bot", description="Desc", reply_url="https://example.com/hook")

        body = json.loads(mock_urlopen.call_args[0][0].data)
        assert body["name"] == "My Bot"
        assert body["description"] == "Desc"
        assert body["reply_url"] == "https://example.com/hook"

    @patch("botbell.client.urllib.request.urlopen")
    def test_get_bot(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {
                "code": 0,
                "data": {
                    "bot_id": "bot_1",
                    "name": "Test Bot",
                    "api_token_hint": "bt_xxxx...xxxx",
                    "status": "active",
                },
            }
        )
        client = BotBell(pat="pak_test123")
        bot = client.get_bot("bot_1")
        assert bot.bot_id == "bot_1"
        assert bot.name == "Test Bot"

    @patch("botbell.client.urllib.request.urlopen")
    def test_update_bot(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"code": 0, "data": {"bot_id": "bot_1", "name": "New Name", "status": "paused"}}
        )
        client = BotBell(pat="pak_test123")
        bot = client.update_bot("bot_1", name="New Name", status="paused")

        assert bot.name == "New Name"
        assert not bot.is_active
        body = json.loads(mock_urlopen.call_args[0][0].data)
        assert body["name"] == "New Name"
        assert body["status"] == "paused"

    @patch("botbell.client.urllib.request.urlopen")
    def test_delete_bot(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"code": 0, "message": "success"})
        client = BotBell(pat="pak_test123")
        client.delete_bot("bot_1")

        req = mock_urlopen.call_args[0][0]
        assert req.method == "DELETE"
        assert "/bots/bot_1" in req.full_url

    @patch("botbell.client.urllib.request.urlopen")
    def test_reset_bot_token(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {
                "code": 0,
                "data": {
                    "api_token": "bt_new_rotated",
                    "push_url": "https://api.botbell.app/v1/push/bt_new_rotated",
                },
            }
        )
        client = BotBell(pat="pak_test123")
        result = client.reset_bot_token("bot_1")

        assert result["api_token"] == "bt_new_rotated"
        assert "push_url" in result
        req = mock_urlopen.call_args[0][0]
        assert "/bots/bot_1/reset-token" in req.full_url

    @patch("botbell.client.urllib.request.urlopen")
    def test_reset_webhook_secret(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"code": 0, "data": {"webhook_secret": "whsec_new_rotated"}}
        )
        client = BotBell(pat="pak_test123")
        new_secret = client.reset_webhook_secret("bot_1")

        assert new_secret == "whsec_new_rotated"
        req = mock_urlopen.call_args[0][0]
        assert "/bots/bot_1/reset-webhook-secret" in req.full_url

    @patch("botbell.client.urllib.request.urlopen")
    def test_get_quota(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {
                "code": 0,
                "data": {
                    "plan": "free",
                    "monthly_limit": 300,
                    "used": 42,
                    "remaining": 258,
                    "reset_at": 1700000000,
                },
            }
        )
        client = BotBell(pat="pak_test123")
        quota = client.get_quota()

        assert quota.plan == "free"
        assert quota.monthly_limit == 300
        assert quota.used == 42
        assert quota.remaining == 258
        assert quota.reset_at == 1700000000

    def test_bot_management_requires_pat(self):
        client = BotBell("bt_test123")
        with pytest.raises(BotBellError, match="requires PAT mode"):
            client.list_bots()
        with pytest.raises(BotBellError, match="requires PAT mode"):
            client.create_bot("test")
        with pytest.raises(BotBellError, match="requires PAT mode"):
            client.get_bot("bot_1")
        with pytest.raises(BotBellError, match="requires PAT mode"):
            client.update_bot("bot_1", name="x")
        with pytest.raises(BotBellError, match="requires PAT mode"):
            client.delete_bot("bot_1")
        with pytest.raises(BotBellError, match="requires PAT mode"):
            client.reset_bot_token("bot_1")
        with pytest.raises(BotBellError, match="requires PAT mode"):
            client.reset_webhook_secret("bot_1")
        with pytest.raises(BotBellError, match="requires PAT mode"):
            client.get_quota()


# ── Error handling ────────────────────────────────────────────────────


class TestErrorHandling:
    @patch("botbell.client.urllib.request.urlopen")
    def test_authentication_error(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_http_error(
            {"code": 40001, "message": "Invalid token"}, 401
        )
        client = BotBell("bt_test123")
        with pytest.raises(AuthenticationError, match="Invalid token"):
            client.send("Hello")

    @patch("botbell.client.urllib.request.urlopen")
    def test_rate_limit_error(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_http_error(
            {"code": 40029, "message": "Rate limit exceeded"}, 429
        )
        client = BotBell("bt_test123")
        with pytest.raises(RateLimitError):
            client.send("Hello")

    @patch("botbell.client.urllib.request.urlopen")
    def test_quota_exceeded_error(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_http_error(
            {"code": 40030, "message": "Monthly quota exhausted"}, 403
        )
        client = BotBell("bt_test123")
        with pytest.raises(QuotaExceededError):
            client.send("Hello")

    @patch("botbell.client.urllib.request.urlopen")
    def test_bot_paused_error(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_http_error(
            {"code": 40033, "message": "Bot is paused"}, 403
        )
        client = BotBell("bt_test123")
        with pytest.raises(BotPausedError):
            client.send("Hello")

    @patch("botbell.client.urllib.request.urlopen")
    def test_validation_error(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_http_error(
            {"code": 40010, "message": "message is required"}, 400
        )
        client = BotBell("bt_test123")
        with pytest.raises(ValidationError):
            client.send("")

    @patch("botbell.client.urllib.request.urlopen")
    def test_unknown_error_code(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_http_error(
            {"code": 99999, "message": "Something weird"}, 500
        )
        client = BotBell("bt_test123")
        with pytest.raises(BotBellError, match="Something weird") as exc_info:
            client.send("Hello")
        assert exc_info.value.code == 99999

    @patch("botbell.client.urllib.request.urlopen")
    def test_non_json_error(self, mock_urlopen):
        err = urllib.error.HTTPError(
            url="https://api.botbell.app/v1/test",
            code=502,
            msg="Bad Gateway",
            hdrs={},
            fp=BytesIO(b"<html>Bad Gateway</html>"),
        )
        mock_urlopen.side_effect = err
        client = BotBell("bt_test123")
        with pytest.raises(BotBellError, match="HTTP 502"):
            client.send("Hello")

    @patch("botbell.client.urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        client = BotBell("bt_test123")
        with pytest.raises(BotBellError, match="Connection error"):
            client.send("Hello")


# ── Models ────────────────────────────────────────────────────────────


class TestModels:
    def test_action_to_dict_default(self):
        a = Action(key="ok", label="OK")
        assert a.to_dict() == {"key": "ok", "label": "OK"}

    def test_action_to_dict_input(self):
        a = Action(key="comment", label="Comment", type="input", placeholder="Type here")
        d = a.to_dict()
        assert d["type"] == "input"
        assert d["placeholder"] == "Type here"

    def test_quota_fields(self):
        q = Quota(plan="free", monthly_limit=300, used=42, remaining=258, reset_at=1700000000)
        assert q.plan == "free"
        assert q.monthly_limit == 300
        assert q.used == 42
        assert q.remaining == 258
        assert q.reset_at == 1700000000

    def test_bot_is_active(self):
        from botbell.models import Bot

        active = Bot(bot_id="1", name="a", status="active")
        paused = Bot(bot_id="2", name="b", status="paused")
        assert active.is_active
        assert not paused.is_active


# ── send_and_wait ─────────────────────────────────────────────────────


class TestSendAndWait:
    @patch("botbell.client.time.sleep")
    @patch("botbell.client.urllib.request.urlopen")
    def test_send_and_wait_gets_reply(self, mock_urlopen, mock_sleep):
        # First call: send; Second call: poll returns reply
        mock_urlopen.side_effect = [
            _mock_response(
                {"code": 0, "data": {"message_id": "msg_1", "bot_id": "bot_1"}}
            ),
            _mock_response(
                {
                    "code": 0,
                    "data": {
                        "messages": [
                            {
                                "message_id": "r_1",
                                "content": "Yes",
                                "action": "approve",
                                "reply_to": "msg_1",
                            }
                        ],
                        "has_more": False,
                    },
                }
            ),
        ]
        client = BotBell("bt_test123")
        reply = client.send_and_wait("Approve?", timeout=10)

        assert reply is not None
        assert reply.message == "Yes"
        assert reply.action == "approve"

    @patch("botbell.client.time.sleep")
    @patch("botbell.client.urllib.request.urlopen")
    def test_send_and_wait_preserves_other_replies(self, mock_urlopen, mock_sleep):
        """Replies for other messages should be buffered, not lost."""
        mock_urlopen.side_effect = [
            # send
            _mock_response(
                {"code": 0, "data": {"message_id": "msg_1", "bot_id": "bot_1"}}
            ),
            # first poll: reply before match, the match, and reply after match
            _mock_response(
                {
                    "code": 0,
                    "data": {
                        "messages": [
                            {
                                "message_id": "r_before",
                                "content": "Before",
                                "reply_to": "msg_other",
                            },
                            {
                                "message_id": "r_1",
                                "content": "Yes",
                                "reply_to": "msg_1",
                            },
                            {
                                "message_id": "r_after",
                                "content": "After",
                                "reply_to": "msg_another",
                            },
                        ],
                        "has_more": False,
                    },
                }
            ),
            # subsequent get_replies call
            _mock_response(
                {"code": 0, "data": {"messages": [], "has_more": False}}
            ),
        ]
        client = BotBell("bt_test123")
        reply = client.send_and_wait("Approve?", timeout=10)

        assert reply is not None
        assert reply.reply_to == "msg_1"

        # Both non-matched replies (before AND after match) should be preserved
        remaining = client.get_replies()
        assert len(remaining) == 2
        assert remaining[0].reply_id == "r_before"
        assert remaining[1].reply_id == "r_after"

    @patch("botbell.client.time.sleep")
    @patch("botbell.client.urllib.request.urlopen")
    def test_send_and_wait_timeout(self, mock_urlopen, mock_sleep):
        # send returns msg_1, first poll returns empty, second poll also empty
        mock_urlopen.side_effect = [
            _mock_response(
                {"code": 0, "data": {"message_id": "msg_1", "bot_id": "bot_1"}}
            ),
            _mock_response(
                {"code": 0, "data": {"messages": [], "has_more": False}}
            ),
        ]
        client = BotBell("bt_test123")
        # Use very short timeout so it exits after one poll cycle
        reply = client.send_and_wait("Hello?", timeout=0)

        assert reply is None
