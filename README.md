<a id="readme-top"></a>

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/elyase/simple-telegram-mcp"> 
    <img src="logo.png" alt="Logo" width="100" height="100">
  </a>

  <h3 align="center">Simple Telegram MCP</h3>

  <p align="center">
    The easiest way to use Telegram with MCP.
    <br />
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#available-tools">Available Tools</a></li>
  </ol>
</details>

<!-- GETTING STARTED -->
## Getting Started

### Login with Telegram

```bash
uvx simple-telegram-mcp --login
```

### Add to your MCP client

```bash
uvx simple-telegram-mcp --install cursor
```

<!-- AVAILABLE TOOLS -->
## Available Tools

The following tools are provided by this MCP server:

| Tool                           | Description                                                                 |
| ------------------------------ | --------------------------------------------------------------------------- |
| `telegram_add_reaction`        | Adds a reaction to a specific Telegram message.                             |
| `telegram_get_chat_history`    | Retrieves the message history for a given chat.                             |
| `telegram_get_user_profile`    | Fetches profile information for a Telegram user.                            |
| `telegram_list_chats`          | Lists the chats (conversations, groups, channels) the user is part of.      |
| `telegram_login_status`        | Checks the current login status of the Telegram client.                     |
| `telegram_post_message`        | Sends a new message to a specified chat.                                    |
| `telegram_reply_to_message`    | Sends a reply to a specific message within a chat.                          |
| `telegram_search_chats`        | Searches through the user's list of chats based on a query.                 |
| `search_telegram_messages`     | Searches for messages containing specific text within chats.                |

<p align="right">(<a href="#readme-top">back to top</a>)</p>
