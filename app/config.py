from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _parse_ids(value: str | None) -> set[int]:
    if not value:
        return set()
    result: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            result.add(int(item))
    return result


@dataclass(slots=True)
class Config:
    bot_token: str
    api_id: int
    api_hash: str
    bot_owner_id: int
    default_admins: set[int]
    default_allowed_users: set[int]
    database_path: Path
    session_dir: Path


def load_config() -> Config:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    api_id = int(os.getenv("API_ID", "0").strip() or "0")
    api_hash = os.getenv("API_HASH", "").strip()
    bot_owner_id = int(os.getenv("BOT_OWNER_ID", "0").strip() or "0")

    if not bot_token or not api_id or not api_hash or not bot_owner_id:
        raise RuntimeError(
            "Fill BOT_TOKEN, API_ID, API_HASH and BOT_OWNER_ID in .env before starting the bot."
        )

    database_path = Path(os.getenv("DATABASE_PATH", "bot.sqlite3")).expanduser().resolve()
    session_dir = Path(os.getenv("SESSION_DIR", "sessions")).expanduser().resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        bot_token=bot_token,
        api_id=api_id,
        api_hash=api_hash,
        bot_owner_id=bot_owner_id,
        default_admins=_parse_ids(os.getenv("ADMINS")),
        default_allowed_users=_parse_ids(os.getenv("ALLOWED_USERS")),
        database_path=database_path,
        session_dir=session_dir,
    )
