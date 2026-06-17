from __future__ import annotations

from app.config import Config
from app.database import Database


class AccessService:
    def __init__(self, db: Database, config: Config) -> None:
        self.db = db
        self.config = config
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO admins(user_id) VALUES (?)",
                (self.config.bot_owner_id,),
            )
            for user_id in self.config.default_admins:
                conn.execute("INSERT OR IGNORE INTO admins(user_id) VALUES (?)", (user_id,))
            for user_id in self.config.default_allowed_users | {
                self.config.bot_owner_id,
                *self.config.default_admins,
            }:
                conn.execute(
                    "INSERT OR IGNORE INTO allowed_users(user_id) VALUES (?)",
                    (user_id,),
                )

    def is_admin(self, user_id: int) -> bool:
        with self.db.connect() as conn:
            row = conn.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone()
            return row is not None

    def is_allowed(self, user_id: int) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM allowed_users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return row is not None

    def add_admin(self, user_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO admins(user_id) VALUES (?)", (user_id,))
            conn.execute("INSERT OR IGNORE INTO allowed_users(user_id) VALUES (?)", (user_id,))

    def add_allowed_user(self, user_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO allowed_users(user_id) VALUES (?)", (user_id,))

    def list_admins(self) -> list[int]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT user_id FROM admins ORDER BY user_id").fetchall()
            return [int(row["user_id"]) for row in rows]

    def list_allowed_users(self) -> list[int]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT user_id FROM allowed_users ORDER BY user_id"
            ).fetchall()
            return [int(row["user_id"]) for row in rows]
