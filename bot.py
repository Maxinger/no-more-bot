"""NoMoreBot - Track your activities."""
import datetime
import logging
import os
from typing import Any

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

from ddd.application import (
    LoadWeekProgressUseCase,
    RecordActivityForDayCommand,
    RecordActivityNowCommand,
    RecordActivityUseCase,
)
from ddd.domain.record import Activity as DddActivity
from ddd.domain.user import User as DddUser
from ddd.infra import InMemoryRepositories
from ddd.infra.dev import apply_initial_data_fixture as apply_ddd_initial_data_fixture
from ddd.representation import CurrentWeekSummaryText, WeekDetailsText

logger = logging.getLogger(__name__)
ddd_repositories = InMemoryRepositories()
apply_ddd_initial_data_fixture(ddd_repositories)
current_week_summary_text = CurrentWeekSummaryText(
    LoadWeekProgressUseCase(ddd_repositories.goals, ddd_repositories.records)
)
week_details_text = WeekDetailsText(
    LoadWeekProgressUseCase(ddd_repositories.goals, ddd_repositories.records)
)
record_activity = RecordActivityUseCase(ddd_repositories.records)

USER_DATA_PENDING_ACTION = "pending_action"
HOME_ICON = "🏠"
BED_ICON = "🛏️"
TIME_ICON = "⏰"
CALENDAR_ICON = "📅"
GOALS_ICON = "🎯"
BACK_TO_MENU_LABEL = "Back to Menu"

WELCOME = (
    "NoMoreBot — track activities.\n\n"
    f"{HOME_ICON} Now and {BED_ICON} Now record an event immediately.\n"
    f"{TIME_ICON} Past lets you save yesterday or a specific date.\n"
    f"{GOALS_ICON} Goals is reserved for a future goals workflow.\n\n"
    "Send /start anytime to return to the main menu."
)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"{HOME_ICON} Now", callback_data="record_now:home"),
                InlineKeyboardButton(f"{BED_ICON} Now", callback_data="record_now:bed"),
            ],
            [
                InlineKeyboardButton(f"{TIME_ICON} Past", callback_data="menu:past"),
                InlineKeyboardButton(f"{GOALS_ICON} Goals", callback_data="menu:goals"),
            ],
        ]
    )


def back_to_menu_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(BACK_TO_MENU_LABEL, callback_data="menu:main")]


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([back_to_menu_row()])


def past_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"{HOME_ICON} Yesterday", callback_data="past_yesterday:home"),
                InlineKeyboardButton(f"{BED_ICON} Yesterday", callback_data="past_yesterday:bed"),
            ],
            [
                InlineKeyboardButton(f"{HOME_ICON} Earlier", callback_data="past_date:home"),
                InlineKeyboardButton(f"{BED_ICON} Earlier", callback_data="past_date:bed"),
            ],
            back_to_menu_row(),
        ]
    )


def goals_menu_keyboard() -> InlineKeyboardMarkup:
    return back_to_menu_keyboard()


def parse_activity_token(token: str) -> DddActivity | None:
    t = token.strip().lower()
    if t in ("bed", "going_to_bed"):
        return DddActivity.BED
    if t in ("home", "going_home"):
        return DddActivity.HOME
    return None


def parse_hhmm(s: str) -> datetime.time | None:
    """Parse HH:MM (24h). Single-digit hour is allowed (e.g. 9:30)."""
    try:
        return datetime.datetime.strptime(s.strip(), "%H:%M").time()
    except ValueError:
        return None


def parse_past_event_datetime(s: str) -> datetime.datetime | None:
    text = s.strip()
    current_year = datetime.datetime.now(datetime.timezone.utc).year
    for fmt, includes_year in (("%d.%m.%Y %H:%M", True), ("%d.%m %H:%M", False)):
        try:
            parsed = datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
        if not includes_year:
            parsed = parsed.replace(year=current_year)
        return parsed.replace(tzinfo=datetime.timezone.utc)
    return None


def current_utc_datetime() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def current_date_for_user(user: DddUser) -> datetime.date:
    return current_utc_datetime().astimezone(user.time_zone).date()


def activity_name(activity: DddActivity) -> str:
    return "Home" if activity == DddActivity.HOME else "Bed"


def clear_pending_action(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(USER_DATA_PENDING_ACTION, None)


def set_pending_action(
    context: ContextTypes.DEFAULT_TYPE,
    kind: str,
    activity: DddActivity,
    week_start: datetime.date | None = None,
) -> None:
    pending: dict[str, Any] = {"kind": kind, "activity": activity}
    if week_start is not None:
        pending["week_start"] = week_start
    context.user_data[USER_DATA_PENDING_ACTION] = pending


def pending_reply_markup(kind: str) -> InlineKeyboardMarkup:
    return back_to_menu_keyboard()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    clear_pending_action(context)
    logger.info(
        "PROCESS /start user_id=%s username=%r chat_id=%s",
        user.id if user else None,
        user.username if user else None,
        update.effective_chat.id if update.effective_chat else None,
    )
    if update.message:
        text = (
            current_week_summary_text.summary_for_current_week(DddUser(user.id))
            if user is not None
            else "Current week is not available."
        )
        await update.message.reply_text(text, reply_markup=main_menu_keyboard())
    logger.debug("PROCESS /start done: sent current week summary + keyboard")


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


async def maybe_handle_pending_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = context.user_data.get(USER_DATA_PENDING_ACTION)
    if pending is None or not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    kind = pending.get("kind")
    activity = pending.get("activity")
    user_id = update.effective_user.id if update.effective_user else None
    if not isinstance(kind, str) or not isinstance(activity, DddActivity) or user_id is None:
        clear_pending_action(context)
        return
    user = DddUser(user_id)

    if kind == "event_yesterday":
        time_value = parse_hhmm(text)
        if time_value is None:
            await update.message.reply_text(
                "Expected HH:MM, for example 22:30. Send /start to cancel.",
                reply_markup=pending_reply_markup(kind),
            )
            return
        day = current_date_for_user(user) - datetime.timedelta(days=1)
        result = record_activity.handle(
            RecordActivityForDayCommand(
                user=user,
                activity=activity,
                activity_date=day,
                activity_time=time_value,
            )
        )
        clear_pending_action(context)
        await update.message.reply_text(
            week_details_text.details_for_week(
                user=user,
                activity=activity,
                date=result.record.time.date,
            ),
            reply_markup=back_to_menu_keyboard(),
        )
        return

    if kind == "event_date":
        timestamp = parse_past_event_datetime(text)
        if timestamp is None:
            await update.message.reply_text(
                "Expected `dd.mm.yyyy HH:MM` or `dd.mm HH:MM`, for example `12.04.2026 22:30`.",
                reply_markup=pending_reply_markup(kind),
            )
            return
        result = record_activity.handle(
            RecordActivityForDayCommand(
                user=user,
                activity=activity,
                activity_date=timestamp.date(),
                activity_time=timestamp.time(),
            )
        )
        clear_pending_action(context)
        await update.message.reply_text(
            week_details_text.details_for_week(
                user=user,
                activity=activity,
                date=result.record.time.date,
            ),
            reply_markup=back_to_menu_keyboard(),
        )
        return

    clear_pending_action(context)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or update.effective_user is None:
        return
    user_id = update.effective_user.id
    user = DddUser(user_id)
    logger.info("PROCESS callback data=%r user_id=%s", query.data, user_id)
    await query.answer()

    text: str
    reply_markup = back_to_menu_keyboard()
    parse_mode: str | None = None

    if query.data == "menu:main":
        clear_pending_action(context)
        text = current_week_summary_text.summary_for_current_week(user)
        reply_markup = main_menu_keyboard()
    elif query.data == "menu:past":
        clear_pending_action(context)
        text = (
            "Choose a past event flow.\n\n"
            f"• {HOME_ICON} Yesterday / {BED_ICON} Yesterday expects HH:MM\n"
            f"• {CALENDAR_ICON} Date expects `dd.mm.yyyy HH:MM` or `dd.mm HH:MM`\n\n"
            f"Tap {BACK_TO_MENU_LABEL} or send /start to return to the main menu."
        )
        reply_markup = past_menu_keyboard()
    elif query.data == "menu:goals":
        clear_pending_action(context)
        text = "Goals are temporarily unavailable while the new DDD goals workflow is being built."
        reply_markup = goals_menu_keyboard()
    elif query.data.startswith("record_now:"):
        clear_pending_action(context)
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            occurred_at = current_utc_datetime()
            result = record_activity.handle(
                RecordActivityNowCommand(
                    user=user,
                    activity=activity,
                    occurred_at=occurred_at,
                )
            )
            text = week_details_text.details_for_week(
                user=user,
                activity=activity,
                date=result.record.time.date,
            )
            reply_markup = back_to_menu_keyboard()
    elif query.data.startswith("past_yesterday:"):
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            set_pending_action(context, "event_yesterday", activity)
            text = f"Send the time for yesterday's {activity_name(activity)} event as HH:MM."
            reply_markup = pending_reply_markup("event_yesterday")
    elif query.data.startswith("past_date:"):
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            set_pending_action(context, "event_date", activity)
            text = (
                f"Send the date and time for the {activity_name(activity)} event as "
                "`dd.mm.yyyy HH:MM` or `dd.mm HH:MM`."
            )
            reply_markup = pending_reply_markup("event_date")
    else:
        logger.warning("PROCESS callback ignored unknown data=%r", query.data)
        return

    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            logger.info("PROCESS callback ignored: message not modified (data=%r user_id=%s)", query.data, user_id)
            return
        raise
    logger.debug("PROCESS callback done: edited message")


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Welcome and keyboard"),
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
    app.add_handler(MessageHandler(filters.ALL, log_incoming_message), group=-1)
    app.add_handler(CallbackQueryHandler(log_incoming_callback), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, maybe_handle_pending_input),
        group=0,
    )
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Starting bot (LOG_LEVEL=%s)...", log_level)
    app.run_polling()


if __name__ == "__main__":
    main()
