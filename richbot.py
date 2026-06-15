import os, re, logging
import aiohttp
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (Application, MessageHandler, CallbackQueryHandler,
                          CommandHandler, filters, ContextTypes)
from telegram.constants import ChatAction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TG_API    = f"https://api.telegram.org/bot{BOT_TOKEN}"
REPO      = "https://github.com/devgaganin/RichTextBot"

# ── HTTP helpers ────────────────────────────────────────────────────────────

async def _post(endpoint: str, payload: dict) -> tuple:
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{TG_API}/{endpoint}", json=payload) as r:
            data = await r.json()
            return data.get("ok", False), data

async def send_rich(chat_id: int, content: str, mode: str, thread_id=None) -> tuple:
    p = {"chat_id": chat_id, "rich_message": {mode: content}}
    if thread_id:
        p["message_thread_id"] = thread_id
    return await _post("sendRichMessage", p)

async def send_plain(chat_id: int, text: str, thread_id=None):
    p = {"chat_id": chat_id, "text": text[:4096]}
    if thread_id:
        p["message_thread_id"] = thread_id
    return await _post("sendMessage", p)

async def try_delete(bot, chat_id: int, msg_id: int):
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass

# ── Slideshow detection & wrapping ─────────────────────────────────────────

_HAS_SS = re.compile(r'<tg-slideshow', re.I)

# 2+ markdown image lines separated ONLY by blank lines (no other content between)
# Handles: ![](url1)\n\n![](url2)  and  ![](url1)\n![](url2)
_CONSEC_MD = re.compile(
    r'!\[.*?\]\([^)]+\)'             # first image tag
    r'(?:[ \t]*\n(?:[ \t]*\n)*'      # newline + optional blank lines
    r'!\[.*?\]\([^)]+\))+',           # next image tag, 1+ times
    re.MULTILINE
)

def _has_slideshow_candidate(text: str) -> bool:
    """True if 2+ consecutive media items (blank lines allowed between) not in <tg-slideshow>."""
    if _HAS_SS.search(text):
        return False
    if _CONSEC_MD.search(text):
        return True
    # HTML: consecutive media tags
    if re.search(r'<(?:img|video|audio)\b[^>]*/?\s*>\s*<(?:img|video|audio)\b', text, re.I):
        return True
    return False

def _wrap_slideshow(text: str) -> str:
    """Wraps consecutive media groups in <tg-slideshow> tags."""
    def _md(m):
        return f'<tg-slideshow>\n\n{m.group(0).strip()}\n\n</tg-slideshow>'
    text = _CONSEC_MD.sub(_md, text)

    def _html(m):
        return f'<tg-slideshow>\n{m.group(0).strip()}\n</tg-slideshow>'
    text = re.sub(r'((?:<(?:img|video|audio)\b[^>]*/?\s*>\s*){2,})', _html, text, flags=re.I)
    return text

# ── Core send ───────────────────────────────────────────────────────────────

def _detect_mode(text: str) -> str:
    return "html" if text.lstrip().startswith("<") else "markdown"

async def _send_once(bot, chat_id: int, text: str, mode: str,
                     thread_id, orig_msg_id: int, prompt_msg_id: int = None):
    """Send rich message, delete original + prompt (if any)."""
    ok, resp = await send_rich(chat_id, text, mode, thread_id)
    if not ok:
        other = "html" if mode == "markdown" else "markdown"
        ok2, resp2 = await send_rich(chat_id, text, other, thread_id)
        if not ok2:
            await send_plain(
                chat_id,
                f"❌ sendRichMessage ({mode}): {resp.get('description','')}\n"
                f"❌ fallback ({other}): {resp2.get('description','')}",
                thread_id
            )
            return
    # Clean up: delete original + the choice prompt
    await try_delete(bot, chat_id, orig_msg_id)
    if prompt_msg_id:
        await try_delete(bot, chat_id, prompt_msg_id)


async def _process(bot, chat_id: int, text: str, mode: str,
                   thread_id, orig_msg_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Main entry point.
    - Consecutive media detected → ask user (rich text OR slideshow), do NOT send yet
    - No consecutive media → send rich message directly, delete original
    """
    if _has_slideshow_candidate(text):
        # Store text and wait for user's choice
        ctx.bot_data[f"ss_{chat_id}"] = {
            "text": text, "mode": mode,
            "thread": thread_id, "orig": orig_msg_id
        }
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📄 Send as Rich Text",  callback_data=f"rich:{chat_id}"),
            InlineKeyboardButton("📸 Send as Slideshow",  callback_data=f"ss:{chat_id}"),
        ]])
        await bot.send_message(
            chat_id,
            "📸 Consecutive media detected — how do you want to send it?",
            reply_markup=kb,
            message_thread_id=thread_id
        )
        # Do NOT send anything else — wait for button click
    else:
        await _send_once(bot, chat_id, text, mode, thread_id, orig_msg_id)

# ── Callbacks ───────────────────────────────────────────────────────────────

async def _choice_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()

    action, cid = q.data.split(":", 1)
    chat_id = int(cid)
    stored  = ctx.bot_data.pop(f"ss_{chat_id}", None)

    if not stored:
        await q.edit_message_text("⚠️ Session expired — please resend.")
        return

    text     = stored["text"]
    mode     = stored["mode"]
    thread   = stored.get("thread")
    orig     = stored["orig"]
    prompt   = q.message.message_id

    if action == "ss":
        text = _wrap_slideshow(text)

    await q.edit_message_text("⏳ Sending...")
    await _send_once(ctx.bot, chat_id, text, mode, thread, orig, prompt)

# ── Message helpers ─────────────────────────────────────────────────────────

def _msg(update: Update):
    return update.message or update.channel_post

# ── Handlers ────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = _msg(update)
    if m:
        await m.reply_text(
            "Send me any markdown or HTML — I'll render it as a Telegram Rich Message "
            "and delete your original for a clean look.\n\n"
            "• /md <text> — force Markdown mode\n"
            "• /html <text> — force HTML mode\n"
            "• Send an .md / .html file directly\n\n"
            f"Source: {REPO}"
        )

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = _msg(update)
    if not m:
        return
    text = (m.text or "").strip()
    if not text:
        return
    await ctx.bot.send_chat_action(m.chat_id, ChatAction.TYPING,
                                   message_thread_id=getattr(m, "message_thread_id", None))
    await _process(ctx.bot, m.chat_id, text, _detect_mode(text),
                   getattr(m, "message_thread_id", None), m.message_id, ctx)

async def handle_doc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = _msg(update)
    if not m or not m.document:
        return
    name = (m.document.file_name or "").lower()
    if not (name.endswith(".md") or name.endswith(".html") or name.endswith(".txt")):
        await m.reply_text("Send an .md or .html file.")
        return
    await ctx.bot.send_chat_action(m.chat_id, ChatAction.TYPING)
    raw  = await (await m.document.get_file()).download_as_bytearray()
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        await m.reply_text("File is empty.")
        return
    mode = "html" if name.endswith(".html") else "markdown"
    await _process(ctx.bot, m.chat_id, text, mode,
                   getattr(m, "message_thread_id", None), m.message_id, ctx)

async def cmd_md(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m    = _msg(update)
    text = " ".join(ctx.args or []).strip()
    if not text:
        await m.reply_text("Usage: /md <markdown text>")
        return
    await _process(ctx.bot, m.chat_id, text, "markdown",
                   getattr(m, "message_thread_id", None), m.message_id, ctx)

async def cmd_html(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m    = _msg(update)
    text = " ".join(ctx.args or []).strip()
    if not text:
        await m.reply_text("Usage: /html <html text>")
        return
    await _process(ctx.bot, m.chat_id, text, "html",
                   getattr(m, "message_thread_id", None), m.message_id, ctx)

# ── Main ────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("md",    cmd_md))
    app.add_handler(CommandHandler("html",  cmd_html))

    chan = filters.UpdateType.CHANNEL_POSTS
    doc  = filters.Document.ALL
    txt  = filters.TEXT & ~filters.COMMAND

    app.add_handler(MessageHandler(doc & ~chan, handle_doc))
    app.add_handler(MessageHandler(txt & ~chan, handle_text))
    app.add_handler(MessageHandler(chan & doc,  handle_doc))
    app.add_handler(MessageHandler(chan & txt,  handle_text))

    app.add_handler(CallbackQueryHandler(_choice_cb, pattern=r"^(rich|ss):"))

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
