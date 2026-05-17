import datetime
import unittest

from ddd.representation.formatting_utils import (
    format_reward,
    format_time,
)


class ProgressTextFormatTest(unittest.TestCase):
    def test_format_time(self) -> None:
        self.assertEqual(
            format_time(datetime.time(22, 5)),
            "22:05",
        )

    def test_format_reward_zero(self) -> None:
        self.assertEqual(format_reward(0), "⚪ +0")

    def test_format_reward_signed(self) -> None:
        self.assertEqual(format_reward(15), "🟢 +15")
        self.assertEqual(format_reward(-5), "🔴 -5")

    def test_format_reward_accepts_custom_color_scheme(self) -> None:
        self.assertEqual(format_reward(15, "👍➖❌"), "👍 +15")
        self.assertEqual(format_reward(0, "👍➖❌"), "➖ +0")
        self.assertEqual(format_reward(-5, "👍➖❌"), "❌ -5")


if __name__ == "__main__":
    unittest.main()
