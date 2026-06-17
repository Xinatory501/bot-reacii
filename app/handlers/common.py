from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.services.access import AccessService
from app.services.reaction_store import ReactionStore
from app.utils.keyboards import main_menu

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, access: AccessService) -> None:
    user_id = message.from_user.id
    if not access.is_allowed(user_id):
        await message.answer("Доступ запрещен. Попроси администратора добавить твой Telegram ID.")
        return
    await message.answer(
        "Бот запущен.\nИспользуй меню для управления админами, аккаунтами Telethon и авто-реакциями.",
        reply_markup=main_menu(access.is_admin(user_id)),
    )


@router.message(F.text == "/status")
@router.message(F.text == "Аккаунты")
async def status_handler(
    message: Message,
    access: AccessService,
    store: ReactionStore,
) -> None:
    user_id = message.from_user.id
    if not access.is_allowed(user_id):
        await message.answer("Доступ запрещен.")
        return

    accounts = store.list_accounts()
    reactions_status = "включены" if store.are_reactions_enabled() else "выключены"
    if not accounts:
        text = f"Реакции сейчас: {reactions_status}\n\nПока не добавлено ни одного аккаунта."
    else:
        accounts_text = "\n".join(
            f"#{item.id} {item.phone} | авторизован={'да' if item.is_authorized else 'нет'}"
            for item in accounts
        )
        text = f"Реакции сейчас: {reactions_status}\n\n{accounts_text}"
    await message.answer(text, reply_markup=main_menu(access.is_admin(user_id)))
