# Telegram bot on aiogram + Telethon

Bot features:

- access only for allowed Telegram IDs;
- admins can be set in `.env` and added inside the bot;
- Telethon account can be added by phone number from the admin menu;
- login flow supports code and 2FA password;
- auto reaction rules can be configured from the bot.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env`:

- `BOT_TOKEN` - token from BotFather
- `API_ID` and `API_HASH` - from https://my.telegram.org
- `BOT_OWNER_ID` - your Telegram numeric ID
- `ADMINS` - comma separated admin IDs
- `ALLOWED_USERS` - comma separated allowed IDs

## Run

```bash
python3 -m app.main
```

## Docker

```bash
cp .env.example .env
docker compose up --build -d
```

Stop:

```bash
docker compose down
```

## How it works

1. Start the bot from an allowed Telegram account.
2. Открой меню администратора и нажми `Добавить аккаунт`.
3. Отправь номер телефона в международном формате.
4. Отправь код входа из Telegram.
5. Если Telegram попросит облачный пароль, отправь его боту.
6. Используй `Добавить правило реакции` и отправь:

```text
account_id group_id target_user_id emoji
```

Example:

```text
1 -1001234567890 123456789 👍
```

После этого выбранный Telethon-аккаунт будет пытаться ставить выбранную реакцию на новые сообщения этого пользователя в указанной группе.

## Notes

- `group_id` должен быть настоящим ID группы/чата, обычно для супергрупп он начинается с `-100`.
- `target_user_id` должен быть настоящим числовым Telegram ID пользователя.
- Telethon-аккаунт должен состоять в этой группе и видеть сообщения нужного пользователя.
- Sessions are stored in the `sessions/` folder.
- Current implementation stores settings in SQLite.
- In Docker, sessions and SQLite database are mounted from the project folder.
