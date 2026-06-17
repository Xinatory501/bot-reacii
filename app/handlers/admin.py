from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.services.access import AccessService
from app.services.reaction_store import ReactionStore
from app.services.telethon_manager import TelethonManager
from app.utils.keyboards import (
    accounts_keyboard,
    code_input_keyboard,
    main_menu,
    reaction_picker_keyboard,
    rule_mode_keyboard,
)

router = Router()


class AdminOnly(BaseFilter):
    async def __call__(self, message: Message, access: AccessService) -> bool:
        return access.is_admin(message.from_user.id)


class AdminStates(StatesGroup):
    waiting_admin_id = State()
    waiting_allowed_id = State()
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()
    waiting_rule_account = State()
    waiting_rule_chat_id = State()
    waiting_rule_target_user_id = State()
    waiting_rule_mode = State()
    waiting_rule_reaction = State()


def _parse_int(text: str) -> int | None:
    try:
        return int(text.strip())
    except (TypeError, ValueError):
        return None


def _safe_error_text(exc: Exception) -> str:
    return escape(str(exc) or exc.__class__.__name__)


@router.message(AdminOnly(), F.text == "Админы")
async def list_admins(message: Message, access: AccessService) -> None:
    text = "Админы:\n" + "\n".join(str(item) for item in access.list_admins())
    await message.answer(text, reply_markup=main_menu(True))


@router.message(AdminOnly(), F.text == "Разрешенные пользователи")
async def list_allowed(message: Message, access: AccessService) -> None:
    text = "Разрешенные пользователи:\n" + "\n".join(
        str(item) for item in access.list_allowed_users()
    )
    await message.answer(text, reply_markup=main_menu(True))


@router.message(AdminOnly(), F.text == "Добавить админа")
async def add_admin_prompt(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_admin_id)
    await message.answer("Отправь Telegram ID пользователя, которого нужно добавить в админы.")


@router.message(AdminOnly(), AdminStates.waiting_admin_id)
async def add_admin_finish(
    message: Message,
    state: FSMContext,
    access: AccessService,
) -> None:
    user_id = _parse_int(message.text)
    if user_id is None:
        await message.answer("Отправь только числовой Telegram ID.")
        return
    access.add_admin(user_id)
    await state.clear()
    await message.answer(f"Админ {user_id} добавлен.", reply_markup=main_menu(True))


@router.message(AdminOnly(), F.text == "Добавить пользователя")
async def add_allowed_prompt(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_allowed_id)
    await message.answer("Отправь Telegram ID пользователя, которому нужно выдать доступ.")


@router.message(AdminOnly(), AdminStates.waiting_allowed_id)
async def add_allowed_finish(
    message: Message,
    state: FSMContext,
    access: AccessService,
) -> None:
    user_id = _parse_int(message.text)
    if user_id is None:
        await message.answer("Отправь только числовой Telegram ID.")
        return
    access.add_allowed_user(user_id)
    await state.clear()
    await message.answer(f"Пользователь {user_id} добавлен в список доступа.", reply_markup=main_menu(True))


@router.message(AdminOnly(), F.text == "Добавить аккаунт")
async def add_account_prompt(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_phone)
    await message.answer("Отправь номер телефона в международном формате, например +375291112233.")


@router.message(AdminOnly(), AdminStates.waiting_phone)
async def add_account_phone(
    message: Message,
    state: FSMContext,
    manager: TelethonManager,
) -> None:
    phone = (message.text or "").strip()
    if not phone:
        await message.answer("Отправь номер телефона текстом, например +375291112233.")
        return
    try:
        pending = await manager.request_login_code(phone)
    except Exception as exc:
        await message.answer(f"Не удалось отправить код входа: {_safe_error_text(exc)}")
        return
    await state.update_data(account_id=pending.account_id)
    await state.set_state(AdminStates.waiting_code)
    await message.answer(
        "Код отправлен в Telegram. Введи его кнопками ниже.",
        reply_markup=code_input_keyboard(),
    )


@router.callback_query(AdminOnly(), AdminStates.waiting_code, F.data.startswith("code_digit:"))
async def add_account_code_digit(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    current_code = str(data.get("current_code", ""))
    if len(current_code) >= 6:
        await callback.answer("Обычно код не длиннее 6 символов.")
        return
    digit = callback.data.split(":", maxsplit=1)[1]
    current_code += digit
    await state.update_data(current_code=current_code)
    await callback.message.edit_text(
        f"Код: {current_code or 'пусто'}",
        reply_markup=code_input_keyboard(current_code),
    )
    await callback.answer()


@router.callback_query(AdminOnly(), AdminStates.waiting_code, F.data == "code_clear")
async def add_account_code_clear(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.update_data(current_code="")
    await callback.message.edit_text(
        "Код очищен. Введи его кнопками ниже.",
        reply_markup=code_input_keyboard(),
    )
    await callback.answer("Код очищен.")


@router.callback_query(AdminOnly(), AdminStates.waiting_code, F.data == "code_submit")
async def add_account_code_submit(
    callback: CallbackQuery,
    state: FSMContext,
    manager: TelethonManager,
) -> None:
    data = await state.get_data()
    account_id = int(data["account_id"])
    code = str(data.get("current_code", ""))
    if not code:
        await callback.answer("Сначала введи код.", show_alert=True)
        return
    try:
        result = await manager.sign_in(account_id=account_id, code=code)
    except Exception as exc:
        await callback.message.answer(f"Ошибка авторизации: {_safe_error_text(exc)}")
        await callback.answer()
        return
    if result == "password_required":
        await state.set_state(AdminStates.waiting_password)
        await callback.message.answer("Включена двухэтапная защита. Отправь облачный пароль.")
        await callback.answer()
        return
    await manager.ensure_account_connected(account_id)
    await state.clear()
    await callback.message.answer("Аккаунт авторизован и подключен.", reply_markup=main_menu(True))
    await callback.answer("Готово.")


@router.message(AdminOnly(), AdminStates.waiting_code)
async def add_account_code_text(message: Message) -> None:
    await message.answer("Используй inline-кнопки под сообщением для ввода кода.")


@router.message(AdminOnly(), AdminStates.waiting_password)
async def add_account_password(
    message: Message,
    state: FSMContext,
    manager: TelethonManager,
) -> None:
    data = await state.get_data()
    account_id = int(data["account_id"])
    try:
        result = await manager.sign_in(account_id=account_id, password=message.text.strip())
    except Exception as exc:
        await message.answer(f"Ошибка авторизации по паролю: {_safe_error_text(exc)}")
        return
    if result != "ok":
        await message.answer("Пароль не подошел.")
        return
    await manager.ensure_account_connected(account_id)
    await state.clear()
    await message.answer("Аккаунт авторизован по паролю и подключен.", reply_markup=main_menu(True))


@router.message(AdminOnly(), F.text == "Добавить правило реакции")
async def add_rule_prompt(message: Message, state: FSMContext, store: ReactionStore) -> None:
    accounts = store.list_accounts()
    if not accounts:
        await message.answer("Сначала добавь и авторизуй аккаунт.")
        return
    await state.clear()
    await state.set_state(AdminStates.waiting_rule_account)
    await message.answer(
        "Шаг 1 из 4. Выбери аккаунт, с которого ставить реакцию.",
        reply_markup=accounts_keyboard([(item.id, item.phone) for item in accounts]),
    )


@router.callback_query(AdminOnly(), AdminStates.waiting_rule_account, F.data.startswith("rule_account:"))
async def add_rule_account(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    account_id = int(callback.data.split(":", maxsplit=1)[1])
    await state.update_data(rule_account_id=account_id)
    await state.set_state(AdminStates.waiting_rule_chat_id)
    await callback.message.answer(
        "Шаг 2 из 4. Отправь ID группы или чата, где нужно ставить реакцию.\nПример: -1001234567890"
    )
    await callback.answer()


@router.message(AdminOnly(), AdminStates.waiting_rule_chat_id)
async def add_rule_chat_id(message: Message, state: FSMContext) -> None:
    chat_id = _parse_int(message.text)
    if chat_id is None:
        await message.answer("Отправь числовой ID группы или чата.")
        return
    await message.answer(
        "Шаг 3 из 4. Отправь Telegram ID пользователя, которому нужно ставить реакцию."
    )
    await state.update_data(rule_chat_id=chat_id)
    await state.set_state(AdminStates.waiting_rule_target_user_id)


@router.message(AdminOnly(), AdminStates.waiting_rule_target_user_id)
async def add_rule_target_user(message: Message, state: FSMContext) -> None:
    target_user_id = _parse_int(message.text)
    if target_user_id is None:
        await message.answer("Отправь числовой Telegram ID пользователя.")
        return
    await state.update_data(rule_target_user_id=target_user_id)
    await state.set_state(AdminStates.waiting_rule_mode)
    await message.answer(
        "Шаг 4 из 5. Выбери режим правила.\n"
        "Только новые - реакция только на новые сообщения.\n"
        "Все сообщения - бот пройдет по всей доступной истории этого пользователя в группе.",
        reply_markup=rule_mode_keyboard(),
    )


@router.callback_query(
    AdminOnly(),
    AdminStates.waiting_rule_mode,
    F.data.startswith("rule_mode:"),
)
async def add_rule_mode(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    mode = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(rule_mode=mode)
    await state.set_state(AdminStates.waiting_rule_reaction)
    await callback.message.answer(
        "Шаг 5 из 5. Выбери реакцию кнопкой ниже или отправь стикер/кастом-эмодзи.\n"
        "Если пришлешь обычный стикер без custom emoji, я покажу его ID, но для реакции он не подойдет.",
        reply_markup=reaction_picker_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    AdminOnly(),
    AdminStates.waiting_rule_reaction,
    F.data.startswith("rule_reaction_emoji:"),
)
async def add_rule_finish_emoji(
    callback: CallbackQuery,
    state: FSMContext,
    store: ReactionStore,
    manager: TelethonManager,
) -> None:
    reaction = callback.data.split(":", maxsplit=1)[1]
    await _save_rule(
        message=callback.message,
        state=state,
        store=store,
        manager=manager,
        reaction_type="emoji",
        reaction_value=reaction,
    )
    await callback.answer("Реакция выбрана.")


@router.message(AdminOnly(), AdminStates.waiting_rule_reaction)
async def add_rule_finish(
    message: Message,
    state: FSMContext,
    store: ReactionStore,
    manager: TelethonManager,
) -> None:
    if message.sticker:
        custom_emoji_id = message.sticker.custom_emoji_id
        if custom_emoji_id:
            await _save_rule(
                message=message,
                state=state,
                store=store,
                manager=manager,
                reaction_type="custom_emoji",
                reaction_value=custom_emoji_id,
            )
            return
        await message.answer(
            "Это обычный стикер.\n"
            f"Sticker file_id: {message.sticker.file_id}\n"
            f"Sticker file_unique_id: {message.sticker.file_unique_id}\n"
            "Для реакции нужен кастом-эмодзи стикер из Telegram."
        )
        return

    reaction = (message.text or "").strip()
    if not reaction:
        await message.answer("Выбери реакцию кнопкой или отправь эмодзи/кастом-стикер.")
        return
    await _save_rule(
        message=message,
        state=state,
        store=store,
        manager=manager,
        reaction_type="emoji",
        reaction_value=reaction,
    )


async def _save_rule(
    message: Message,
    state: FSMContext,
    store: ReactionStore,
    manager: TelethonManager,
    reaction_type: str,
    reaction_value: str,
) -> None:
    data = await state.get_data()
    account_id = int(data["rule_account_id"])
    chat_id = int(data["rule_chat_id"])
    target_user_id = int(data["rule_target_user_id"])
    mode = str(data.get("rule_mode", "new_only"))
    store.upsert_rule(
        account_id=account_id,
        chat_id=chat_id,
        target_user_id=target_user_id,
        reaction_type=reaction_type,
        mode=mode,
        reaction=reaction_value,
    )
    try:
        await manager.refresh_rules(account_id)
        await manager.ensure_account_connected(account_id)
    except Exception as exc:
        await message.answer(
            f"Правило сохранено, но аккаунт не удалось подключить: {_safe_error_text(exc)}"
        )
        await state.clear()
        return
    await state.clear()
    reaction_view = reaction_value if reaction_type == "emoji" else f"custom_emoji:{reaction_value}"
    mode_view = "все сообщения" if mode == "all_messages" else "только новые"
    await message.answer(
        f"Правило сохранено: аккаунт #{account_id} ставит {reaction_view} пользователю {target_user_id} в группе {chat_id}, режим: {mode_view}.",
        reply_markup=main_menu(True),
    )


@router.message(AdminOnly(), F.text == "Правила реакций")
async def list_rules(message: Message, store: ReactionStore) -> None:
    rules = store.list_rules()
    if not rules:
        await message.answer("Правила реакций пока не настроены.", reply_markup=main_menu(True))
        return
    text = "\n".join(
        f"#{rule.id} аккаунт={rule.account_id} ({rule.phone}) группа={rule.chat_id} пользователь={rule.target_user_id} режим={rule.mode} тип={rule.reaction_type} реакция={rule.reaction}"
        for rule in rules
    )
    await message.answer(text, reply_markup=main_menu(True))


@router.message(AdminOnly(), F.text == "Включить реакции")
async def enable_reactions(message: Message, manager: TelethonManager) -> None:
    await manager.set_reactions_enabled(True)
    await message.answer("Авто-реакции включены. Бот будет проверять новые сообщения каждые 5 секунд.")


@router.message(AdminOnly(), F.text == "Выключить реакции")
async def disable_reactions(message: Message, manager: TelethonManager) -> None:
    await manager.set_reactions_enabled(False)
    await message.answer("Авто-реакции выключены. Проверка сообщений приостановлена.")


@router.message(AdminOnly(), F.text == "Все аккаунты: все сообщения")
async def enable_all_messages_mode(
    message: Message,
    store: ReactionStore,
    manager: TelethonManager,
) -> None:
    changed = store.set_all_rules_mode("all_messages")
    await manager.refresh_all_rules()
    await message.answer(
        f"Готово. Режим 'все сообщения' включен для всех правил. Обновлено правил: {changed}."
    )


@router.message(AdminOnly(), F.text == "Все аккаунты: только новые")
async def enable_new_only_mode(
    message: Message,
    store: ReactionStore,
    manager: TelethonManager,
) -> None:
    changed = store.set_all_rules_mode("new_only")
    await manager.refresh_all_rules()
    await message.answer(
        f"Готово. Режим 'только новые' включен для всех правил. Обновлено правил: {changed}."
    )
