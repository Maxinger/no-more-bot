import datetime
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
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


class InputFile:
    def __init__(self, file_obj, filename: str | None = None):
        self.file_obj = file_obj
        self.filename = filename


class BotCommand:
    def __init__(self, command: str, description: str):
        self.command = command
        self.description = description


class Update:
    pass


telegram_module.BotCommand = BotCommand
telegram_module.InlineKeyboardButton = InlineKeyboardButton
telegram_module.InlineKeyboardMarkup = InlineKeyboardMarkup
telegram_module.InputFile = InputFile
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

_BOT_TEST_TEMP_DIR = tempfile.TemporaryDirectory()
os.environ[  # Keep bot import-time repository bootstrap out of the workspace.
    "DB_PATH"
] = str(Path(_BOT_TEST_TEMP_DIR.name) / "bot-test.sqlite3")

import bot
from domain import Activity, Record, RecordTime, WeekGoal, WeekProgress, WeekStart


class BotRepositoryBootstrapTest(unittest.TestCase):
    def write_initial_data(
        self,
        directory: Path,
        *,
        time_value: str = "20:42",
    ) -> Path:
        path = directory / "initial-data.json"
        path.write_text(
            json.dumps(
                {
                    "user_id": 123,
                    "weeks": [
                        {
                            "startDate": "2026-04-06",
                            "goals": {"work": "20:10"},
                            "data": {"work": {"mon": time_value}},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_database_path_from_environment_honors_configured_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "configured.sqlite3"

            with patch.dict(os.environ, {bot.DATABASE_PATH_ENV_VAR: str(db_path)}):
                self.assertEqual(bot.database_path_from_environment(), db_path)

    def test_repository_backend_defaults_to_db(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(bot.REPOSITORY_BACKEND_ENV_VAR, None)
            self.assertEqual(bot.repository_backend_from_environment(), "db")

    def test_repository_backend_honors_memory(self) -> None:
        with patch.dict(os.environ, {bot.REPOSITORY_BACKEND_ENV_VAR: "memory"}):
            self.assertEqual(bot.repository_backend_from_environment(), "memory")

    def test_invalid_repository_backend_exits(self) -> None:
        with patch.dict(os.environ, {bot.REPOSITORY_BACKEND_ENV_VAR: "postgres"}):
            with self.assertRaises(SystemExit):
                bot.repository_backend_from_environment()

    def test_build_repositories_creates_and_seeds_missing_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            db_path = directory / "bot.sqlite3"
            initial_data_path = self.write_initial_data(directory)

            repositories = bot.build_repositories(
                db_path,
                initial_data_path=initial_data_path,
                backend="db",
            )

            self.assertTrue(db_path.exists())
            week = WeekStart(datetime.date(2026, 4, 6))
            self.assertEqual(
                repositories.goals.find(123, Activity.HOME, week).target_time,
                datetime.time(20, 10),
            )
            self.assertEqual(
                repositories.records.find(123, Activity.HOME, datetime.date(2026, 4, 6)).time,
                RecordTime(datetime.date(2026, 4, 6), datetime.time(20, 42)),
            )

    def test_build_repositories_seeds_existing_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            db_path = directory / "bot.sqlite3"
            db_path.touch()
            initial_data_path = self.write_initial_data(directory)

            repositories = bot.build_repositories(
                db_path,
                initial_data_path=initial_data_path,
                backend="db",
            )

            self.assertEqual(
                repositories.records.find(123, Activity.HOME, datetime.date(2026, 4, 6)).time,
                RecordTime(datetime.date(2026, 4, 6), datetime.time(20, 42)),
            )

    def test_build_repositories_does_not_seed_non_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            db_path = directory / "bot.sqlite3"
            first_initial_data_path = self.write_initial_data(directory, time_value="20:42")
            repositories = bot.build_repositories(
                db_path,
                initial_data_path=first_initial_data_path,
                backend="db",
            )
            second_initial_data_path = self.write_initial_data(directory, time_value="19:30")

            restarted_repositories = bot.build_repositories(
                db_path,
                initial_data_path=second_initial_data_path,
                backend="db",
            )

            self.assertEqual(
                restarted_repositories.records.find(
                    123, Activity.HOME, datetime.date(2026, 4, 6)
                ).time,
                RecordTime(datetime.date(2026, 4, 6), datetime.time(20, 42)),
            )
            self.assertEqual(
                repositories.records.find(123, Activity.HOME, datetime.date(2026, 4, 6)).time,
                RecordTime(datetime.date(2026, 4, 6), datetime.time(20, 42)),
            )

    def test_build_repositories_memory_backend_seeds_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            initial_data_path = self.write_initial_data(Path(tmp))

            repositories = bot.build_repositories(
                initial_data_path=initial_data_path,
                backend="memory",
            )

            week = WeekStart(datetime.date(2026, 4, 6))
            self.assertEqual(
                repositories.goals.find(123, Activity.HOME, week).target_time,
                datetime.time(20, 10),
            )
            self.assertEqual(
                repositories.records.find(123, Activity.HOME, datetime.date(2026, 4, 6)).time,
                RecordTime(datetime.date(2026, 4, 6), datetime.time(20, 42)),
            )


class BotHelpersTest(unittest.TestCase):
    def test_main_menu_contains_reports_button_not_export(self) -> None:
        markup = bot.main_menu_keyboard()

        self.assertEqual(len(markup.inline_keyboard), 3)
        reports_row = markup.inline_keyboard[2]
        self.assertEqual(len(reports_row), 1)
        self.assertEqual(reports_row[0].text, "📊 Reports")
        self.assertEqual(reports_row[0].callback_data, "menu:reports")
        all_callback_data = {
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
        }
        self.assertNotIn("export:data", all_callback_data)

    def test_reports_navigation_keyboard(self) -> None:
        markup = bot.reports_navigation_keyboard()

        self.assertEqual(len(markup.inline_keyboard), 1)
        self.assertEqual(len(markup.inline_keyboard[0]), 2)
        self.assertEqual(markup.inline_keyboard[0][0].text, "Back to Reports")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "menu:reports")
        self.assertEqual(markup.inline_keyboard[0][1].text, "Back to Menu")
        self.assertEqual(markup.inline_keyboard[0][1].callback_data, "menu:main")

    def test_reports_menu_keyboard(self) -> None:
        markup = bot.reports_menu_keyboard()

        self.assertEqual(markup.inline_keyboard[0][0].text, "🏠 This week")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "report_this_week:home")
        self.assertEqual(markup.inline_keyboard[0][1].text, "🛏️ This week")
        self.assertEqual(markup.inline_keyboard[0][1].callback_data, "report_this_week:bed")
        self.assertEqual(markup.inline_keyboard[1][0].text, "🏠 All")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "report_all:home")
        self.assertEqual(markup.inline_keyboard[1][1].text, "🛏️ All")
        self.assertEqual(markup.inline_keyboard[1][1].callback_data, "report_all:bed")
        self.assertEqual(markup.inline_keyboard[2][0].text, "Export")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "export:data")
        self.assertEqual(markup.inline_keyboard[3][0].text, "Back to Menu")
        self.assertEqual(markup.inline_keyboard[3][0].callback_data, "menu:main")

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
        self.all_weeks_calls = []

    def report_for_activity(self, user, activity, date):
        self.calls.append((user.id, activity, date))
        return f"Activity weeks report for {activity.value} on {date.isoformat()}"

    def report_for_all_weeks(self, user, activity, date):
        self.all_weeks_calls.append((user.id, activity, date))
        return f"All weeks report for {activity.value} on {date.isoformat()}"


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
    def __init__(self, data: str, *, chat_id: int = 456) -> None:
        self.data = data
        self.message = types.SimpleNamespace(chat_id=chat_id)
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


class FakeBot:
    def __init__(self) -> None:
        self.documents = []

    async def send_document(self, chat_id, document, caption=None):
        self.documents.append(
            {
                "chat_id": chat_id,
                "document": document,
                "caption": caption,
            }
        )


class FakeExportUserData:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.commands = []

    def handle(self, command):
        self.commands.append(command)
        return types.SimpleNamespace(user_id=command.user.id, weeks=())


class FakeInitialDataJsonBytes:
    def serialize(self, result) -> bytes:
        return json.dumps({"user_id": result.user_id, "weeks": []}).encode("utf-8")


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
            "HH:MM only.",
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
        self.assertIn("Auto = suggested goal.", query.edits[0]["text"])
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

        self.assertNotIn("Auto = suggested goal.", query.edits[0]["text"])
        self.assertIn("HH:MM for Bed goal.", query.edits[0]["text"])
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

    async def test_export_button_sends_document_and_shows_confirmation(self) -> None:
        original_export_user_data = bot.export_user_data
        original_initial_data_json_bytes = bot.initial_data_json_bytes
        fake_export = FakeExportUserData(123)
        fake_serializer = FakeInitialDataJsonBytes()
        bot.export_user_data = fake_export
        bot.initial_data_json_bytes = fake_serializer
        fake_bot = FakeBot()
        query = FakeCallbackQuery("export:data", chat_id=789)
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(
            user_data={bot.USER_DATA_PENDING_ACTION: {"kind": "goal_manual"}},
            bot=fake_bot,
        )

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 19, 9, 0, tzinfo=datetime.timezone.utc
                )
                await bot.button_callback(update, context)
        finally:
            bot.export_user_data = original_export_user_data
            bot.initial_data_json_bytes = original_initial_data_json_bytes

        self.assertEqual(query.answers, 1)
        self.assertNotIn(bot.USER_DATA_PENDING_ACTION, context.user_data)
        self.assertEqual(len(fake_export.commands), 1)
        self.assertEqual(fake_export.commands[0].user.id, 123)
        self.assertEqual(len(fake_bot.documents), 1)
        self.assertEqual(fake_bot.documents[0]["chat_id"], 789)
        self.assertEqual(fake_bot.documents[0]["caption"], "Data export")
        self.assertEqual(
            fake_bot.documents[0]["document"].filename,
            "nomorebot-export-123-20260519.json",
        )
        self.assertEqual(query.edits[0]["text"], "Export sent.")
        markup = query.edits[0]["reply_markup"]
        self.assertEqual(markup.inline_keyboard[0][0].text, "Back to Reports")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "menu:reports")
        self.assertEqual(markup.inline_keyboard[0][1].text, "Back to Menu")
        self.assertEqual(markup.inline_keyboard[0][1].callback_data, "menu:main")

    async def test_reports_button_shows_reports_menu(self) -> None:
        query = FakeCallbackQuery("menu:reports")
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(user_data={bot.USER_DATA_PENDING_ACTION: {"kind": "event_date"}})

        await bot.button_callback(update, context)

        self.assertEqual(query.answers, 1)
        self.assertIn("Reports", query.edits[0]["text"])
        self.assertEqual(
            query.edits[0]["reply_markup"].inline_keyboard[0][0].callback_data,
            "report_this_week:home",
        )
        self.assertNotIn(bot.USER_DATA_PENDING_ACTION, context.user_data)

    async def test_report_this_week_home_shows_week_details(self) -> None:
        original_week_details_text = bot.week_details_text
        fake_week_details_text = FakeWeekDetailsText()
        bot.week_details_text = fake_week_details_text
        query = FakeCallbackQuery("report_this_week:home")
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(user_data={})

        try:
            with patch("bot.current_utc_datetime") as mock_now:
                mock_now.return_value = datetime.datetime(
                    2026, 5, 17, 9, 0, tzinfo=datetime.timezone.utc
                )
                await bot.button_callback(update, context)
        finally:
            bot.week_details_text = original_week_details_text

        self.assertEqual(query.answers, 1)
        self.assertEqual(
            fake_week_details_text.calls,
            [(123, bot.Activity.HOME, datetime.date(2026, 5, 17), None)],
        )
        self.assertEqual(query.edits[0]["text"], "Week details for going_home on 2026-05-17")
        self.assertEqual(query.edits[0]["reply_markup"].inline_keyboard[0][0].callback_data, "menu:reports")
        self.assertEqual(query.edits[0]["reply_markup"].inline_keyboard[0][1].callback_data, "menu:main")

    async def test_report_all_home_shows_all_weeks_report(self) -> None:
        original_activity_weeks_report_text = bot.activity_weeks_report_text
        fake_activity_weeks_report_text = FakeActivityWeeksReportText()
        bot.activity_weeks_report_text = fake_activity_weeks_report_text
        query = FakeCallbackQuery("report_all:home")
        update = types.SimpleNamespace(
            effective_user=types.SimpleNamespace(id=123),
            callback_query=query,
        )
        context = types.SimpleNamespace(user_data={})

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
            fake_activity_weeks_report_text.all_weeks_calls,
            [(123, bot.Activity.HOME, datetime.date(2026, 5, 17))],
        )
        self.assertEqual(query.edits[0]["text"], "All weeks report for going_home on 2026-05-17")
        self.assertEqual(query.edits[0]["reply_markup"].inline_keyboard[0][0].callback_data, "menu:reports")
        self.assertEqual(query.edits[0]["reply_markup"].inline_keyboard[0][1].callback_data, "menu:main")

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
