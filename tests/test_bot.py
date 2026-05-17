import datetime
import sys
import types
import unittest
from unittest.mock import patch

dotenv_module = types.ModuleType("dotenv")
dotenv_module.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", dotenv_module)

telegram_module = types.ModuleType("telegram")


class InlineKeyboardButton:
    def __init__(self, text: str, callback_data: str | None = None):
        self.text = text
        self.callback_data = callback_data


class InlineKeyboardMarkup:
    def __init__(self, inline_keyboard):
        self.inline_keyboard = inline_keyboard


class BotCommand:
    def __init__(self, command: str, description: str):
        self.command = command
        self.description = description


class Update:
    pass


telegram_module.BotCommand = BotCommand
telegram_module.InlineKeyboardButton = InlineKeyboardButton
telegram_module.InlineKeyboardMarkup = InlineKeyboardMarkup
telegram_module.Update = Update
sys.modules.setdefault("telegram", telegram_module)

telegram_error_module = types.ModuleType("telegram.error")


class BadRequest(Exception):
    pass


telegram_error_module.BadRequest = BadRequest
sys.modules.setdefault("telegram.error", telegram_error_module)

telegram_ext_module = types.ModuleType("telegram.ext")
telegram_ext_module.Application = object
telegram_ext_module.CallbackQueryHandler = object
telegram_ext_module.CommandHandler = object
telegram_ext_module.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
telegram_ext_module.MessageHandler = object
telegram_ext_module.filters = types.SimpleNamespace(ALL=object(), TEXT=object(), COMMAND=object())
sys.modules.setdefault("telegram.ext", telegram_ext_module)

import bot
from domain import Record, RecordTime, WeekGoal, WeekProgress, WeekStart


class BotHelpersTest(unittest.TestCase):
    def test_pending_reply_markup_contains_back_to_menu_button(self) -> None:
        markup = bot.pending_reply_markup("event_yesterday")

        self.assertEqual(len(markup.inline_keyboard[0]), 1)
        self.assertEqual(markup.inline_keyboard[0][0].text, "Back to Menu")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "menu:main")

    def test_past_menu_contains_wide_back_to_menu_button(self) -> None:
        markup = bot.past_menu_keyboard()

        back_row = markup.inline_keyboard[-1]
        self.assertEqual(len(back_row), 1)
        self.assertEqual(back_row[0].text, "Back to Menu")
        self.assertEqual(back_row[0].callback_data, "menu:main")

    def test_goals_menu_contains_back_to_menu_button(self) -> None:
        markup = bot.goals_menu_keyboard()

        self.assertEqual(len(markup.inline_keyboard), 2)
        self.assertEqual(markup.inline_keyboard[0][0].text, "🏠 Set")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "goal_set:home")
        self.assertEqual(markup.inline_keyboard[0][1].text, "🛏️ Set")
        self.assertEqual(markup.inline_keyboard[0][1].callback_data, "goal_set:bed")
        self.assertEqual(markup.inline_keyboard[1][0].text, "Back to Menu")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "menu:main")


class FakeMessage:
    def __init__(self) -> None:
        self.replies = []

    async def reply_text(self, text, reply_markup=None, parse_mode=None):
        self.replies.append(
            {
                "text": text,
                "reply_markup": reply_markup,
                "parse_mode": parse_mode,
            }
        )


class FakeCurrentWeekSummaryText:
    def __init__(self) -> None:
        self.calls = []

    def summary_for_current_week(self, user: bot.User, auto_progress=None) -> str:
        self.calls.append((user.id, auto_progress))
        return f"Current week summary for {user.id}"


class FakeRecordActivity:
    def __init__(self) -> None:
        self.command = None

    def handle(self, command):
        self.command = command
        if hasattr(command, "occurred_at"):
            record_time = RecordTime.from_datetime(command.occurred_at, command.user.time_zone)
        else:
            record_time = RecordTime(command.activity_date, command.activity_time)
        return types.SimpleNamespace(
            record=Record(
                user_id=command.user.id,
                activity=command.activity,
                time=record_time,
            )
        )


class FakeWeekDetailsText:
    def __init__(self) -> None:
        self.calls = []

    def details_for_week(self, user, activity, date, auto_progress=None):
        self.calls.append((user.id, activity, date, auto_progress))
        return f"Week details for {activity.value} on {date.isoformat()}"


class FakeActivityWeeksReportText:
    def __init__(self) -> None:
        self.calls = []

    def report_for_activity(self, user, activity, date):
        self.calls.append((user.id, activity, date))
        return f"Activity weeks report for {activity.value} on {date.isoformat()}"


class FakeLoadWeekProgress:
    def __init__(self, result) -> None:
        self.result = result
        self.commands = []

    def handle(self, command):
        self.commands.append(command)
        return self.result


class FakeSetWeekGoal:
    def __init__(self) -> None:
        self.commands = []

    def handle(self, command):
        self.commands.append(command)
        return types.SimpleNamespace(goal=command, replaced_existing=False)


def make_progress(
    activity: bot.Activity = bot.Activity.HOME,
    week: datetime.date = datetime.date(2026, 5, 11),
    target_time: datetime.time = datetime.time(20, 0),
) -> WeekProgress:
    return WeekProgress(
        goal=WeekGoal(
            user_id=123,
            activity=activity,
            week=WeekStart(week),
            target_time=target_time,
        ),
        records=(),
    )


class FakeCallbackQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.answers = 0
        self.edits = []

    async def answer(self) -> None:
        self.answers += 1

    async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
        self.edits.append(
            {
                "text": text,
                "reply_markup": reply_markup,
                "parse_mode": parse_mode,
            }
        )


class StartHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_replies_with_current_week_summary(self) -> None:
        original_summary_text = bot.current_week_summary_text
        bot.current_week_summary_text = FakeCurrentWeekSummaryText()
        message = FakeMessage()
        context = types.SimpleNamespace(user_data={bot.USER_DATA_PENDING_ACTION: {"kind": "event_date"}})
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123, username="maxi"),
            effective_chat=types.SimpleNamespace(id=456),
            message=message,
        )

        try:
            await bot.start(update, context)
        finally:
            bot.current_week_summary_text = original_summary_text

        self.assertNotIn(bot.USER_DATA_PENDING_ACTION, context.user_data)
        self.assertEqual(len(message.replies), 1)
        self.assertEqual(message.replies[0]["text"], "Current week summary for 123")
        self.assertIsNotNone(message.replies[0]["reply_markup"])


class PendingInputHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_yesterday_recording_replies_with_week_details_for_yesterday(self) -> None:
        original_record_activity = bot.record_activity
        original_week_details_text = bot.week_details_text
        fake_record_activity = FakeRecordActivity()
        fake_week_details_text = FakeWeekDetailsText()
        bot.record_activity = fake_record_activity
        bot.week_details_text = fake_week_details_text
        message = FakeMessage()
        context = types.SimpleNamespace(
            user_data={
                bot.USER_DATA_PENDING_ACTION: {
                    "kind": "event_yesterday",
                    "activity": bot.Activity.HOME,
                }
            }
        )
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            message=types.SimpleNamespace(text="20:01", reply_text=message.reply_text),
        )

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 18, 9, 0, tzinfo=datetime.timezone.utc
                )
                await bot.maybe_handle_pending_input(update, context)
        finally:
            bot.record_activity = original_record_activity
            bot.week_details_text = original_week_details_text

        self.assertIsInstance(fake_record_activity.command, bot.RecordActivityForDayCommand)
        self.assertEqual(fake_record_activity.command.activity_date, datetime.date(2026, 5, 17))
        self.assertEqual(fake_record_activity.command.activity_time, datetime.time(20, 1))
        self.assertEqual(fake_record_activity.command.activity, bot.Activity.HOME)
        self.assertEqual(fake_week_details_text.calls, [(123, bot.Activity.HOME, datetime.date(2026, 5, 17), None)])
        self.assertNotIn(bot.USER_DATA_PENDING_ACTION, context.user_data)
        self.assertEqual(message.replies[0]["text"], "Week details for going_home on 2026-05-17")
        self.assertIsNotNone(message.replies[0]["reply_markup"])

    async def test_yesterday_recording_uses_minsk_date_near_utc_midnight(self) -> None:
        original_record_activity = bot.record_activity
        original_week_details_text = bot.week_details_text
        fake_record_activity = FakeRecordActivity()
        fake_week_details_text = FakeWeekDetailsText()
        bot.record_activity = fake_record_activity
        bot.week_details_text = fake_week_details_text
        message = FakeMessage()
        context = types.SimpleNamespace(
            user_data={
                bot.USER_DATA_PENDING_ACTION: {
                    "kind": "event_yesterday",
                    "activity": bot.Activity.HOME,
                }
            }
        )
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            message=types.SimpleNamespace(text="20:01", reply_text=message.reply_text),
        )

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 17, 22, 30, tzinfo=datetime.timezone.utc
                )
                await bot.maybe_handle_pending_input(update, context)
        finally:
            bot.record_activity = original_record_activity
            bot.week_details_text = original_week_details_text

        self.assertEqual(fake_record_activity.command.activity_date, datetime.date(2026, 5, 17))
        self.assertEqual(fake_week_details_text.calls, [(123, bot.Activity.HOME, datetime.date(2026, 5, 17), None)])

    async def test_past_date_recording_replies_with_week_details_for_entered_date(self) -> None:
        original_record_activity = bot.record_activity
        original_week_details_text = bot.week_details_text
        fake_record_activity = FakeRecordActivity()
        fake_week_details_text = FakeWeekDetailsText()
        bot.record_activity = fake_record_activity
        bot.week_details_text = fake_week_details_text
        message = FakeMessage()
        context = types.SimpleNamespace(
            user_data={
                bot.USER_DATA_PENDING_ACTION: {
                    "kind": "event_date",
                    "activity": bot.Activity.BED,
                }
            }
        )
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            message=types.SimpleNamespace(text="17.05.2026 00:15", reply_text=message.reply_text),
        )

        try:
            await bot.maybe_handle_pending_input(update, context)
        finally:
            bot.record_activity = original_record_activity
            bot.week_details_text = original_week_details_text

        self.assertIsInstance(fake_record_activity.command, bot.RecordActivityForDayCommand)
        self.assertEqual(fake_record_activity.command.activity_date, datetime.date(2026, 5, 17))
        self.assertEqual(fake_record_activity.command.activity_time, datetime.time(0, 15))
        self.assertEqual(fake_record_activity.command.activity, bot.Activity.BED)
        self.assertEqual(fake_week_details_text.calls, [(123, bot.Activity.BED, datetime.date(2026, 5, 17), None)])
        self.assertNotIn(bot.USER_DATA_PENDING_ACTION, context.user_data)
        self.assertEqual(message.replies[0]["text"], "Week details for going_to_bed on 2026-05-17")
        self.assertIsNotNone(message.replies[0]["reply_markup"])

    async def test_goal_manual_input_saves_current_week_goal_and_shows_week_details(self) -> None:
        original_set_week_goal = bot.set_week_goal
        original_week_details_text = bot.week_details_text
        fake_set_week_goal = FakeSetWeekGoal()
        fake_week_details_text = FakeWeekDetailsText()
        bot.set_week_goal = fake_set_week_goal
        bot.week_details_text = fake_week_details_text
        message = FakeMessage()
        context = types.SimpleNamespace(
            user_data={
                bot.USER_DATA_PENDING_ACTION: {
                    "kind": "goal_manual",
                    "activity": bot.Activity.HOME,
                }
            }
        )
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            message=types.SimpleNamespace(text="19:45", reply_text=message.reply_text),
        )

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 14, 9, 0, tzinfo=datetime.timezone.utc
                )
                await bot.maybe_handle_pending_input(update, context)
        finally:
            bot.set_week_goal = original_set_week_goal
            bot.week_details_text = original_week_details_text

        self.assertIsInstance(fake_set_week_goal.commands[0], bot.SetWeekGoalCommand)
        self.assertEqual(fake_set_week_goal.commands[0].week, WeekStart(datetime.date(2026, 5, 11)))
        self.assertEqual(fake_set_week_goal.commands[0].target_time, datetime.time(19, 45))
        self.assertEqual(
            fake_week_details_text.calls,
            [(123, bot.Activity.HOME, datetime.date(2026, 5, 14), None)],
        )
        self.assertNotIn(bot.USER_DATA_PENDING_ACTION, context.user_data)
        self.assertEqual(message.replies[0]["text"], "Week details for going_home on 2026-05-14")
        self.assertEqual(message.replies[0]["reply_markup"].inline_keyboard[0][0].callback_data, "menu:main")

    async def test_goal_manual_input_rejects_invalid_hhmm(self) -> None:
        message = FakeMessage()
        context = types.SimpleNamespace(
            user_data={
                bot.USER_DATA_PENDING_ACTION: {
                    "kind": "goal_manual",
                    "activity": bot.Activity.BED,
                }
            }
        )
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            message=types.SimpleNamespace(text="25:99", reply_text=message.reply_text),
        )

        await bot.maybe_handle_pending_input(update, context)

        self.assertIn(bot.USER_DATA_PENDING_ACTION, context.user_data)
        self.assertEqual(
            message.replies[0]["text"],
            "Expected HH:MM, for example 22:30. Send /start to cancel.",
        )
        self.assertEqual(message.replies[0]["reply_markup"].inline_keyboard[0][0].callback_data, "menu:main")


class CallbackHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_back_to_menu_replies_with_current_week_summary(self) -> None:
        original_summary_text = bot.current_week_summary_text
        bot.current_week_summary_text = FakeCurrentWeekSummaryText()
        query = FakeCallbackQuery("menu:main")
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(user_data={bot.USER_DATA_PENDING_ACTION: {"kind": "event_date"}})

        try:
            await bot.button_callback(update, context)
        finally:
            bot.current_week_summary_text = original_summary_text

        self.assertEqual(query.answers, 1)
        self.assertEqual(query.edits[0]["text"], "Current week summary for 123")
        self.assertNotIn(bot.USER_DATA_PENDING_ACTION, context.user_data)
        self.assertIsNotNone(query.edits[0]["reply_markup"])

    async def test_goals_button_shows_activity_reports_with_back_to_menu(self) -> None:
        original_activity_weeks_report_text = bot.activity_weeks_report_text
        fake_activity_weeks_report_text = FakeActivityWeeksReportText()
        bot.activity_weeks_report_text = fake_activity_weeks_report_text
        query = FakeCallbackQuery("menu:goals")
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(user_data={bot.USER_DATA_PENDING_ACTION: {"kind": "event_date"}})

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 17, 9, 0, tzinfo=datetime.timezone.utc
                )
                await bot.button_callback(update, context)
        finally:
            bot.activity_weeks_report_text = original_activity_weeks_report_text

        self.assertEqual(query.answers, 1)
        self.assertEqual(
            query.edits[0]["text"],
            "\n===============\n".join(
                [
                    "Activity weeks report for going_home on 2026-05-17",
                    "Activity weeks report for going_to_bed on 2026-05-17",
                ]
            ),
        )
        self.assertEqual(
            fake_activity_weeks_report_text.calls,
            [
                (123, bot.Activity.HOME, datetime.date(2026, 5, 17)),
                (123, bot.Activity.BED, datetime.date(2026, 5, 17)),
            ],
        )
        self.assertIsNone(query.edits[0]["parse_mode"])
        self.assertEqual(query.edits[0]["reply_markup"].inline_keyboard[0][0].callback_data, "goal_set:home")
        self.assertNotIn(bot.USER_DATA_PENDING_ACTION, context.user_data)

    async def test_goal_set_button_shows_auto_preview_and_auto_button(self) -> None:
        original_load_week_progress = bot.load_week_progress
        original_week_details_text = bot.week_details_text
        progress = make_progress(target_time=datetime.time(19, 55))
        fake_load_week_progress = FakeLoadWeekProgress(
            types.SimpleNamespace(progress=progress, is_auto=True)
        )
        fake_week_details_text = FakeWeekDetailsText()
        bot.load_week_progress = fake_load_week_progress
        bot.week_details_text = fake_week_details_text
        query = FakeCallbackQuery("goal_set:home")
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(user_data={})

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 14, 9, 0, tzinfo=datetime.timezone.utc
                )
                await bot.button_callback(update, context)
        finally:
            bot.load_week_progress = original_load_week_progress
            bot.week_details_text = original_week_details_text

        self.assertEqual(query.answers, 1)
        self.assertIn("Week details for going_home on 2026-05-14", query.edits[0]["text"])
        self.assertIn("Tap Auto", query.edits[0]["text"])
        self.assertEqual(
            fake_week_details_text.calls[0],
            (123, bot.Activity.HOME, datetime.date(2026, 5, 14), progress),
        )
        self.assertEqual(query.edits[0]["reply_markup"].inline_keyboard[0][0].text, "Auto")
        self.assertEqual(query.edits[0]["reply_markup"].inline_keyboard[0][0].callback_data, "goal_auto:home")
        self.assertEqual(
            context.user_data[bot.USER_DATA_PENDING_ACTION],
            {"kind": "goal_manual", "activity": bot.Activity.HOME},
        )

    async def test_goal_set_button_without_previous_goal_allows_manual_only(self) -> None:
        original_load_week_progress = bot.load_week_progress
        original_week_details_text = bot.week_details_text
        fake_load_week_progress = FakeLoadWeekProgress(
            types.SimpleNamespace(progress=None, is_auto=False)
        )
        fake_week_details_text = FakeWeekDetailsText()
        bot.load_week_progress = fake_load_week_progress
        bot.week_details_text = fake_week_details_text
        query = FakeCallbackQuery("goal_set:bed")
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(user_data={})

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 14, 9, 0, tzinfo=datetime.timezone.utc
                )
                await bot.button_callback(update, context)
        finally:
            bot.load_week_progress = original_load_week_progress
            bot.week_details_text = original_week_details_text

        self.assertNotIn("Tap Auto", query.edits[0]["text"])
        self.assertIn("Send HH:MM", query.edits[0]["text"])
        self.assertEqual(
            fake_week_details_text.calls[0][1:],
            (bot.Activity.BED, datetime.date(2026, 5, 14), None),
        )
        self.assertEqual(len(query.edits[0]["reply_markup"].inline_keyboard), 1)
        self.assertEqual(query.edits[0]["reply_markup"].inline_keyboard[0][0].callback_data, "menu:main")

    async def test_goal_auto_button_saves_recommended_goal_and_shows_week_details(self) -> None:
        original_load_week_progress = bot.load_week_progress
        original_set_week_goal = bot.set_week_goal
        original_week_details_text = bot.week_details_text
        progress = make_progress(activity=bot.Activity.BED, target_time=datetime.time(22, 25))
        bot.load_week_progress = FakeLoadWeekProgress(
            types.SimpleNamespace(progress=progress, is_auto=True)
        )
        fake_set_week_goal = FakeSetWeekGoal()
        fake_week_details_text = FakeWeekDetailsText()
        bot.set_week_goal = fake_set_week_goal
        bot.week_details_text = fake_week_details_text
        query = FakeCallbackQuery("goal_auto:bed")
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(user_data={bot.USER_DATA_PENDING_ACTION: {"kind": "goal_manual"}})

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 14, 9, 0, tzinfo=datetime.timezone.utc
                )
                await bot.button_callback(update, context)
        finally:
            bot.load_week_progress = original_load_week_progress
            bot.set_week_goal = original_set_week_goal
            bot.week_details_text = original_week_details_text

        self.assertIsInstance(fake_set_week_goal.commands[0], bot.SetWeekGoalCommand)
        self.assertEqual(fake_set_week_goal.commands[0].activity, bot.Activity.BED)
        self.assertEqual(fake_set_week_goal.commands[0].week, WeekStart(datetime.date(2026, 5, 11)))
        self.assertEqual(fake_set_week_goal.commands[0].target_time, datetime.time(22, 25))
        self.assertEqual(
            fake_week_details_text.calls,
            [(123, bot.Activity.BED, datetime.date(2026, 5, 14), None)],
        )
        self.assertNotIn(bot.USER_DATA_PENDING_ACTION, context.user_data)
        self.assertEqual(query.edits[0]["text"], "Week details for going_to_bed on 2026-05-14")
        self.assertEqual(query.edits[0]["reply_markup"].inline_keyboard[0][0].callback_data, "menu:main")

    async def test_record_now_uses_minsk_timezone_near_utc_midnight(self) -> None:
        original_record_activity = bot.record_activity
        original_week_details_text = bot.week_details_text
        fake_record_activity = FakeRecordActivity()
        fake_week_details_text = FakeWeekDetailsText()
        bot.record_activity = fake_record_activity
        bot.week_details_text = fake_week_details_text
        query = FakeCallbackQuery("record_now:bed")
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(user_data={})

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 17, 22, 30, 45, tzinfo=datetime.timezone.utc
                )
                await bot.button_callback(update, context)
        finally:
            bot.record_activity = original_record_activity
            bot.week_details_text = original_week_details_text

        self.assertEqual(query.answers, 1)
        self.assertIsInstance(fake_record_activity.command, bot.RecordActivityNowCommand)
        self.assertEqual(fake_record_activity.command.user.id, 123)
        self.assertEqual(
            fake_record_activity.command.occurred_at,
            datetime.datetime(2026, 5, 17, 22, 30, 45, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(
            fake_record_activity.command.occurred_at.astimezone(
                fake_record_activity.command.user.time_zone
            ).time(),
            datetime.time(1, 30, 45),
        )
        self.assertEqual(fake_record_activity.command.activity, bot.Activity.BED)
        self.assertEqual(fake_week_details_text.calls, [(123, bot.Activity.BED, datetime.date(2026, 5, 17), None)])
        self.assertEqual(query.edits[0]["text"], "Week details for going_to_bed on 2026-05-17")


if __name__ == "__main__":
    unittest.main()
