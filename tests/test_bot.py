import datetime
import sys
import types
import unittest

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

    def test_format_activity_report_merges_goals_and_records_sorted_by_date(self) -> None:
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
            datetime.datetime(2026, 4, 7, 8, 45, tzinfo=datetime.timezone.utc),
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
                    "06.04.2026: 19:15",
                    "07.04.2026: 08:45",
                    "13.04.2026 goal: 18:30",
                    "13.04.2026: 20:00",
                ]
            ),
        )

    def test_pending_reply_markup_contains_cancel_button(self) -> None:
        markup = bot.pending_reply_markup("goal_current")

        self.assertEqual(markup.inline_keyboard[0][0].text, "Cancel")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "menu:main")


if __name__ == "__main__":
    unittest.main()
