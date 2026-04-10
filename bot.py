"""NoMoreBot - Track your activities."""
import datetime
import logging
import os

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from application.tracking_service import TrackingService, monday_of_week_containing
from domain.model.record import Activity
from infra.tracker.in_memory import InMemoryTracker

logger = logging.getLogger(__name__)
tracking_service = TrackingService(InMemoryTracker())

# After "Goal this week (…)" the next plain text message is interpreted as HH:MM for that activity.
USER_DATA_PENDING_GOAL_ACTIVITY = "pending_goal_activity"
HOME_ICON = "🏠"
BED_ICON = "🛏️"

WELCOME = (
    "NoMoreBot — track activities and weekly goals.\n\n"
    "Set this week's goal (Mon–Sun, UTC):\n"
    f"• tap {HOME_ICON} Goal or {BED_ICON} Goal, then send a time like 22:30\n"
    "• or use: /setgoal bed 22:30\n\n"
    "Other: /getgoal bed · /goals bed"
)

KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(f"{HOME_ICON} Record", callback_data="record:home"),
        InlineKeyboardButton(f"{BED_ICON} Record", callback_data="record:bed"),
    ],
    [
        InlineKeyboardButton(f"{HOME_ICON} Goal", callback_data="goal_get:home"),
        InlineKeyboardButton(f"{BED_ICON} Goal", callback_data="goal_get:bed"),
    ],
    [
        InlineKeyboardButton(f"{HOME_ICON} Recent goals", callback_data="goals_list:home"),
        InlineKeyboardButton(f"{BED_ICON} Recent goals", callback_data="goals_list:bed"),
    ],
])


def parse_activity_token(token: str) -> Activity | None:
    t = token.strip().lower()
    if t in ("bed", "going_to_bed"):
        return Activity.BED
    if t in ("home", "going_home"):
        return Activity.HOME
    return None


def parse_hhmm(s: str) -> datetime.time | None:
    """Parse HH:MM (24h). Single-digit hour is allowed (e.g. 9:30)."""
    s = s.strip()
    parts = s.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None
        return datetime.time(h, m)
    except ValueError:
        return None


def format_goal_week_label(week_start: datetime.date) -> str:
    return f"Week of {week_start.isoformat()} (Mon)"


def format_goals_list(pairs: list[tuple[datetime.date, datetime.time]]) -> str:
    if not pairs:
        return "No goals stored for this activity yet."
    lines = [f"{d.isoformat()}  {t.strftime('%H:%M')}" for d, t in pairs]
    return "\n".join(lines)


async def cmd_setgoal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(USER_DATA_PENDING_GOAL_ACTIVITY, None)
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "Usage: /setgoal <bed|home> <HH:MM>\n"
            "Sets your goal for the current week (Monday–Sunday, UTC date).",
            reply_markup=KEYBOARD,
        )
        return
    activity = parse_activity_token(context.args[0])
    t = parse_hhmm(context.args[1])
    if activity is None or t is None:
        await update.message.reply_text(
            "Could not parse activity or time. Use e.g. /setgoal bed 22:30",
            reply_markup=KEYBOARD,
        )
        return
    tracking_service.set_goal(activity, t)
    week = monday_of_week_containing(datetime.datetime.now(datetime.timezone.utc).date())
    await update.message.reply_text(
        f"Goal set: {activity.value} at {t.strftime('%H:%M')} for {format_goal_week_label(week)}.",
        reply_markup=KEYBOARD,
    )


async def cmd_getgoal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(USER_DATA_PENDING_GOAL_ACTIVITY, None)
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /getgoal <bed|home>\nShows the goal for the current week (UTC).",
            reply_markup=KEYBOARD,
        )
        return
    activity = parse_activity_token(context.args[0])
    if activity is None:
        await update.message.reply_text("Unknown activity. Use `bed` or `home`.", reply_markup=KEYBOARD)
        return
    try:
        g = tracking_service.get_goal(activity)
    except KeyError:
        week = monday_of_week_containing(datetime.datetime.now(datetime.timezone.utc).date())
        await update.message.reply_text(
            f"No goal set for {activity.value} for {format_goal_week_label(week)}.",
            reply_markup=KEYBOARD,
        )
        return
    week = monday_of_week_containing(datetime.datetime.now(datetime.timezone.utc).date())
    await update.message.reply_text(
        f"{activity.value}: {g.strftime('%H:%M')} ({format_goal_week_label(week)})",
        reply_markup=KEYBOARD,
    )


async def cmd_goals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(USER_DATA_PENDING_GOAL_ACTIVITY, None)
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /goals <bed|home> [limit]\nLists recent goals (default limit 10).",
            reply_markup=KEYBOARD,
        )
        return
    activity = parse_activity_token(context.args[0])
    if activity is None:
        await update.message.reply_text("Unknown activity. Use `bed` or `home`.", reply_markup=KEYBOARD)
        return
    limit = 10
    if len(context.args) >= 2:
        try:
            limit = max(1, min(50, int(context.args[1])))
        except ValueError:
            await update.message.reply_text("Limit must be a number between 1 and 50.", reply_markup=KEYBOARD)
            return
    pairs = tracking_service.get_goals(activity, limit=limit)
    await update.message.reply_text(format_goals_list(pairs), reply_markup=KEYBOARD)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    context.user_data.pop(USER_DATA_PENDING_GOAL_ACTIVITY, None)
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


def _goal_prompt_suffix(activity: Activity) -> str:
    return (
        f"\n\nSend a new goal time as HH:MM (UTC week), e.g. 22:30 — "
        f"or /start to cancel."
    )


async def maybe_handle_pending_goal_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """If user tapped Home: Goal / Bed: Goal, next non-command message sets that goal when HH:MM."""
    activity = context.user_data.get(USER_DATA_PENDING_GOAL_ACTIVITY)
    if activity is None or not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    t = parse_hhmm(text)
    if t is None:
        await update.message.reply_text(
            "Expected HH:MM (e.g. 22:30). Try again, or send /start to cancel.",
            reply_markup=KEYBOARD,
        )
        return
    tracking_service.set_goal(activity, t)
    context.user_data.pop(USER_DATA_PENDING_GOAL_ACTIVITY, None)
    week = monday_of_week_containing(datetime.datetime.now(datetime.timezone.utc).date())
    await update.message.reply_text(
        f"Goal set: {activity.value} at {t.strftime('%H:%M')} for {format_goal_week_label(week)}.",
        reply_markup=KEYBOARD,
    )
    logger.info("PROCESS pending goal set activity=%s time=%s", activity.value, t)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    logger.info("PROCESS callback data=%r user_id=%s", query.data, user_id)
    await query.answer()

    if query.data.startswith("record:"):
        context.user_data.pop(USER_DATA_PENDING_GOAL_ACTIVITY, None)
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        logger.info("PROCESS record token=%r", token)
        if activity is None:
            text = "Unknown activity."
        else:
            record = tracking_service.record(user_id, activity)
            icon = HOME_ICON if activity == Activity.HOME else BED_ICON
            text = f"{icon} Recorded: {record.timestamp.strftime('%Y-%m-%d %H:%M')}"
            logger.info(
                "PROCESS record stored recorded_at=%s activity=%s",
                record.timestamp,
                activity.value,
            )
    elif query.data.startswith("goal_get:"):
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            context.user_data[USER_DATA_PENDING_GOAL_ACTIVITY] = activity
            try:
                g = tracking_service.get_goal(activity)
            except KeyError:
                week = monday_of_week_containing(datetime.datetime.now(datetime.timezone.utc).date())
                text = f"No goal for {activity.value} ({format_goal_week_label(week)})."
            else:
                week = monday_of_week_containing(datetime.datetime.now(datetime.timezone.utc).date())
                text = f"{activity.value}: {g.strftime('%H:%M')} ({format_goal_week_label(week)})"
            text += _goal_prompt_suffix(activity)
        logger.info("PROCESS goal_get token=%r", token)
    elif query.data.startswith("goals_list:"):
        context.user_data.pop(USER_DATA_PENDING_GOAL_ACTIVITY, None)
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            pairs = tracking_service.get_goals(activity, limit=10)
            text = format_goals_list(pairs)
        logger.info("PROCESS goals_list token=%r", token)
    else:
        logger.warning("PROCESS callback ignored unknown data=%r", query.data)
        return

    try:
        await query.edit_message_text(text=text, reply_markup=KEYBOARD)
    except BadRequest as e:
        # Telegram throws this when the new content+markup are identical to the current message
        # (e.g., user presses the same button again quickly and our formatted text doesn't change).
        if "Message is not modified" in str(e):
            logger.info("PROCESS callback ignored: message not modified (data=%r user_id=%s)", query.data, user_id)
            return
        raise
    logger.debug("PROCESS callback done: edited message")


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Welcome and keyboard"),
            BotCommand("setgoal", "Set this week's goal, e.g. bed 22:30"),
            BotCommand("getgoal", "Show this week's goal, e.g. bed"),
            BotCommand("goals", "List recent goals, e.g. bed"),
        ]
    )


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
    app = Application.builder().token(token).post_init(post_init).build()
    # Group -1 runs first: log all incoming messages and callback queries
    app.add_handler(MessageHandler(filters.ALL, log_incoming_message), group=-1)
    app.add_handler(CallbackQueryHandler(log_incoming_callback), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setgoal", cmd_setgoal))
    app.add_handler(CommandHandler("getgoal", cmd_getgoal))
    app.add_handler(CommandHandler("goals", cmd_goals))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, maybe_handle_pending_goal_time),
        group=0,
    )
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Starting bot (LOG_LEVEL=%s)...", log_level)
    app.run_polling()


if __name__ == "__main__":
    main()
