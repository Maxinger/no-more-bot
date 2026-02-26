"""NoMoreBot - Track your activities."""
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from db import get_history, init_db, record_event

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
    await update.message.reply_text(WELCOME, reply_markup=KEYBOARD)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "record":
        recorded_at = record_event(user_id)
        text = f"Recorded: {recorded_at.strftime('%Y-%m-%d %H:%M')}"
    elif query.data == "history":
        records = get_history(user_id, days=14)
        text = format_history(records)
    else:
        return

    await query.edit_message_text(text=text, reply_markup=KEYBOARD)


def main() -> None:
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in environment or .env")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("Starting bot...")
    app.run_polling()


if __name__ == "__main__":
    main()
