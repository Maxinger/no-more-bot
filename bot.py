"""NoMoreBot - Track your activities."""
import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from db import get_history, init_db, record_event

logger = logging.getLogger(__name__)

WELCOME = "NoMoreBot - Track your activities"

KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("Record now", callback_data="record"),
        InlineKeyboardButton("Show history", callback_data="history"),
    ]
])


def format_history(records: list) -> str:
    """Format history records as date + time per line."""
    if not records:
        return "No records for the last 14 days."
    lines = [f"{r.strftime('%Y-%m-%d')}  {r.strftime('%H:%M')}" for r in records]
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info(
        "PROCESS /start user_id=%s username=%r chat_id=%s",
        user.id if user else None,
        user.username if user else None,
        update.effective_chat.id if update.effective_chat else None,
    )
    await update.message.reply_text(WELCOME, reply_markup=KEYBOARD)
    logger.debug("PROCESS /start done: sent welcome + keyboard")


async def log_incoming_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log every message-style update (message / edited_message / channel_post)."""
    em = update.effective_message
    if not em:
        return
    kind = "message"
    if update.edited_message:
        kind = "edited_message"
    elif update.channel_post:
        kind = "channel_post"
    text = em.text or em.caption
    if text is None:
        text = f"<{em.content_type or 'unknown'}>"
    logger.info(
        "IN  update_id=%s kind=%s user_id=%s chat_id=%s text=%r",
        update.update_id,
        kind,
        em.from_user.id if em.from_user else None,
        em.chat_id,
        text[:500] + ("…" if len(str(text)) > 500 else ""),
    )
    logger.debug("IN  full effective_message payload: %s", em.to_dict() if hasattr(em, "to_dict") else em)


async def log_incoming_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    logger.info(
        "IN  update_id=%s callback_query user_id=%s data=%r inline_msg_id=%s",
        update.update_id,
        q.from_user.id if q.from_user else None,
        q.data,
        q.inline_message_id,
    )
    logger.debug("IN  callback_query full: %s", q.to_dict() if hasattr(q, "to_dict") else q)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    logger.info("PROCESS callback data=%r user_id=%s", query.data, user_id)
    await query.answer()

    if query.data == "record":
        recorded_at = record_event(user_id)
        text = f"Recorded: {recorded_at.strftime('%Y-%m-%d %H:%M')}"
        logger.info("PROCESS record stored recorded_at=%s", recorded_at)
    elif query.data == "history":
        records = get_history(user_id, days=14)
        text = format_history(records)
        logger.info("PROCESS history rows=%d", len(records))
    else:
        logger.warning("PROCESS callback ignored unknown data=%r", query.data)
        return

    await query.edit_message_text(text=text, reply_markup=KEYBOARD)
    logger.debug("PROCESS callback done: edited message")


def main() -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, log_level, logging.INFO),
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in environment or .env")
    init_db()
    app = Application.builder().token(token).build()
    # Group -1 runs first: log all incoming messages and callback queries
    app.add_handler(MessageHandler(filters.ALL, log_incoming_message), group=-1)
    app.add_handler(CallbackQueryHandler(log_incoming_callback), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Starting bot (LOG_LEVEL=%s)...", log_level)
    app.run_polling()


if __name__ == "__main__":
    main()
