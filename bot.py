"""NoMoreBot - Track your activities."""
import datetime
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from application import (
    ExportUserDataCommand,
    ExportUserDataUseCase,
    LoadCurrentWeekGoalPreviewCommand,
    LoadWeekProgressUseCase,
    RecordActivityForDayCommand,
    RecordActivityNowCommand,
    RecordActivityUseCase,
    SetWeekGoalCommand,
    SetWeekGoalUseCase,
)
from domain.record import Activity, RecordTime, WeekStart
from domain.user import User
from infra import InMemoryRepositories, SQLiteRepositories
from infra.dev import DEFAULT_INITIAL_DATA_PATH, apply_initial_data_fixture
from representation import (
    ActivityWeeksReportText,
    CurrentWeekSummaryText,
    InitialDataJsonBytes,
    WeekDetailsText,
)
from representation.formatting_utils import SEPARATOR
from representation.icons import HOME_ICON, BED_ICON, TIME_ICON, GOALS_ICON, REPORTS_ICON

logger = logging.getLogger(__name__)

DATABASE_PATH_ENV_VAR = "DB_PATH"
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "data" / "no-more-bot.sqlite3"
REPOSITORY_BACKEND_ENV_VAR = "REPOSITORY_BACKEND"
DEFAULT_REPOSITORY_BACKEND = "db"


def repository_backend_from_environment() -> str:
    configured = os.environ.get(REPOSITORY_BACKEND_ENV_VAR, DEFAULT_REPOSITORY_BACKEND)
    normalized = configured.strip().lower()
    if normalized in {"db", "sqlite"}:
        logger.info("Repository backend from %s: db", REPOSITORY_BACKEND_ENV_VAR)
        return "db"
    if normalized in {"memory", "in_memory"}:
        logger.info("Repository backend from %s: memory", REPOSITORY_BACKEND_ENV_VAR)
        return "memory"
    raise SystemExit(
        f"Invalid {REPOSITORY_BACKEND_ENV_VAR}={configured!r}; use 'db' or 'memory'"
    )


def database_path_from_environment() -> Path:
    configured_path = os.environ.get(DATABASE_PATH_ENV_VAR)
    if configured_path:
        path = Path(configured_path).expanduser()
        logger.info("Database path from %s: %s", DATABASE_PATH_ENV_VAR, path)
        return path
    logger.info("Database path default: %s", DEFAULT_DATABASE_PATH)
    return DEFAULT_DATABASE_PATH


def build_sqlite_repositories(
    db_path: Path | None = None,
    *,
    initial_data_path: Path = DEFAULT_INITIAL_DATA_PATH,
) -> SQLiteRepositories:
    if db_path is not None:
        path = db_path
        logger.info("Database path explicit: %s", path)
    else:
        path = database_path_from_environment()

    database_existed = path.exists()
    if database_existed:
        logger.info("Found existing database file at %s", path)
    else:
        logger.info("No database file at %s; a new database will be created", path)

    repositories = SQLiteRepositories(path)
    tables_empty = repositories.database.main_tables_are_empty()

    if not database_existed or tables_empty:
        logger.info("Seeding database from %s", initial_data_path)
        apply_initial_data_fixture(repositories, json_path=initial_data_path)
        record_count, goal_count = repositories.database.table_row_counts()
        logger.info(
            "Database seeding complete: records=%d, week_goals=%d",
            record_count,
            goal_count,
        )
    else:
        logger.info("Skipping initial data seed; database already contains data")

    return repositories


def build_memory_repositories(
    *,
    initial_data_path: Path = DEFAULT_INITIAL_DATA_PATH,
) -> InMemoryRepositories:
    logger.info("Using in-memory repositories")
    repositories = InMemoryRepositories()
    logger.info("Seeding in-memory repositories from %s", initial_data_path)
    apply_initial_data_fixture(repositories, json_path=initial_data_path)
    return repositories


def build_repositories(
    db_path: Path | None = None,
    *,
    initial_data_path: Path = DEFAULT_INITIAL_DATA_PATH,
    backend: str | None = None,
) -> InMemoryRepositories | SQLiteRepositories:
    selected_backend = backend or repository_backend_from_environment()
    if selected_backend == "memory":
        return build_memory_repositories(initial_data_path=initial_data_path)
    return build_sqlite_repositories(
        db_path,
        initial_data_path=initial_data_path,
    )


def configure_logging() -> str:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, log_level, logging.INFO),
    )
    return log_level


load_dotenv()
configure_logging()
repositories = build_repositories()
load_week_progress = LoadWeekProgressUseCase(repositories.goals, repositories.records)
current_week_summary_text = CurrentWeekSummaryText(load_week_progress)
week_details_text = WeekDetailsText(load_week_progress)
activity_weeks_report_text = ActivityWeeksReportText(load_week_progress)
record_activity = RecordActivityUseCase(repositories.records)
set_week_goal = SetWeekGoalUseCase(repositories.goals)
export_user_data = ExportUserDataUseCase(repositories.goals, repositories.records)
initial_data_json_bytes = InitialDataJsonBytes()

USER_DATA_PENDING_ACTION = "pending_action"
BACK_TO_MENU_LABEL = "Back to Menu"
BACK_TO_REPORTS_LABEL = "Back to Reports"
BACK_TO_GOALS_LABEL = "Back to Goals"

WELCOME = (
    "NoMoreBot.\n\n"
    f"{HOME_ICON}/{BED_ICON} Now: save now\n"
    f"{TIME_ICON} Past: save earlier\n"
    f"{GOALS_ICON} Goals: set targets\n"
    f"{REPORTS_ICON} Reports: details/export"
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
            [
                InlineKeyboardButton(f"{REPORTS_ICON} Reports", callback_data="menu:reports"),
            ],
        ]
    )


def back_to_menu_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(BACK_TO_MENU_LABEL, callback_data="menu:main")]


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([back_to_menu_row()])


def reports_navigation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(BACK_TO_REPORTS_LABEL, callback_data="menu:reports"),
                InlineKeyboardButton(BACK_TO_MENU_LABEL, callback_data="menu:main"),
            ]
        ]
    )


def goals_navigation_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(BACK_TO_GOALS_LABEL, callback_data="menu:goals"),
        InlineKeyboardButton(BACK_TO_MENU_LABEL, callback_data="menu:main"),
    ]


def goals_navigation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([goals_navigation_row()])


def past_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"{HOME_ICON} Yesterday", callback_data="past_yesterday:home"),
                InlineKeyboardButton(f"{BED_ICON} Yesterday", callback_data="past_yesterday:bed"),
            ],
            [
                InlineKeyboardButton(f"{HOME_ICON} Other", callback_data="past_date:home"),
                InlineKeyboardButton(f"{BED_ICON} Other", callback_data="past_date:bed"),
            ],
            back_to_menu_row(),
        ]
    )


def reports_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{HOME_ICON} This week",
                    callback_data="report_this_week:home",
                ),
                InlineKeyboardButton(
                    f"{BED_ICON} This week",
                    callback_data="report_this_week:bed",
                ),
            ],
            [
                InlineKeyboardButton(f"{HOME_ICON} All", callback_data="report_all:home"),
                InlineKeyboardButton(f"{BED_ICON} All", callback_data="report_all:bed"),
            ],
            [
                InlineKeyboardButton("Export", callback_data="export:data"),
            ],
            back_to_menu_row(),
        ]
    )


def goals_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"{HOME_ICON} Set", callback_data="goal_set:home"),
                InlineKeyboardButton(f"{BED_ICON} Set", callback_data="goal_set:bed"),
            ],
            back_to_menu_row(),
        ]
    )


def goal_set_keyboard(activity: Activity, *, has_auto: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_auto:
        rows.append(
            [
                InlineKeyboardButton(
                    "Auto",
                    callback_data=f"goal_auto:{activity_token(activity)}",
                )
            ]
        )
    rows.append(goals_navigation_row())
    return InlineKeyboardMarkup(rows)


def parse_activity_token(token: str) -> Activity | None:
    t = token.strip().lower()
    if t in ("bed", "going_to_bed"):
        return Activity.BED
    if t in ("home", "going_home"):
        return Activity.HOME
    return None


def activity_token(activity: Activity) -> str:
    return "home" if activity == Activity.HOME else "bed"


def parse_hhmm(s: str) -> datetime.time | None:
    """Parse HH:MM (24h). Single-digit hour is allowed (e.g. 9:30)."""
    try:
        return datetime.datetime.strptime(s.strip(), "%H:%M").time()
    except ValueError:
        return None


PAST_OTHER_FORMAT_HINT = "dd.mm.yyyy HH:MM, dd.mm HH:MM, or HH:MM for today"


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


def parse_past_event_for_user(
    s: str, user: User
) -> tuple[datetime.date, datetime.time] | None:
    text = s.strip()
    time_value = parse_hhmm(text)
    if time_value is not None:
        today = current_date_for_user(user)
        local_dt = datetime.datetime.combine(today, time_value, tzinfo=user.time_zone)
        record_time = RecordTime.from_datetime(local_dt, user.time_zone)
        return record_time.date, record_time.time

    timestamp = parse_past_event_datetime(text)
    if timestamp is None:
        return None
    return timestamp.date(), timestamp.time()


def current_utc_datetime() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def current_date_for_user(user: User) -> datetime.date:
    return current_utc_datetime().astimezone(user.time_zone).date()


def current_week_for_user(user: User) -> WeekStart:
    return WeekStart.from_any_date(current_date_for_user(user))


def activity_icon(activity: Activity) -> str:
    return HOME_ICON if activity == Activity.HOME else BED_ICON


def goals_report_for_current_week(user: User) -> str:
    current_date = current_date_for_user(user)
    return f"\n{SEPARATOR}\n".join(
        activity_weeks_report_text.report_for_activity(
            user=user,
            activity=activity,
            date=current_date,
        )
        for activity in (Activity.HOME, Activity.BED)
    )


def goal_set_screen_for_current_week(
    user: User, activity: Activity
) -> tuple[str, InlineKeyboardMarkup]:
    current_date = current_date_for_user(user)
    preview = load_week_progress.handle(
        LoadCurrentWeekGoalPreviewCommand(
            user=user,
            activity=activity,
            date=current_date,
        )
    )
    text = week_details_text.details_for_week(
        user=user,
        activity=activity,
        date=current_date,
        auto_progress=preview.progress if preview.is_auto else None,
    )
    instructions = [f"HH:MM for {activity_icon(activity)} goal."]
    if preview.is_auto and preview.progress is not None:
        instructions.insert(0, "Auto = suggested goal.")
    return (
        f"{text}\n\n" + "\n".join(instructions),
        goal_set_keyboard(activity, has_auto=preview.is_auto and preview.progress is not None),
    )


def clear_pending_action(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(USER_DATA_PENDING_ACTION, None)


def set_pending_action(
    context: ContextTypes.DEFAULT_TYPE,
    kind: str,
    activity: Activity,
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
            current_week_summary_text.summary_for_current_week(User(user.id))
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
    if not isinstance(kind, str) or not isinstance(activity, Activity) or user_id is None:
        clear_pending_action(context)
        return
    user = User(user_id)

    if kind == "event_yesterday":
        time_value = parse_hhmm(text)
        if time_value is None:
            await update.message.reply_text(
                "HH:MM only.",
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

    if kind == "event_other":
        parsed = parse_past_event_for_user(text, user)
        if parsed is None:
            await update.message.reply_text(
                PAST_OTHER_FORMAT_HINT,
                reply_markup=pending_reply_markup(kind),
            )
            return
        activity_date, activity_time = parsed
        result = record_activity.handle(
            RecordActivityForDayCommand(
                user=user,
                activity=activity,
                activity_date=activity_date,
                activity_time=activity_time,
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

    if kind == "goal_manual":
        target_time = parse_hhmm(text)
        if target_time is None:
            await update.message.reply_text(
                "HH:MM only.",
                reply_markup=pending_reply_markup(kind),
            )
            return
        set_week_goal.handle(
            SetWeekGoalCommand(
                user=user,
                activity=activity,
                week=current_week_for_user(user),
                target_time=target_time,
            )
        )
        clear_pending_action(context)
        await update.message.reply_text(
            week_details_text.details_for_week(
                user=user,
                activity=activity,
                date=current_date_for_user(user),
            ),
            reply_markup=goals_navigation_keyboard(),
        )
        return

    clear_pending_action(context)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or update.effective_user is None:
        return
    user_id = update.effective_user.id
    user = User(user_id)
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
        text = "Input past events"
        reply_markup = past_menu_keyboard()
    elif query.data == "menu:reports":
        clear_pending_action(context)
        text = "Reports"
        reply_markup = reports_menu_keyboard()
    elif query.data == "menu:goals":
        clear_pending_action(context)
        text = goals_report_for_current_week(user)
        reply_markup = goals_menu_keyboard()
    elif query.data.startswith("report_this_week:"):
        clear_pending_action(context)
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            text = week_details_text.details_for_week(
                user=user,
                activity=activity,
                date=current_date_for_user(user),
            )
            reply_markup = reports_navigation_keyboard()
    elif query.data.startswith("report_all:"):
        clear_pending_action(context)
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            text = activity_weeks_report_text.report_for_all_weeks(
                user=user,
                activity=activity,
                date=current_date_for_user(user),
            )
            reply_markup = reports_navigation_keyboard()
    elif query.data.startswith("goal_set:"):
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            set_pending_action(context, "goal_manual", activity)
            text, reply_markup = goal_set_screen_for_current_week(user, activity)
    elif query.data.startswith("goal_auto:"):
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            preview = load_week_progress.handle(
                LoadCurrentWeekGoalPreviewCommand(
                    user=user,
                    activity=activity,
                    date=current_date_for_user(user),
                )
            )
            if preview.is_auto and preview.progress is not None:
                set_week_goal.handle(
                    SetWeekGoalCommand(
                        user=user,
                        activity=activity,
                        week=preview.progress.goal.week,
                        target_time=preview.progress.goal.target_time,
                    )
                )
                clear_pending_action(context)
                text = week_details_text.details_for_week(
                    user=user,
                    activity=activity,
                    date=current_date_for_user(user),
                )
                reply_markup = goals_navigation_keyboard()
            else:
                set_pending_action(context, "goal_manual", activity)
                text, reply_markup = goal_set_screen_for_current_week(user, activity)
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
            text = f"Supported formats for yesterday {activity_icon(activity)}: HH:MM"
            reply_markup = pending_reply_markup("event_yesterday")
    elif query.data.startswith("past_date:"):
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            set_pending_action(context, "event_other", activity)
            text = f"Supported formats for {activity_icon(activity)}: {PAST_OTHER_FORMAT_HINT}"
            reply_markup = pending_reply_markup("event_other")
    elif query.data == "export:data":
        clear_pending_action(context)
        result = export_user_data.handle(ExportUserDataCommand(user=user))
        payload = initial_data_json_bytes.serialize(result)
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=InputFile(
                BytesIO(payload),
                filename=f"nomorebot-export-{user_id}-{current_date_for_user(user).strftime('%Y%m%d')}.json",
            ),
            caption="Data export",
        )
        text = "Export sent."
        reply_markup = reports_navigation_keyboard()
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
    load_dotenv()
    log_level = configure_logging()
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
