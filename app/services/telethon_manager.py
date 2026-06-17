from __future__ import annotations

import asyncio
from dataclasses import dataclass

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionCustomEmoji, ReactionEmoji

from app.config import Config
from app.services.reaction_store import AccountRecord, ReactionStore


@dataclass(slots=True)
class PendingLogin:
    account_id: int
    phone: str
    phone_code_hash: str
    session_name: str


class TelethonManager:
    def __init__(self, config: Config, store: ReactionStore) -> None:
        self.config = config
        self.store = store
        self.clients: dict[int, TelegramClient] = {}
        self.rules_cache: dict[int, dict[tuple[int, int], tuple[str, str, str]]] = {}
        self.polling_tasks: dict[int, asyncio.Task] = {}
        self.last_seen_message_ids: dict[tuple[int, int], int] = {}
        self.history_completed: set[tuple[int, int, int]] = set()
        self.pending_logins: dict[int, PendingLogin] = {}
        self._lock = asyncio.Lock()

    def _session_path(self, session_name: str) -> str:
        return str((self.config.session_dir / session_name).resolve())

    async def start_existing_clients(self) -> None:
        for account in self.store.list_accounts():
            if account.is_authorized:
                await self._connect_account(account)

    async def _connect_account(self, account: AccountRecord) -> None:
        async with self._lock:
            if account.id in self.clients:
                return
            client = TelegramClient(
                self._session_path(account.session_name),
                self.config.api_id,
                self.config.api_hash,
            )
            await client.connect()
            if not await client.is_user_authorized():
                self.store.mark_account_authorized(account.id, False)
                await client.disconnect()
                return

            self.rules_cache[account.id] = self.store.get_rules_for_account(account.id)
            await client.start()
            self.clients[account.id] = client
            self.polling_tasks[account.id] = asyncio.create_task(
                self._poll_account_messages(account.id, client)
            )

    async def request_login_code(self, phone: str) -> PendingLogin:
        session_name = f"acct_{phone.replace('+', '').replace(' ', '')}"
        account_id = self.store.create_account(phone, session_name)
        client = TelegramClient(
            self._session_path(session_name),
            self.config.api_id,
            self.config.api_hash,
        )
        await client.connect()
        sent = await client.send_code_request(phone)
        pending = PendingLogin(
            account_id=account_id,
            phone=phone,
            phone_code_hash=sent.phone_code_hash,
            session_name=session_name,
        )
        self.pending_logins[account_id] = pending
        self.clients[account_id] = client
        return pending

    async def sign_in(self, account_id: int, code: str | None = None, password: str | None = None) -> str:
        pending = self.pending_logins.get(account_id)
        if pending is None:
            raise RuntimeError("Authorization session expired. Request a new code.")

        client = self.clients.get(account_id)
        if client is None:
            raise RuntimeError("Telethon client not found for this account.")

        if password:
            await client.sign_in(password=password)
            self.store.mark_account_authorized(account_id, True)
            account = self.store.get_account(account_id)
            if account is None:
                raise RuntimeError("Account record missing after sign in.")
            self.rules_cache[account.id] = self.store.get_rules_for_account(account.id)
            self.pending_logins.pop(account_id, None)
            await client.disconnect()
            self.clients.pop(account_id, None)
            return "ok"

        if not code:
            raise RuntimeError("Login code is required.")

        try:
            await client.sign_in(
                phone=pending.phone,
                code=code,
                phone_code_hash=pending.phone_code_hash,
            )
        except SessionPasswordNeededError:
            if not password:
                return "password_required"
            await client.sign_in(password=password)

        self.store.mark_account_authorized(account_id, True)
        account = self.store.get_account(account_id)
        if account is None:
            raise RuntimeError("Account record missing after sign in.")
        self.rules_cache[account.id] = self.store.get_rules_for_account(account.id)
        self.pending_logins.pop(account_id, None)
        await client.disconnect()
        self.clients.pop(account_id, None)
        return "ok"

    async def refresh_rules(self, account_id: int) -> None:
        self.rules_cache[account_id] = self.store.get_rules_for_account(account_id)
        self.history_completed = {
            item for item in self.history_completed if item[0] != account_id
        }
        self.last_seen_message_ids = {
            key: value for key, value in self.last_seen_message_ids.items() if key[0] != account_id
        }

    async def refresh_all_rules(self) -> None:
        for account in self.store.list_accounts():
            if account.is_authorized:
                self.rules_cache[account.id] = self.store.get_rules_for_account(account.id)
        self.history_completed.clear()
        self.last_seen_message_ids.clear()

    async def ensure_account_connected(self, account_id: int) -> None:
        account = self.store.get_account(account_id)
        if account is None:
            raise RuntimeError("Account not found.")
        if not account.is_authorized:
            raise RuntimeError("Account is not authorized yet.")
        if account_id not in self.clients or not self.clients[account_id].is_connected():
            await self._connect_account(account)

    async def set_reactions_enabled(self, enabled: bool) -> None:
        self.store.set_reactions_enabled(enabled)

    def are_reactions_enabled(self) -> bool:
        return self.store.are_reactions_enabled()

    async def _poll_account_messages(self, account_id: int, client: TelegramClient) -> None:
        while True:
            try:
                if not self.store.are_reactions_enabled():
                    await asyncio.sleep(5)
                    continue

                rules = self.rules_cache.get(account_id, {})
                if not rules:
                    await asyncio.sleep(5)
                    continue

                for chat_id in self.store.get_rule_chat_ids(account_id):
                    chat_key = (account_id, chat_id)
                    messages = await client.get_messages(chat_id, limit=10)
                    if not messages:
                        continue

                    if chat_key not in self.last_seen_message_ids:
                        self.last_seen_message_ids[chat_key] = max(msg.id for msg in messages)
                        continue

                    last_seen_id = self.last_seen_message_ids[chat_key]
                    new_messages = [msg for msg in messages if msg.id > last_seen_id]
                    if not new_messages:
                        continue

                    for message in sorted(new_messages, key=lambda item: item.id):
                        sender_id = getattr(message, "sender_id", None)
                        if sender_id is None:
                            continue
                        reaction_rule = rules.get((chat_id, int(sender_id)))
                        if not reaction_rule:
                            continue
                        reaction_type, mode, reaction_value = reaction_rule
                        if mode not in {"new_only", "all_messages"}:
                            continue
                        try:
                            await self._send_reaction(
                                client=client,
                                chat_id=chat_id,
                                message_id=message.id,
                                reaction_type=reaction_type,
                                reaction_value=reaction_value,
                            )
                        except Exception:
                            continue

                    self.last_seen_message_ids[chat_key] = max(msg.id for msg in messages)

                for (chat_id, target_user_id), reaction_rule in rules.items():
                    reaction_type, mode, reaction_value = reaction_rule
                    if mode != "all_messages":
                        continue
                    history_key = (account_id, chat_id, target_user_id)
                    if history_key in self.history_completed:
                        continue
                    try:
                        async for message in client.iter_messages(chat_id, from_user=target_user_id):
                            current_rule = self.rules_cache.get(account_id, {}).get(
                                (chat_id, target_user_id)
                            )
                            if current_rule is None:
                                break
                            current_reaction_type, current_mode, current_reaction_value = current_rule
                            if current_mode != "all_messages":
                                break
                            await self._send_reaction(
                                client=client,
                                chat_id=chat_id,
                                message_id=message.id,
                                reaction_type=current_reaction_type,
                                reaction_value=current_reaction_value,
                            )
                            await asyncio.sleep(0.35)
                        current_rule = self.rules_cache.get(account_id, {}).get((chat_id, target_user_id))
                        if current_rule is not None and current_rule[1] == "all_messages":
                            self.history_completed.add(history_key)
                    except Exception:
                        continue
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(5)

    async def _send_reaction(
        self,
        client: TelegramClient,
        chat_id: int,
        message_id: int,
        reaction_type: str,
        reaction_value: str,
    ) -> None:
        input_entity = await client.get_input_entity(chat_id)
        if reaction_type == "custom_emoji":
            reaction_payload = [ReactionCustomEmoji(document_id=int(reaction_value))]
        else:
            reaction_payload = [ReactionEmoji(emoticon=reaction_value)]
        await client(
            SendReactionRequest(
                peer=input_entity,
                msg_id=message_id,
                reaction=reaction_payload,
                big=False,
                add_to_recent=True,
            )
        )
