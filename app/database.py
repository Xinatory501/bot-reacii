from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self.connect() as conn:
            existing_tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if "reaction_rules" in existing_tables:
                columns = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(reaction_rules)").fetchall()
                }
                if (
                    "chat_id" not in columns
                    or "reaction_type" not in columns
                    or "mode" not in columns
                ):
                    conn.executescript(
                        """
                        ALTER TABLE reaction_rules RENAME TO reaction_rules_old;

                        CREATE TABLE reaction_rules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            chat_id INTEGER NOT NULL DEFAULT 0,
                            target_user_id INTEGER NOT NULL,
                            reaction_type TEXT NOT NULL DEFAULT 'emoji',
                            mode TEXT NOT NULL DEFAULT 'new_only',
                            reaction TEXT NOT NULL,
                            enabled INTEGER NOT NULL DEFAULT 1,
                            account_id INTEGER NOT NULL,
                            UNIQUE(chat_id, target_user_id, account_id),
                            FOREIGN KEY(account_id) REFERENCES telethon_accounts(id) ON DELETE CASCADE
                        );

                        INSERT INTO reaction_rules(id, chat_id, target_user_id, reaction_type, mode, reaction, enabled, account_id)
                        SELECT
                            id,
                            CASE
                                WHEN EXISTS (
                                    SELECT 1
                                    FROM pragma_table_info('reaction_rules_old')
                                    WHERE name = 'chat_id'
                                ) THEN chat_id
                                ELSE 0
                            END,
                            target_user_id,
                            CASE
                                WHEN EXISTS (
                                    SELECT 1
                                    FROM pragma_table_info('reaction_rules_old')
                                    WHERE name = 'reaction_type'
                                ) THEN reaction_type
                                ELSE 'emoji'
                            END,
                            'new_only',
                            reaction,
                            enabled,
                            account_id
                        FROM reaction_rules_old;

                        DROP TABLE reaction_rules_old;
                        """
                    )

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS allowed_users (
                    user_id INTEGER PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telethon_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT NOT NULL UNIQUE,
                    session_name TEXT NOT NULL UNIQUE,
                    is_authorized INTEGER NOT NULL DEFAULT 0,
                    label TEXT
                );

                CREATE TABLE IF NOT EXISTS reaction_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL DEFAULT 0,
                    target_user_id INTEGER NOT NULL,
                    reaction_type TEXT NOT NULL DEFAULT 'emoji',
                    mode TEXT NOT NULL DEFAULT 'new_only',
                    reaction TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    account_id INTEGER NOT NULL,
                    UNIQUE(chat_id, target_user_id, account_id),
                    FOREIGN KEY(account_id) REFERENCES telethon_accounts(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO app_settings(key, value) VALUES ('reactions_enabled', '1')"
            )
