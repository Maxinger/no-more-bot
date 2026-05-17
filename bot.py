"""NoMoreBot - Track your activities."""
import datetime
import html
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

from application.tracking_service import TrackingService, monday_of_week_containing
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
from domain.model.record import Activity, activity_day, timestamp_for_activity_day
from infra.dev.initial_data_json_loader import apply_initial_data_fixture as apply_legacy_initial_data_fixture
from infra.tracker.in_memory import InMemoryTracker

logger = logging.getLogger(__name__)
tracking_service = TrackingService(InMemoryTracker())
apply_legacy_initial_data_fixture(tracking_service)
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

WELCOME = (
    "NoMoreBot — track activities and weekly goals.\n\n"
    f"{HOME_ICON} Now and {BED_ICON} Now record an event immediately.\n"
    f"{TIME_ICON} Past lets you save yesterday or a specific date.\n"
    f"{GOALS_ICON} Goals lets you set weekly goals.\n\n"
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
            [InlineKeyboardButton("Cancel", callback_data="menu:main")],
        ]
    )


def goals_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"{HOME_ICON} Current", callback_data="goal_current:home"),
                InlineKeyboardButton(f"{BED_ICON} Current", callback_data="goal_current:bed"),
            ],
            [
                InlineKeyboardButton(f"{HOME_ICON} Past", callback_data="goal_past:home"),
                InlineKeyboardButton(f"{BED_ICON} Past", callback_data="goal_past:bed"),
            ],
            [
                InlineKeyboardButton(f"{HOME_ICON} Report", callback_data="goal_report:home"),
                InlineKeyboardButton(f"{BED_ICON} Report", callback_data="goal_report:bed"),
            ],
            [InlineKeyboardButton("Cancel", callback_data="menu:main")],
        ]
    )


def parse_activity_token(token: str) -> Activity | None:
    t = token.strip().lower()
    if t in ("bed", "going_to_bed"):
        return Activity.BED
    if t in ("home", "going_home"):
        return Activity.HOME
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


def parse_past_goal_week_start(s: str) -> datetime.date | None:
    text = s.strip()
    current_year = datetime.datetime.now(datetime.timezone.utc).year
    for fmt, includes_year in (("%d.%m.%Y", True), ("%d.%m", False)):
        try:
            parsed = datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        if not includes_year:
            parsed = parsed.replace(year=current_year)
        return parsed
    return None


def current_utc_datetime() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def current_date_for_user(user: DddUser) -> datetime.date:
    return current_utc_datetime().astimezone(user.time_zone).date()


def format_goal_week_label(week_start: datetime.date) -> str:
    return f"Week of {week_start.isoformat()} (Mon)"


def format_goals_list(pairs: list[tuple[datetime.date, datetime.time]]) -> str:
    if not pairs:
        return "No goals stored for this activity yet."
    lines = [f"{d.isoformat()}  {t.strftime('%H:%M')}" for d, t in pairs]
    return "\n".join(lines)


def activity_icon(activity: Activity) -> str:
    return HOME_ICON if activity == Activity.HOME else BED_ICON


def activity_name(activity: Activity) -> str:
    return "Home" if activity == Activity.HOME else "Bed"


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
    return InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="menu:main")]])


def build_activity_timestamp(
    activity: Activity,
    day: datetime.date,
    time_value: datetime.time,
) -> datetime.datetime:
    return timestamp_for_activity_day(activity, day, time_value)


def format_saved_event(activity: Activity, timestamp: datetime.datetime) -> str:
    return f"{activity_day(activity, timestamp).strftime('%Y-%m-%d')} {timestamp.strftime('%H:%M')}"


def current_goal_summary(user: DddUser, activity: Activity) -> str:
    week = monday_of_week_containing(current_date_for_user(user))
    try:
        goal = tracking_service.get_goal(activity, week_start=week)
    except KeyError:
        return f"No current goal for {activity_name(activity)} ({format_goal_week_label(week)})."
    return f"Current goal for {activity_name(activity)}: {goal.strftime('%H:%M')} ({format_goal_week_label(week)})."


def format_report_line(day: datetime.date, label: str, time_value: datetime.time) -> str:
    return f"{day.strftime('%d.%m.%Y')}{label}: {time_value.strftime('%H:%M')}"


def minutes_since_midnight(time_value: datetime.time) -> int:
    return time_value.hour * 60 + time_value.minute


def format_signed_minutes(minutes: int) -> str:
    if minutes == 0:
        return "0"
    return f"{minutes:+d}"


def report_day(activity: Activity, timestamp: datetime.datetime) -> datetime.date:
    return activity_day(activity, timestamp)


def goal_delta_minutes(activity: Activity, goal_time: datetime.time, actual_time: datetime.time) -> int:
    """Positive means earlier/better than goal; negative means later."""
    if activity == Activity.BED and goal_time == datetime.time(0, 0) and actual_time.hour == 23:
        return min(actual_time.minute, 60 - actual_time.minute)

    delta = minutes_since_midnight(goal_time) - minutes_since_midnight(actual_time)
    half_day = 12 * 60
    full_day = 24 * 60
    if delta > half_day:
        delta -= full_day
    elif delta <= -half_day:
        delta += full_day
    return delta


def records_by_report_week(
    user_id: int,
    activity: Activity,
) -> dict[datetime.date, list[tuple[datetime.date, datetime.time]]]:
    records_by_week: dict[datetime.date, list[tuple[datetime.date, datetime.time]]] = {}
    for record in tracking_service.history(user_id, days=36500, activity=activity):
        day = report_day(record.activity, record.timestamp)
        week_start = monday_of_week_containing(day)
        records_by_week.setdefault(week_start, []).append((day, record.timestamp.time()))
    return records_by_week


def format_activity_week_report(
    activity: Activity,
    week_start: datetime.date,
    goal_time: datetime.time | None,
    records: list[tuple[datetime.date, datetime.time]],
) -> str:
    lines: list[str] = []
    if goal_time is None:
        lines.append(f"{week_start.strftime('%d.%m.%Y')} goal: (not set)")
    else:
        lines.append(format_report_line(week_start, " goal", goal_time))

    total = 0
    has_delta = False
    for day, time_value in sorted(records, key=lambda item: (item[0], item[1])):
        day_label = day.strftime("%a")
        if goal_time is None:
            lines.append(f"{day_label:<3}  {time_value.strftime('%H:%M')}")
            continue

        delta = goal_delta_minutes(activity, goal_time, time_value)
        total += delta
        has_delta = True
        lines.append(f"{day_label:<3}  {time_value.strftime('%H:%M')}  {format_signed_minutes(delta):>5}")

    lines.append("---")
    if has_delta:
        lines.append(f"Total       {format_signed_minutes(total):>5}")
    return "\n".join(lines)


def format_activity_report(user_id: int, activity: Activity) -> str:
    goals_by_week = dict(tracking_service.get_goals(activity, limit=None))
    records_by_week = records_by_report_week(user_id, activity)
    week_starts = sorted(set(goals_by_week) | set(records_by_week))
    if not week_starts:
        return f"No report data for {activity_name(activity)} yet."

    lines: list[str] = []
    for week_start in week_starts:
        if lines:
            lines.append("")
        lines.append(
            format_activity_week_report(
                activity,
                week_start,
                goals_by_week.get(week_start),
                records_by_week.get(week_start, []),
            )
        )
    return "\n".join(lines)


def format_current_week_report(user: DddUser) -> str:
    week_start = monday_of_week_containing(current_date_for_user(user))
    lines: list[str] = []
    for activity in (Activity.HOME, Activity.BED):
        if lines:
            lines.append("")
        try:
            goal_time = tracking_service.get_goal(activity, week_start=week_start)
        except KeyError:
            goal_time = None
        lines.append(activity_name(activity))
        lines.append(
            format_activity_week_report(
                activity,
                week_start,
                goal_time,
                records_by_report_week(user.id, activity).get(week_start, []),
            )
        )
    return "\n".join(lines)


def monospace_message(text: str) -> str:
    return f"<pre>{html.escape(text)}</pre>"


async def cmd_setgoal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_pending_action(context)
    if not update.message:
        return
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "Usage: /setgoal <bed|home> <HH:MM>\n"
            "Sets your goal for the current week (Monday-Sunday, your timezone).",
            reply_markup=main_menu_keyboard(),
        )
        return
    activity = parse_activity_token(context.args[0])
    time_value = parse_hhmm(context.args[1])
    if activity is None or time_value is None:
        await update.message.reply_text(
            "Could not parse activity or time. Use e.g. /setgoal bed 22:30",
            reply_markup=main_menu_keyboard(),
        )
        return
    user = DddUser(update.effective_user.id) if update.effective_user else None
    week = (
        monday_of_week_containing(current_date_for_user(user))
        if user is not None
        else monday_of_week_containing(current_utc_datetime().date())
    )
    tracking_service.set_goal(activity, time_value, week_start=week)
    await update.message.reply_text(
        f"{activity_icon(activity)} Goal set for {activity_name(activity)} at {time_value.strftime('%H:%M')} "
        f"for {format_goal_week_label(week)}.",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_getgoal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_pending_action(context)
    if not update.message:
        return
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /getgoal <bed|home>\nShows the goal for the current week.",
            reply_markup=main_menu_keyboard(),
        )
        return
    activity = parse_activity_token(context.args[0])
    if activity is None:
        await update.message.reply_text("Unknown activity. Use `bed` or `home`.", reply_markup=main_menu_keyboard())
        return
    user = DddUser(update.effective_user.id) if update.effective_user else None
    week = (
        monday_of_week_containing(current_date_for_user(user))
        if user is not None
        else monday_of_week_containing(current_utc_datetime().date())
    )
    try:
        goal = tracking_service.get_goal(activity, week_start=week)
    except KeyError:
        await update.message.reply_text(
            f"No goal set for {activity_name(activity)} for {format_goal_week_label(week)}.",
            reply_markup=main_menu_keyboard(),
        )
        return
    await update.message.reply_text(
        f"{activity_icon(activity)} {activity_name(activity)}: {goal.strftime('%H:%M')} "
        f"({format_goal_week_label(week)})",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_goals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_pending_action(context)
    if not update.message:
        return
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /goals <bed|home> [limit]\nLists recent goals (default limit 10).",
            reply_markup=main_menu_keyboard(),
        )
        return
    activity = parse_activity_token(context.args[0])
    if activity is None:
        await update.message.reply_text("Unknown activity. Use `bed` or `home`.", reply_markup=main_menu_keyboard())
        return
    limit = 10
    if len(context.args) >= 2:
        try:
            limit = max(1, min(50, int(context.args[1])))
        except ValueError:
            await update.message.reply_text(
                "Limit must be a number between 1 and 50.",
                reply_markup=main_menu_keyboard(),
            )
            return
    pairs = tracking_service.get_goals(activity, limit=limit)
    await update.message.reply_text(format_goals_list(pairs), reply_markup=main_menu_keyboard())


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
    if not isinstance(kind, str) or not isinstance(activity, Activity) or user_id is None:
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
        ddd_activity = DddActivity[activity.name]
        result = record_activity.handle(
            RecordActivityForDayCommand(
                user=user,
                activity=ddd_activity,
                activity_date=day,
                activity_time=time_value,
            )
        )
        saved_ts = result.record.time.to_datetime(user.time_zone)
        tracking_service.record(user_id, activity, saved_ts)
        clear_pending_action(context)
        await update.message.reply_text(
            week_details_text.details_for_week(
                user=user,
                activity=ddd_activity,
                date=result.record.time.date,
            ),
            reply_markup=main_menu_keyboard(),
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
        ddd_activity = DddActivity[activity.name]
        result = record_activity.handle(
            RecordActivityForDayCommand(
                user=user,
                activity=ddd_activity,
                activity_date=timestamp.date(),
                activity_time=timestamp.time(),
            )
        )
        saved_ts = result.record.time.to_datetime(user.time_zone)
        tracking_service.record(user_id, activity, saved_ts)
        clear_pending_action(context)
        await update.message.reply_text(
            week_details_text.details_for_week(
                user=user,
                activity=ddd_activity,
                date=result.record.time.date,
            ),
            reply_markup=main_menu_keyboard(),
        )
        return

    if kind == "goal_current":
        time_value = parse_hhmm(text)
        if time_value is None:
            await update.message.reply_text(
                "Expected HH:MM, for example 22:30. Send /start to cancel.",
                reply_markup=pending_reply_markup(kind),
            )
            return
        week = monday_of_week_containing(current_date_for_user(user))
        tracking_service.set_goal(activity, time_value, week_start=week)
        clear_pending_action(context)
        await update.message.reply_text(
            f"{activity_icon(activity)} Goal set for {activity_name(activity)} at {time_value.strftime('%H:%M')} "
            f"for {format_goal_week_label(week)}.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if kind == "goal_past_week":
        week_start = parse_past_goal_week_start(text)
        if week_start is None:
            await update.message.reply_text(
                "Expected Monday date in `dd.mm.yyyy` or `dd.mm`, for example `07.04.2025`.",
                reply_markup=pending_reply_markup(kind),
            )
            return
        if week_start.weekday() != 0:
            await update.message.reply_text(
                "That date is not a Monday. Please send the Monday of the target week.",
                reply_markup=pending_reply_markup(kind),
            )
            return
        set_pending_action(context, "goal_past_time", activity, week_start=week_start)
        await update.message.reply_text(
            f"Send the goal time for {activity_name(activity)} for {format_goal_week_label(week_start)} "
            "as HH:MM.",
            reply_markup=pending_reply_markup("goal_past_time"),
        )
        return

    if kind == "goal_past_time":
        time_value = parse_hhmm(text)
        week_start = pending.get("week_start")
        if time_value is None:
            await update.message.reply_text(
                "Expected HH:MM, for example 22:30. Send /start to cancel.",
                reply_markup=pending_reply_markup(kind),
            )
            return
        if not isinstance(week_start, datetime.date):
            clear_pending_action(context)
            await update.message.reply_text(
                "Could not determine the target week. Please try again from Goals.",
                reply_markup=main_menu_keyboard(),
            )
            return
        tracking_service.set_goal(activity, time_value, week_start=week_start)
        clear_pending_action(context)
        await update.message.reply_text(
            f"{activity_icon(activity)} Goal set for {activity_name(activity)} at {time_value.strftime('%H:%M')} "
            f"for {format_goal_week_label(week_start)}.",
            reply_markup=main_menu_keyboard(),
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
    reply_markup = main_menu_keyboard()
    parse_mode: str | None = None

    if query.data == "menu:main":
        clear_pending_action(context)
        text = WELCOME
        reply_markup = main_menu_keyboard()
    elif query.data == "menu:past":
        clear_pending_action(context)
        text = (
            "Choose a past event flow.\n\n"
            f"• {HOME_ICON} Yesterday / {BED_ICON} Yesterday expects HH:MM\n"
            f"• {CALENDAR_ICON} Date expects `dd.mm.yyyy HH:MM` or `dd.mm HH:MM`\n\n"
            "Tap Cancel or send /start to return to the main menu."
        )
        reply_markup = past_menu_keyboard()
    elif query.data == "menu:goals":
        clear_pending_action(context)
        text = monospace_message(format_current_week_report(user))
        parse_mode = "HTML"
        reply_markup = goals_menu_keyboard()
    elif query.data.startswith("record_now:"):
        clear_pending_action(context)
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            occurred_at = current_utc_datetime()
            ddd_activity = DddActivity[activity.name]
            result = record_activity.handle(
                RecordActivityNowCommand(
                    user=user,
                    activity=ddd_activity,
                    occurred_at=occurred_at,
                )
            )
            saved_ts = result.record.time.to_datetime(user.time_zone)
            tracking_service.record(user_id, activity, saved_ts)
            text = week_details_text.details_for_week(
                user=user,
                activity=ddd_activity,
                date=result.record.time.date,
            )
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
    elif query.data.startswith("goal_current:"):
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            set_pending_action(context, "goal_current", activity)
            text = current_goal_summary(user, activity) + "\n\nSend the new goal time as HH:MM."
            reply_markup = pending_reply_markup("goal_current")
    elif query.data.startswith("goal_past:"):
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            set_pending_action(context, "goal_past_week", activity)
            text = (
                f"Send the Monday date for the {activity_name(activity)} goal week as "
                "`dd.mm.yyyy` or `dd.mm`."
            )
            reply_markup = pending_reply_markup("goal_past_week")
    elif query.data.startswith("goal_report:"):
        clear_pending_action(context)
        token = query.data.split(":", 1)[1]
        activity = parse_activity_token(token)
        if activity is None:
            text = "Unknown activity."
        else:
            text = monospace_message(format_activity_report(user_id, activity))
            parse_mode = "HTML"
        reply_markup = goals_menu_keyboard()
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
    app.add_handler(MessageHandler(filters.ALL, log_incoming_message), group=-1)
    app.add_handler(CallbackQueryHandler(log_incoming_callback), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setgoal", cmd_setgoal))
    app.add_handler(CommandHandler("getgoal", cmd_getgoal))
    app.add_handler(CommandHandler("goals", cmd_goals))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, maybe_handle_pending_input),
        group=0,
    )
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Starting bot (LOG_LEVEL=%s)...", log_level)
    app.run_polling()


if __name__ == "__main__":
    main()
