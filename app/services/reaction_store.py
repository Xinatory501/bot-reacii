from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.database import Database


@dataclass(slots=True)
class AccountRecord:
    id: int
    phone: str
    session_name: str
    is_authorized: bool
    label: str | None


@dataclass(slots=True)
class ReactionRule:
    id: int
    chat_id: int
    target_user_id: int
    reaction_type: str
    mode: str
    reaction: str
    enabled: bool
    account_id: int
    phone: str


class ReactionStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_account(self, phone: str, session_name: str, label: str | None = None) -> int:
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO telethon_accounts(phone, session_name, label)
                VALUES (?, ?, ?)
                ON CONFLICT(phone) DO UPDATE SET
                    session_name = excluded.session_name,
                    label = COALESCE(excluded.label, telethon_accounts.label)
                """,
                (phone, session_name, label),
            )
            account_id = cursor.lastrowid
            if not account_id:
                row = conn.execute(
                    "SELECT id FROM telethon_accounts WHERE phone = ?",
                    (phone,),
                ).fetchone()
                account_id = int(row["id"])
            return int(account_id)

    def mark_account_authorized(self, account_id: int, value: bool) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE telethon_accounts SET is_authorized = ? WHERE id = ?",
                (1 if value else 0, account_id),
            )

    def list_accounts(self) -> list[AccountRecord]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM telethon_accounts ORDER BY id DESC"
            ).fetchall()
            return [
                AccountRecord(
                    id=int(row["id"]),
                    phone=str(row["phone"]),
                    session_name=str(row["session_name"]),
                    is_authorized=bool(row["is_authorized"]),
                    label=row["label"],
                )
                for row in rows
            ]

    def get_account(self, account_id: int) -> AccountRecord | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM telethon_accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
            if row is None:
                return None
            return AccountRecord(
                id=int(row["id"]),
                phone=str(row["phone"]),
                session_name=str(row["session_name"]),
                is_authorized=bool(row["is_authorized"]),
                label=row["label"],
            )

    def are_reactions_enabled(self) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'reactions_enabled'"
            ).fetchone()
            return row is None or str(row["value"]) == "1"

    def set_reactions_enabled(self, enabled: bool) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings(key, value)
                VALUES ('reactions_enabled', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                ("1" if enabled else "0",),
            )

    def upsert_rule(
        self,
        account_id: int,
        chat_id: int,
        target_user_id: int,
        reaction_type: str,
        mode: str,
        reaction: str,
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO reaction_rules(chat_id, target_user_id, reaction_type, mode, reaction, enabled, account_id)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(chat_id, target_user_id, account_id) DO UPDATE SET
                    reaction_type = excluded.reaction_type,
                    mode = excluded.mode,
                    reaction = excluded.reaction,
                    enabled = 1
                """,
                (chat_id, target_user_id, reaction_type, mode, reaction, account_id),
            )

    def list_rules(self) -> list[ReactionRule]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT rr.id, rr.chat_id, rr.target_user_id, rr.reaction_type, rr.mode, rr.reaction, rr.enabled, rr.account_id, ta.phone
                FROM reaction_rules rr
                JOIN telethon_accounts ta ON ta.id = rr.account_id
                ORDER BY rr.id DESC
                """
            ).fetchall()
            return [
                ReactionRule(
                    id=int(row["id"]),
                    chat_id=int(row["chat_id"]),
                    target_user_id=int(row["target_user_id"]),
                    reaction_type=str(row["reaction_type"]),
                    mode=str(row["mode"]),
                    reaction=str(row["reaction"]),
                    enabled=bool(row["enabled"]),
                    account_id=int(row["account_id"]),
                    phone=str(row["phone"]),
                )
                for row in rows
            ]

    def get_rules_for_account(self, account_id: int) -> dict[tuple[int, int], tuple[str, str, str]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT chat_id, target_user_id, reaction_type, mode, reaction
                FROM reaction_rules
                WHERE account_id = ? AND enabled = 1
                """,
                (account_id,),
            ).fetchall()
            return {
                (int(row["chat_id"]), int(row["target_user_id"])): (
                    str(row["reaction_type"]),
                    str(row["mode"]),
                    str(row["reaction"]),
                )
                for row in rows
            }

    def get_rule_chat_ids(self, account_id: int) -> list[int]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT chat_id
                FROM reaction_rules
                WHERE account_id = ? AND enabled = 1
                ORDER BY chat_id
                """,
                (account_id,),
            ).fetchall()
            return [int(row["chat_id"]) for row in rows]

    def set_all_rules_mode(self, mode: str) -> int:
        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE reaction_rules SET mode = ? WHERE enabled = 1",
                (mode,),
            )
            return int(cursor.rowcount or 0)
