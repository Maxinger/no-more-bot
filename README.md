# NoMoreBot

A minimal Telegram bot to track activities. Two buttons: record now and show history.

## Setup

1. Create a bot named "NoMoreBot" via [@BotFather](https://t.me/BotFather) and get your token.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your token:
   ```
   cp .env.example .env
   ```
   Edit `.env` and set `TELEGRAM_BOT_TOKEN=your_actual_token`.
4. Run the bot:
   ```
   python bot.py
   ```

## Usage

- **Record now** — Saves the current time (UTC) as an activity.
- **Show history** — Displays activity records for the last 14 days.

Data is stored in a local SQLite database (`no-more.db`).
