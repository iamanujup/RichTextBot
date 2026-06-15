# RichTextBot 

A Telegram bot ([try it](https://t.me/richtextprobot)) that renders Markdown and HTML as native **Telegram Rich Messages** (Bot API 10.1).  
Send any `.md` file, `.html` file, or paste raw text — the bot resends it as a fully rendered rich message with tables, LaTeX, headings, collapsibles, and more.

---

## Features

- **Markdown → Rich Message** — full GFM support: headings, tables, task lists, footnotes, block quotes
- **HTML → Rich Message** — all Bot API 10.1 HTML tags: `<details>`, `<tg-spoiler>`, `<tg-math-block>`, `<sup>`, `<sub>`, tables, collages, etc.
- **File upload** — send `.md` or `.html` file directly
- **Auto-detect** — no need to specify mode; bot guesses from content
- **Force mode** — `/md` or `/html` commands to override
- **Fallback** — if one mode fails, automatically tries the other

## Supported Formatting

### Rich Markdown
| Feature | Syntax |
|---|---|
| Headings | `# H1` … `###### H6` |
| Bold / Italic | `**bold**` / `*italic*` |
| Strikethrough | `~~text~~` |
| Marked | `==text==` |
| Spoiler | `\|\|text\|\|` |
| Inline code | `` `code` `` |
| Code block | ` ```lang\ncode\n``` ` |
| Inline math | `$x^2 + y^2$` |
| Block math | `$$E = mc^2$$` |
| GFM table | `\| Col \| Col \|` |
| Task list | `- [ ]` / `- [x]` |
| Block quote | `> text` |
| Footnotes | `text[^1]` + `[^1]: def` |
| Collapsible | `<details><summary>Title</summary>Body</details>` |
| Underline | `<u>text</u>` |
| Superscript | `<sup>text</sup>` |
| Subscript | `<sub>text</sub>` |
| Horizontal rule | `---` |

### Rich HTML
All tags from Bot API 10.1: `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<pre>`, `<mark>`, `<sup>`, `<sub>`, `<tg-spoiler>`, `<blockquote>`, `<aside>`, `<h1>`–`<h6>`, `<ul>`, `<ol>`, `<table>`, `<details>`, `<tg-math>`, `<tg-math-block>`, `<tg-map>`, `<tg-collage>`, `<tg-slideshow>`, `<figure>`, `<figcaption>`, `<footer>`, `<hr>`, and more.

---

## Requirements

- Python 3.10+
- `python-telegram-bot >= 21.0`
- `aiohttp`
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))

```
pip install python-telegram-bot aiohttp
```

---

## Setup

### 1. Clone

```bash
git clone https://github.com/yourusername/RichTextBot.git
cd RichTextBot
```

### 2. Environment variable

```bash
export BOT_TOKEN=your_telegram_bot_token
```

Or create a `.env` file and load it:

```
BOT_TOKEN=your_telegram_bot_token
```

### 3. Run

```bash
python richbot.py
```

---

## Deploy on Heroku

```bash
heroku create
heroku config:set BOT_TOKEN=your_token
git push heroku main
heroku ps:scale worker=1
```

---

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/md <text>` | Force Markdown mode |
| `/html <text>` | Force HTML mode |
| Send text | Auto-detect mode and render |
| Send `.md` file | Render as Markdown rich message |
| Send `.html` file | Render as HTML rich message |

---

## How It Works

```
User sends text / file
        │
        ▼
   detect mode
  (html or markdown)
        │
        ▼
POST /sendRichMessage
  rich_message: { markdown: ... }
  OR
  rich_message: { html: ... }
        │
      fail?
        │
        ▼
  try other mode
        │
      fail?
        │
        ▼
   send error msg
```

Uses Telegram Bot API 10.1 `sendRichMessage` directly over HTTP (`aiohttp`) — no wrapper library needed for the new method.

---

## Limits (Bot API 10.1)

- Max **32,768 characters** per rich message
- Max **500 blocks** (headings, list items, table rows, etc.)
- Max **16 levels** of nesting
- Max **50 media** attachments
- Max **20 columns** in a table

---

## License

MIT
