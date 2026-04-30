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
from application.tracking_service import TrackingService
from domain.model.record import Activity
from infra.tracker.in_memory import InMemoryTracker


class BotHelpersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_tracking_service = bot.tracking_service
        bot.tracking_service = TrackingService(InMemoryTracker())

    def tearDown(self) -> None:
        bot.tracking_service = self.original_tracking_service

    def test_format_activity_report_groups_records_by_goal_week_with_deltas(self) -> None:
        user_id = 123
        bot.tracking_service.set_goal(Activity.HOME, datetime.time(18, 0), datetime.date(2026, 4, 6))
        bot.tracking_service.set_goal(Activity.HOME, datetime.time(18, 30), datetime.date(2026, 4, 13))
        bot.tracking_service.record(
            user_id,
            Activity.HOME,
            datetime.datetime(2026, 4, 6, 19, 15, tzinfo=datetime.timezone.utc),
        )
        bot.tracking_service.record(
            user_id,
            Activity.HOME,
            datetime.datetime(2026, 4, 7, 18, 45, tzinfo=datetime.timezone.utc),
        )
        bot.tracking_service.record(
            user_id,
            Activity.HOME,
            datetime.datetime(2026, 4, 13, 20, 0, tzinfo=datetime.timezone.utc),
        )

        report = bot.format_activity_report(user_id, Activity.HOME)

        self.assertEqual(
            report,
            "\n".join(
                [
                    "06.04.2026 goal: 18:00",
                    "Mon  19:15    -75",
                    "Tue  18:45    -45",
                    "---",
                    "Total        -120",
                    "",
                    "13.04.2026 goal: 18:30",
                    "Mon  20:00    -90",
                    "---",
                    "Total         -90",
                ]
            ),
        )

    def test_format_activity_report_uses_previous_day_for_after_midnight_bed(self) -> None:
        user_id = 123
        bot.tracking_service.record(
            user_id,
            Activity.BED,
            datetime.datetime(2026, 4, 7, 0, 15, tzinfo=datetime.timezone.utc),
        )

        report = bot.format_activity_report(user_id, Activity.BED)

        self.assertEqual(
            report,
            "\n".join(
                [
                    "06.04.2026 goal: (not set)",
                    "Mon  00:15",
                    "---",
                ]
            ),
        )

    def test_bed_report_matches_midnight_goal_format(self) -> None:
        user_id = 123
        bot.tracking_service.set_goal(Activity.BED, datetime.time(0, 0), datetime.date(2026, 3, 30))
        for timestamp in (
            datetime.datetime(2026, 3, 31, 0, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 1, 0, 4, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 2, 0, 5, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 3, 0, 3, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 4, 23, 15, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 5, 23, 32, tzinfo=datetime.timezone.utc),
        ):
            bot.tracking_service.record(user_id, Activity.BED, timestamp)

        report = bot.format_activity_report(user_id, Activity.BED)

        self.assertEqual(
            report,
            "\n".join(
                [
                    "30.03.2026 goal: 00:00",
                    "Mon  00:00      0",
                    "Tue  00:04     -4",
                    "Wed  00:05     -5",
                    "Thu  00:03     -3",
                    "Sat  23:15    +15",
                    "Sun  23:32    +28",
                    "---",
                    "Total         +31",
                ]
            ),
        )

    def test_goal_delta_minutes_handles_midnight_wraparound(self) -> None:
        goal = datetime.time(0, 0)

        self.assertEqual(bot.goal_delta_minutes(Activity.BED, goal, datetime.time(0, 4)), -4)
        self.assertEqual(bot.goal_delta_minutes(Activity.BED, goal, datetime.time(23, 32)), 28)

    def test_bed_report_keeps_before_midnight_records_on_their_day(self) -> None:
        user_id = 123
        bot.tracking_service.set_goal(Activity.BED, datetime.time(23, 55), datetime.date(2026, 4, 6))
        for timestamp in (
            datetime.datetime(2026, 4, 7, 0, 10, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 7, 23, 50, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 8, 23, 45, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 11, 0, 5, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 12, 0, 15, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 4, 12, 23, 25, tzinfo=datetime.timezone.utc),
        ):
            bot.tracking_service.record(user_id, Activity.BED, timestamp)

        report = bot.format_activity_report(user_id, Activity.BED)

        self.assertEqual(
            report,
            "\n".join(
                [
                    "06.04.2026 goal: 23:55",
                    "Mon  00:10    -15",
                    "Tue  23:50     +5",
                    "Wed  23:45    +10",
                    "Fri  00:05    -10",
                    "Sat  00:15    -20",
                    "Sun  23:25    +30",
                    "---",
                    "Total           0",
                ]
            ),
        )

    @patch("bot.current_utc_datetime")
    def test_format_current_week_report_only_shows_current_week(self, mock_now: object) -> None:
        mock_now.return_value = datetime.datetime(2026, 4, 30, 9, 0, tzinfo=datetime.timezone.utc)
        user_id = 123
        bot.tracking_service.set_goal(Activity.HOME, datetime.time(20, 10), datetime.date(2026, 4, 20))
        bot.tracking_service.set_goal(Activity.HOME, datetime.time(20, 20), datetime.date(2026, 4, 27))
        bot.tracking_service.set_goal(Activity.BED, datetime.time(0, 0), datetime.date(2026, 4, 27))
        bot.tracking_service.record(
            user_id,
            Activity.HOME,
            datetime.datetime(2026, 4, 22, 20, 0, tzinfo=datetime.timezone.utc),
        )
        bot.tracking_service.record(
            user_id,
            Activity.HOME,
            datetime.datetime(2026, 4, 29, 20, 5, tzinfo=datetime.timezone.utc),
        )
        bot.tracking_service.record(
            user_id,
            Activity.BED,
            datetime.datetime(2026, 4, 27, 23, 50, tzinfo=datetime.timezone.utc),
        )
        bot.tracking_service.record(
            user_id,
            Activity.BED,
            datetime.datetime(2026, 4, 30, 0, 15, tzinfo=datetime.timezone.utc),
        )

        report = bot.format_current_week_report(user_id)

        self.assertEqual(
            report,
            "\n".join(
                [
                    "Home",
                    "27.04.2026 goal: 20:20",
                    "Wed  20:05    +15",
                    "---",
                    "Total         +15",
                    "",
                    "Bed",
                    "27.04.2026 goal: 00:00",
                    "Mon  23:50    +10",
                    "Wed  00:15    -15",
                    "---",
                    "Total          -5",
                ]
            ),
        )
        self.assertNotIn("20.04.2026", report)

    def test_pending_reply_markup_contains_cancel_button(self) -> None:
        markup = bot.pending_reply_markup("goal_current")

        self.assertEqual(markup.inline_keyboard[0][0].text, "Cancel")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "menu:main")

    def test_past_menu_contains_cancel_button(self) -> None:
        markup = bot.past_menu_keyboard()

        cancel_button = markup.inline_keyboard[-1][0]
        self.assertEqual(cancel_button.text, "Cancel")
        self.assertEqual(cancel_button.callback_data, "menu:main")

    def test_goals_menu_contains_cancel_button(self) -> None:
        markup = bot.goals_menu_keyboard()

        cancel_button = markup.inline_keyboard[-1][0]
        self.assertEqual(cancel_button.text, "Cancel")
        self.assertEqual(cancel_button.callback_data, "menu:main")


if __name__ == "__main__":
    unittest.main()
