import os, asyncio, aiohttp, logging
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from telegram.constants import ChatAction

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── direct HTTP sendRichMessage (PTB has no native class yet) ──────────────
async def send_rich(chat_id: int, content: str, mode: str, thread_id=None):
    """
    mode = 'markdown' or 'html'
    Calls sendRichMessage directly over HTTP.
    Returns (ok, response_json).
    """
    payload = {
        "chat_id": chat_id,
        "rich_message": {mode: content},
    }
    if thread_id:
        payload["message_thread_id"] = thread_id

    async with aiohttp.ClientSession() as s:
        async with s.post(f"{TG_API}/sendRichMessage", json=payload) as r:
            data = await r.json()
            return data.get("ok", False), data

# ── fallback: plain sendMessage ────────────────────────────────────────────
async def send_plain(chat_id: int, text: str, thread_id=None):
    payload = {"chat_id": chat_id, "text": text[:4096]}
    if thread_id:
        payload["message_thread_id"] = thread_id
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{TG_API}/sendMessage", json=payload) as r:
            return await r.json()

# ── detect input mode ──────────────────────────────────────────────────────
def detect_mode(text: str) -> str:
    """Guess 'html' or 'markdown' from content."""
    stripped = text.lstrip()
    if stripped.startswith("<"):
        return "html"
    return "markdown"

# ── handlers ───────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me:\n"
        "• Any markdown text\n"
        "• An .md or .html file\n"
        "I'll resend it as a Telegram Rich Message.\n\n"
        "Force mode: /md <text>  or  /html <text>"
    )

async def _send_and_reply(update: Update, text: str, mode: str = None):
    msg = update.message
    chat_id = msg.chat_id
    thread_id = getattr(msg, "message_thread_id", None)
    mode = mode or detect_mode(text)

    ok, resp = await send_rich(chat_id, text, mode, thread_id)

    if not ok:
        err = resp.get("description", "unknown error")
        # try the other mode as fallback
        other = "html" if mode == "markdown" else "markdown"
        ok2, resp2 = await send_rich(chat_id, text, other, thread_id)
        if not ok2:
            await send_plain(chat_id,
                f"❌ sendRichMessage failed ({mode}): {err}\n"
                f"❌ fallback ({other}) also failed: {resp2.get('description','')}",
                thread_id)

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return
    await _send_and_reply(update, text)

async def handle_doc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return
    name = (doc.file_name or "").lower()
    if not (name.endswith(".md") or name.endswith(".html") or name.endswith(".txt")):
        await update.message.reply_text("Send an .md or .html file.")
        return
    await ctx.bot.send_chat_action(update.message.chat_id, ChatAction.TYPING)
    f = await doc.get_file()
    raw = await f.download_as_bytearray()
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        await update.message.reply_text("File is empty.")
        return
    mode = "html" if name.endswith(".html") else "markdown"
    await _send_and_reply(update, text, mode)

async def cmd_md(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = " ".join(ctx.args) if ctx.args else (update.message.text or "").split(None, 1)[-1]
    if not text.strip():
        await update.message.reply_text("Usage: /md <markdown text>")
        return
    await _send_and_reply(update, text.strip(), "markdown")

async def cmd_html(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = " ".join(ctx.args) if ctx.args else (update.message.text or "").split(None, 1)[-1]
    if not text.strip():
        await update.message.reply_text("Usage: /html <html text>")
        return
    await _send_and_reply(update, text.strip(), "html")

# ── main ───────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("md",     cmd_md))
    app.add_handler(CommandHandler("html",   cmd_html))
    app.add_handler(MessageHandler(filters.Document.ALL,          handle_doc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
