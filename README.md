<a id="top"></a>

<div align="center">
  <a href="https://github.com/elyase/simple-telegram-mcp">
    <img src="logo.png" alt="Logo" width="110" height="110">
  </a>

  <h1>Simple Telegram MCP</h1>
</div>

## ✨ Example use cases

- **Automate tasks**: “Look up the weather forecast and send it to my family group”
- **Stay on top of things**: “Review my unread messages, give me the highlights, and queue polite replies”
- **Polish before sending**: “Read Tony’s latest note in the Family channel, craft three informal reply drafts, and leave them for me to send.”


## 🚀 Quick Start

### Automatic client configuration

| Client            | Command                                           |
|-------------------|---------------------------------------------------|
| Cursor            | `uvx simple-telegram-mcp --install cursor`        |
| Claude Desktop    | `uvx simple-telegram-mcp --install claude-desktop`|
| Claude Code       | `uvx simple-telegram-mcp --install claude-code`   |
| Gemini CLI        | `uvx simple-telegram-mcp --install gemini-cli`    |
| MCP JSON (stdout) | `uvx simple-telegram-mcp --install mcp-json`      |
| OpenAI Codex CLI  | `uvx simple-telegram-mcp --install codex-cli`     |

### Authorize Telegram

```bash
uvx simple-telegram-mcp --login
```

>
> ✨ Heads-up: the login flow is zero drama. You’ll pop in your phone number, Telegram will DM you a code, you paste it back here, and you’re in.

## 🛠️ Tools

| Tool                     | Description                                                                 |
|--------------------------|-----------------------------------------------------------------------------|
| `telegram_add_reaction`  | Adds an emoji reaction to a specific message.                               |
| `telegram_get_chat_history` | Retrieves recent messages for a chat.                                    |
| `telegram_get_draft`     | Returns the current unsent draft for a chat, if one exists.                 |
| `telegram_get_user_profile` | Fetches profile information for a user.                                 |
| `telegram_list_chats`    | Lists dialogs (DMs, groups, channels) the account can access.               |
| `telegram_login_status`  | Reports connection and authorization status.                               |
| `telegram_post_message`  | Sends a new message to a chat.                                             |
| `telegram_reply_to_message` | Replies to a message by ID.                                             |
| `telegram_save_draft`    | Stores or updates a draft message without sending it.                      |
| `telegram_search_chats`  | Finds chats by partial name or username.                                   |
| `search_telegram_messages` | Searches globally (or within a chat) for messages containing text.      |

## 🧾 Resources

| Resource URI                       | Description                                                   |
|-----------------------------------|---------------------------------------------------------------|
| `telegram://chats`                | Latest 25 dialogs with names, types, and unread counts.       |
| `telegram://session/status`       | Connection and authorization snapshot.                        |
| `telegram://chats/{chat_id}/unread` | Incoming unread messages for a chat (oldest first).         |
| `telegram://chats/{chat_id}/history` | Recent message history for a chat.                         |

## 🧠 Prompts

- `telegram/draft-reply` – Generates a concise reply in the tone you request.
- `telegram/check-session` – Reminds the assistant to verify the session before doing anything else.


## ✅ Testing

- Fast unit tests (default): `uv run pytest -q`
- Integration tests: `RUN_TELEGRAM_TESTS=1 uv run pytest -m integration -q` (make sure to log in first: `uvx simple-telegram-mcp --login`)

<p align="right">(<a href="#top">back to top</a>)</p>
