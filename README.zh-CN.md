[English](README.md) | [中文](README.zh-CN.md)

# BotBell Python SDK

[![PyPI](https://img.shields.io/pypi/v/botbell)](https://pypi.org/project/botbell/)
[![Python](https://img.shields.io/pypi/pyversions/botbell)](https://pypi.org/project/botbell/)
[![License](https://img.shields.io/github/license/qq418716640/botbell-python)](https://github.com/qq418716640/botbell-python/blob/main/LICENSE)
[![CI](https://github.com/qq418716640/botbell-python/actions/workflows/ci.yml/badge.svg)](https://github.com/qq418716640/botbell-python/actions/workflows/ci.yml)

[BotBell](https://botbell.app) 官方 Python SDK —— 为 AI 智能体和脚本提供推送通知。

**零依赖。** 仅使用 Python 标准库。

## 安装

```bash
pip install botbell
```

## 快速开始

```python
from botbell import BotBell

bot = BotBell("bt_your_token")
bot.send("部署成功 ✅")
```

## 发送富文本消息

```python
bot.send(
    "Alice 的新订单",
    title="订单 #1234",
    url="https://dashboard.example.com/orders/1234",
    image_url="https://example.com/preview.png",
    format="markdown",
)
```

## 交互式 Actions

```python
from botbell import BotBell, Action

bot = BotBell("bt_your_token")

result = bot.send(
    "将 v2.1.0 部署到生产环境？",
    actions=[
        Action(key="approve", label="批准"),
        Action(key="reject", label="拒绝"),
    ],
)

# 等待用户回复（最多等 5 分钟）
reply = result.wait_for_reply(timeout=300)
if reply and reply.action == "approve":
    deploy()
```

或使用简写方式：

```python
reply = bot.send_and_wait(
    "删除 3 条重复记录？",
    actions=[
        Action(key="yes", label="是"),
        Action(key="no", label="否"),
    ],
)
```

## 文本输入 Actions

```python
bot.send(
    "构建失败，怎么处理？",
    actions=[
        Action(key="retry", label="重试"),
        Action(key="comment", label="添加备注", type="input", placeholder="输入备注..."),
    ],
)
```

## 轮询回复

```python
replies = bot.get_replies()
for reply in replies:
    print(f"{reply.action or reply.message}")
```

## PAT 模式（多 Bot）

使用个人访问令牌管理多个 Bot：

```python
client = BotBell(pat="pak_your_token")

# 列出 Bot
bots = client.list_bots()

# 创建 Bot
new_bot = client.create_bot("Deploy Bot")

# 通过指定 Bot 发送
client.send("Hello!", bot_id=new_bot.bot_id)

# 查看配额
quota = client.get_quota()
print(f"{quota.plan}: 剩余 {quota.remaining}/{quota.monthly_limit} 条消息")
```

## Webhook 签名验证

使用 `reply_url`（Webhook）时，验证请求来源确实是 BotBell：

```python
from botbell import verify_webhook, WebhookVerificationError

# 在你的 Webhook 处理器中（Flask/FastAPI/Django 等）
try:
    verify_webhook(
        body=request.body,
        signature_header=request.headers["X-Webhook-Signature"],
        timestamp_header=request.headers["X-Webhook-Timestamp"],
        secret="your_webhook_secret",
    )
except WebhookVerificationError as e:
    return {"error": str(e)}, 401

# 签名验证通过 — 处理回复
data = json.loads(request.body)
```

验证使用 HMAC-SHA256 签名，并拒绝超过 5 分钟的请求（可通过 `tolerance` 参数配置）。

## API 参考

### `BotBell(token=None, *, pat=None, base_url=..., timeout=30)`

| 参数 | 说明 |
|------|------|
| `token` | Bot Token（`bt_...`），单 Bot 模式 |
| `pat` | 个人访问令牌（`pak_...`），多 Bot 模式 |
| `base_url` | API 基础 URL（默认：`https://api.botbell.app/v1`） |
| `timeout` | HTTP 请求超时秒数 |

### `send(message, *, title, url, image_url, summary, format, actions, actions_description, reply_mode, bot_id) → SendResult`

### `send_and_wait(message, *, timeout=300, poll_interval=3, bot_id, **kwargs) → Reply | None`

### `get_replies(*, bot_id) → list[Reply]`

### `list_bots() → list[Bot]`（仅 PAT）

### `create_bot(name, *, description=None, reply_url=None) → Bot`（仅 PAT）

### `get_bot(bot_id) → Bot`（仅 PAT）

### `update_bot(bot_id, *, name=None, description=None, reply_url=None, status=None) → Bot`（仅 PAT）

### `delete_bot(bot_id)`（仅 PAT）

### `reset_bot_token(bot_id) → str`（仅 PAT）

### `reset_webhook_secret(bot_id) → str`（仅 PAT）

### `get_quota() → Quota`（仅 PAT）

### `verify_webhook(body, signature_header, timestamp_header, secret, *, tolerance=300)`

验证 Webhook 签名。失败时抛出 `WebhookVerificationError`。

## 错误处理

所有错误继承自 `BotBellError`：

| 异常 | 错误码 | 说明 |
|------|--------|------|
| `AuthenticationError` | 40001 | Token 无效或已过期 |
| `ForbiddenError` | 40003 | 权限不足 |
| `NotFoundError` | 40004 | 资源不存在 |
| `ValidationError` | 40010 | 参数无效 |
| `RateLimitError` | 40029 | 请求过于频繁 |
| `QuotaExceededError` | 40030 | 月度消息配额已用完 |
| `BotPausedError` | 40033 | Bot 已暂停 |
| `ServerError` | 50000 | 服务端错误 |

## 许可证

MIT
