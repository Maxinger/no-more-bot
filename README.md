# NoMoreBot

A minimal Telegram bot to track activities with a DDD learning-path implementation.

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
   py bot.py
   ```

## Usage

- **Now** — Saves a home or bed activity immediately.
- **Past** — Saves a home or bed activity for yesterday or a specific date/time.
- **Goals** — Placeholder for the future goals workflow.

Data is stored in memory, so records are reset when the bot process restarts.
