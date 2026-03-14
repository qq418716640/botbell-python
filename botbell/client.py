"""BotBell client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from botbell._version import __version__
from botbell.exceptions import BotBellError, raise_for_error
from botbell.models import Action, Bot, Quota, Reply, SendResult

DEFAULT_BASE_URL = "https://api.botbell.app/v1"
_USER_AGENT = f"botbell-python/{__version__}"


class BotBell:
    """BotBell SDK client.

    Supports two authentication modes:
    - Bot Token (bt_...): single-bot operations (send, get_replies)
    - Personal Access Token (pak_...): multi-bot management

    Usage::

        # Bot Token mode — simplest
        bot = BotBell("bt_xxx")
        bot.send("Hello!")

        # PAT mode — manage multiple bots
        client = BotBell(pat="pak_xxx")
        client.send("Hello!", bot_id="bot_123")
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        pat: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
    ) -> None:
        if token and pat:
            raise ValueError("Provide either token or pat, not both")
        if not token and not pat:
            raise ValueError("Provide a bot token or PAT")

        self._token = token
        self._pat = pat
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._pending_replies: list[Reply] = []

        # Detect mode
        if token:
            if not token.startswith("bt_"):
                raise ValueError("Bot token must start with 'bt_'")
            self._mode = "bot_token"
        else:
            if not pat.startswith("pak_"):
                raise ValueError("PAT must start with 'pak_'")
            self._mode = "pat"

    @property
    def mode(self) -> str:
        """Return authentication mode: 'bot_token' or 'pat'."""
        return self._mode

    # ── Sending messages ──────────────────────────────────────────────

    def send(
        self,
        message: str,
        *,
        title: str | None = None,
        url: str | None = None,
        image_url: str | None = None,
        summary: str | None = None,
        format: str | None = None,
        actions: list[Action | dict] | None = None,
        actions_description: str | None = None,
        reply_mode: str | None = None,
        bot_id: str | None = None,
    ) -> SendResult:
        """Send a push notification.

        Args:
            message: Message body (required, max 4096 chars).
            title: Optional title (max 256 chars).
            url: Optional URL to attach (max 2048 chars).
            image_url: Optional image URL (max 2048 chars).
            summary: Optional summary (max 512 chars).
            format: Message format — "text" (default) or "markdown".
            actions: List of reply actions (buttons/inputs).
            actions_description: Help text shown above action buttons.
            reply_mode: Reply mode — "open", "actions_only", or "none".
            bot_id: Required in PAT mode, ignored in bot token mode.

        Returns:
            SendResult with message_id and wait_for_reply() method.
        """
        body: dict[str, Any] = {"message": message}
        if title is not None:
            body["title"] = title
        if url is not None:
            body["url"] = url
        if image_url is not None:
            body["image_url"] = image_url
        if summary is not None:
            body["summary"] = summary
        if format is not None:
            body["format"] = format
        if actions is not None:
            body["actions"] = [
                a.to_dict() if isinstance(a, Action) else a for a in actions
            ]
        if actions_description is not None:
            body["actions_description"] = actions_description
        if reply_mode is not None:
            body["reply_mode"] = reply_mode

        if self._mode == "bot_token":
            path = f"/push/{self._token}"
            resp = self._request("POST", path, body=body, auth=False)
        else:
            if not bot_id:
                raise ValueError("bot_id is required in PAT mode")
            path = f"/bots/{bot_id}/push"
            resp = self._request("POST", path, body=body)

        resolved_bot_id = bot_id or resp.get("data", {}).get("bot_id")
        return SendResult(
            message_id=resp["data"]["message_id"],
            _client=self,
            _bot_id=resolved_bot_id,
        )

    def send_and_wait(
        self,
        message: str,
        *,
        timeout: int = 300,
        poll_interval: int = 3,
        bot_id: str | None = None,
        **kwargs: Any,
    ) -> Reply | None:
        """Send a message and block until a reply is received.

        Args:
            message: Message body.
            timeout: Max seconds to wait for reply (default 300).
            poll_interval: Seconds between poll requests (default 3).
            bot_id: Required in PAT mode.
            **kwargs: Additional arguments passed to send().

        Returns:
            The first reply to this message, or None on timeout.
        """
        result = self.send(message, bot_id=bot_id, **kwargs)
        return result.wait_for_reply(timeout=timeout, poll_interval=poll_interval)

    # ── Replies ───────────────────────────────────────────────────────

    def get_replies(self, *, bot_id: str | None = None) -> list[Reply]:
        """Poll for user replies.

        Args:
            bot_id: Required in PAT mode, ignored in bot token mode.

        Returns:
            List of Reply objects (includes any buffered replies from
            prior send_and_wait calls).
        """
        # Drain any replies buffered by send_and_wait
        replies = list(self._pending_replies)
        self._pending_replies.clear()

        replies.extend(self._poll_raw(bot_id=bot_id))
        return replies

    def _poll_raw(self, *, bot_id: str | None = None) -> list[Reply]:
        """Fetch replies from the API without draining pending buffer."""
        if self._mode == "bot_token":
            path = "/messages/poll"
            resp = self._request("GET", path)
        else:
            if not bot_id:
                raise ValueError("bot_id is required in PAT mode")
            path = f"/bots/{bot_id}/replies"
            resp = self._request("GET", path)

        return [
            Reply(
                reply_id=item.get("reply_id", ""),
                bot_id=item.get("bot_id", ""),
                message=item.get("message", ""),
                timestamp=item.get("timestamp", 0),
                action=item.get("action"),
                reply_to=item.get("reply_to"),
            )
            for item in resp.get("data", [])
        ]

    # ── Bot management (PAT mode only) ────────────────────────────────

    def list_bots(self) -> list[Bot]:
        """List all bots. PAT mode only."""
        self._require_pat("list_bots")
        resp = self._request("GET", "/bots")
        data = resp.get("data", {})
        bots_list = data.get("bots", []) if isinstance(data, dict) else data
        return [self._parse_bot(item) for item in bots_list]

    def create_bot(
        self,
        name: str,
        *,
        description: str | None = None,
        reply_url: str | None = None,
    ) -> Bot:
        """Create a new bot. PAT mode only.

        Args:
            name: Bot display name (max 50 chars).
            description: Bot description (max 200 chars).
            reply_url: Webhook URL for user replies (max 512 chars).

        Returns:
            The created Bot (includes token, push_url, and webhook_secret).
        """
        self._require_pat("create_bot")
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if reply_url is not None:
            body["reply_url"] = reply_url
        resp = self._request("POST", "/bots", body=body)
        return self._parse_bot(resp["data"])

    def get_bot(self, bot_id: str) -> Bot:
        """Get bot details. PAT mode only.

        Args:
            bot_id: Bot identifier.

        Returns:
            Bot details (token is masked as hint).
        """
        self._require_pat("get_bot")
        resp = self._request("GET", f"/bots/{bot_id}")
        return self._parse_bot(resp["data"])

    def update_bot(
        self,
        bot_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        reply_url: str | None = None,
        status: str | None = None,
    ) -> Bot:
        """Update a bot. PAT mode only.

        Args:
            bot_id: Bot identifier.
            name: New display name.
            description: New description.
            reply_url: New webhook URL for replies.
            status: "active" or "paused".

        Returns:
            Updated Bot details.
        """
        self._require_pat("update_bot")
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if reply_url is not None:
            body["reply_url"] = reply_url
        if status is not None:
            body["status"] = status
        resp = self._request("PATCH", f"/bots/{bot_id}", body=body)
        return self._parse_bot(resp["data"])

    def delete_bot(self, bot_id: str) -> None:
        """Delete a bot. PAT mode only.

        Args:
            bot_id: Bot identifier.
        """
        self._require_pat("delete_bot")
        self._request("DELETE", f"/bots/{bot_id}")

    def reset_bot_token(self, bot_id: str) -> str:
        """Reset a bot's API token. PAT mode only.

        The old token is invalidated immediately.

        Args:
            bot_id: Bot identifier.

        Returns:
            The new API token string.
        """
        self._require_pat("reset_bot_token")
        resp = self._request("POST", f"/bots/{bot_id}/reset-token")
        return resp["data"]["api_token"]

    def reset_webhook_secret(self, bot_id: str) -> str:
        """Reset a bot's webhook secret. PAT mode only.

        Args:
            bot_id: Bot identifier.

        Returns:
            The new webhook secret string.
        """
        self._require_pat("reset_webhook_secret")
        resp = self._request("POST", f"/bots/{bot_id}/reset-webhook-secret")
        return resp["data"]["webhook_secret"]

    def get_quota(self) -> Quota:
        """Get current message quota. PAT mode only."""
        self._require_pat("get_quota")
        resp = self._request("GET", "/account/quota")
        data = resp["data"]
        return Quota(
            plan=data.get("plan", "free"),
            monthly_limit=data.get("monthly_limit"),
            monthly_used=data.get("monthly_used", 0),
            bot_limit=data.get("bot_limit", 3),
            bot_used=data.get("bot_used", 0),
        )

    # ── Internal ──────────────────────────────────────────────────────

    def _require_pat(self, method: str) -> None:
        if self._mode != "pat":
            raise BotBellError(f"{method}() requires PAT mode")

    def _wait_for_reply(
        self,
        *,
        bot_id: str | None,
        message_id: str,
        timeout: int,
        poll_interval: int,
    ) -> Reply | None:
        """Poll for a reply to a specific message.

        Note: The poll API is destructive (replies are dequeued).
        Any replies not matching the target message_id are stored in
        ``_pending_replies`` so they can be returned by future
        ``get_replies()`` calls.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            replies = self._poll_raw(bot_id=bot_id)
            matched: Reply | None = None
            for reply in replies:
                if matched is None and reply.reply_to == message_id:
                    matched = reply
                else:
                    # Preserve all non-matched replies (including those
                    # after the match in the same batch)
                    self._pending_replies.append(reply)
            if matched is not None:
                return matched
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        return None

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        auth: bool = True,
    ) -> dict:
        """Make an HTTP request to the BotBell API."""
        url = self._base_url + path
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }

        if auth:
            if self._mode == "pat":
                headers["Authorization"] = f"Bearer {self._pat}"
            else:
                headers["X-Bot-Token"] = self._token

        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                resp_body = resp.read().decode("utf-8")
                return json.loads(resp_body) if resp_body else {}
        except urllib.error.HTTPError as e:
            resp_body = e.read().decode("utf-8")
            try:
                error_data = json.loads(resp_body)
                code = error_data.get("code", e.code)
                message = error_data.get("message", str(e))
            except (json.JSONDecodeError, KeyError):
                raise BotBellError(f"HTTP {e.code}: {resp_body}", code=e.code) from e
            raise_for_error(code, message, cause=e)
        except urllib.error.URLError as e:
            raise BotBellError(f"Connection error: {e.reason}") from e
        except TimeoutError as e:
            raise BotBellError(
                f"Request timed out after {self._timeout}s"
            ) from e

    @staticmethod
    def _parse_bot(data: dict) -> Bot:
        return Bot(
            bot_id=data.get("bot_id", ""),
            name=data.get("name", ""),
            description=data.get("description"),
            token=data.get("token") or data.get("api_token"),
            webhook_secret=data.get("webhook_secret"),
            push_url=data.get("push_url"),
            reply_url=data.get("reply_url"),
            status=data.get("status"),
            created_at=data.get("created_at", 0),
        )
