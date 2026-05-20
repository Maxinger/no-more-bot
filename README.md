# NoMoreBot

A minimal Telegram bot to track activities with a domain-driven implementation.

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
   Optionally set `REPOSITORY_BACKEND` to `db` (default) or `memory`, and
   `DB_PATH` when using `db` (defaults to `data/no-more-bot.sqlite3`).
4. Run the bot:
   ```
   py bot.py
   ```

## Usage

- **Now** — Saves a home or bed activity immediately.
- **Past** — Saves a home or bed activity for yesterday or a specific date/time.
- **Goals** — Shows recent progress and lets you set activity goals.

By default, data is stored in SQLite (`REPOSITORY_BACKEND=db`). When the
configured database does not exist, or when the main tables are empty, the bot
creates the schema and loads `tests/initial-data.json` as starter data.

Set `REPOSITORY_BACKEND=memory` for an in-memory store (data is lost on restart;
starter data is loaded from `tests/initial-data.json` each time).
