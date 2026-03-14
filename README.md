# BotBell Python SDK

Official Python SDK for [BotBell](https://botbell.app) — push notifications for AI agents and scripts.

**Zero dependencies.** Uses only Python standard library.

## Install

```bash
pip install botbell
```

## Quick Start

```python
from botbell import BotBell

bot = BotBell("bt_your_token")
bot.send("Deploy succeeded ✅")
```

## Send Rich Messages

```python
bot.send(
    "New order from Alice",
    title="Order #1234",
    url="https://dashboard.example.com/orders/1234",
    image_url="https://example.com/preview.png",
    format="markdown",
)
```

## Interactive Actions

```python
from botbell import BotBell, Action

bot = BotBell("bt_your_token")

result = bot.send(
    "Deploy v2.1.0 to production?",
    actions=[
        Action(key="approve", label="Approve"),
        Action(key="reject", label="Reject"),
    ],
)

# Wait for user's reply (blocks up to 5 minutes)
reply = result.wait_for_reply(timeout=300)
if reply and reply.action == "approve":
    deploy()
```

Or use the shorthand:

```python
reply = bot.send_and_wait(
    "Delete 3 duplicate records?",
    actions=[
        Action(key="yes", label="Yes"),
        Action(key="no", label="No"),
    ],
)
```

## Text Input Actions

```python
bot.send(
    "Build failed. What should we do?",
    actions=[
        Action(key="retry", label="Retry"),
        Action(key="comment", label="Add note", type="input", placeholder="Type a note..."),
    ],
)
```

## Poll Replies

```python
replies = bot.get_replies()
for reply in replies:
    print(f"{reply.action or reply.message}")
```

## PAT Mode (Multi-Bot)

Use a Personal Access Token to manage multiple bots:

```python
client = BotBell(pat="pak_your_token")

# List bots
bots = client.list_bots()

# Create a bot
new_bot = client.create_bot("Deploy Bot")

# Send via specific bot
client.send("Hello!", bot_id=new_bot.bot_id)

# Check quota
quota = client.get_quota()
print(f"{quota.plan}: {quota.messages_remaining} messages left")
```

## Webhook Signature Verification

When using `reply_url` (webhook), verify incoming requests to ensure they're from BotBell:

```python
from botbell import verify_webhook, WebhookVerificationError

# In your webhook handler (Flask/FastAPI/Django etc.)
try:
    verify_webhook(
        body=request.body,
        signature_header=request.headers["X-Webhook-Signature"],
        timestamp_header=request.headers["X-Webhook-Timestamp"],
        secret="your_webhook_secret",
    )
except WebhookVerificationError as e:
    return {"error": str(e)}, 401

# Signature valid — process the reply
data = json.loads(request.body)
```

The verification checks HMAC-SHA256 signature and rejects requests older than 5 minutes (configurable via `tolerance` parameter).

## API Reference

### `BotBell(token=None, *, pat=None, base_url=..., timeout=30)`

| Param | Description |
|-------|-------------|
| `token` | Bot Token (`bt_...`) for single-bot mode |
| `pat` | Personal Access Token (`pak_...`) for multi-bot mode |
| `base_url` | API base URL (default: `https://api.botbell.app/v1`) |
| `timeout` | HTTP request timeout in seconds |

### `send(message, *, title, url, image_url, summary, format, actions, actions_description, reply_mode, bot_id) → SendResult`

### `send_and_wait(message, *, timeout=300, poll_interval=3, bot_id, **kwargs) → Reply | None`

### `get_replies(*, bot_id) → list[Reply]`

### `list_bots() → list[Bot]` (PAT only)

### `create_bot(name, *, description=None, reply_url=None) → Bot` (PAT only)

### `get_bot(bot_id) → Bot` (PAT only)

### `update_bot(bot_id, *, name=None, description=None, reply_url=None, status=None) → Bot` (PAT only)

### `delete_bot(bot_id)` (PAT only)

### `reset_bot_token(bot_id) → str` (PAT only)

### `reset_webhook_secret(bot_id) → str` (PAT only)

### `get_quota() → Quota` (PAT only)

### `verify_webhook(body, signature_header, timestamp_header, secret, *, tolerance=300)`

Verifies webhook signature. Raises `WebhookVerificationError` on failure.

## Errors

All errors inherit from `BotBellError`:

| Exception | Code | Description |
|-----------|------|-------------|
| `AuthenticationError` | 40001 | Invalid or expired token |
| `ForbiddenError` | 40003 | Insufficient permissions |
| `NotFoundError` | 40004 | Resource not found |
| `ValidationError` | 40010 | Invalid parameters |
| `RateLimitError` | 40029 | Too many requests |
| `QuotaExceededError` | 40030 | Monthly message limit reached |
| `BotPausedError` | 40033 | Bot is paused |
| `ServerError` | 50000 | Server-side error |

## License

MIT
