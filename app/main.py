from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import load_config
from app.database import Database
from app.handlers import admin, common
from app.services.access import AccessService
from app.services.reaction_store import ReactionStore
from app.services.telethon_manager import TelethonManager


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    config = load_config()
    db = Database(config.database_path)
    access = AccessService(db, config)
    store = ReactionStore(db)
    telethon_manager = TelethonManager(config, store)
    await telethon_manager.start_existing_clients()

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp["access"] = access
    dp["store"] = store
    dp["manager"] = telethon_manager

    dp.include_router(common.router)
    dp.include_router(admin.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
