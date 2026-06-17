from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text="/start"), KeyboardButton(text="/status")]]
    if is_admin:
        rows.extend(
            [
                [KeyboardButton(text="Админы"), KeyboardButton(text="Разрешенные пользователи")],
                [KeyboardButton(text="Добавить админа"), KeyboardButton(text="Добавить пользователя")],
                [KeyboardButton(text="Добавить аккаунт"), KeyboardButton(text="Аккаунты")],
                [KeyboardButton(text="Добавить правило реакции"), KeyboardButton(text="Правила реакций")],
                [KeyboardButton(text="Включить реакции"), KeyboardButton(text="Выключить реакции")],
                [KeyboardButton(text="Все аккаунты: все сообщения"), KeyboardButton(text="Все аккаунты: только новые")],
            ]
        )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def code_input_keyboard(current_code: str = "") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for digit in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
        builder.button(text=digit, callback_data=f"code_digit:{digit}")
    builder.button(text="Очистить", callback_data="code_clear")
    builder.button(text="0", callback_data="code_digit:0")
    builder.button(text="Подтвердить", callback_data="code_submit")
    builder.adjust(3, 3, 3, 3)
    return builder.as_markup()


def accounts_keyboard(accounts: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for account_id, phone in accounts:
        builder.button(text=f"#{account_id} {phone}", callback_data=f"rule_account:{account_id}")
    builder.adjust(1)
    return builder.as_markup()


def reaction_picker_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for emoji in ("👍", "❤️", "🔥", "😂", "👏", "🎉", "😎", "🤝", "💯"):
        builder.button(text=emoji, callback_data=f"rule_reaction_emoji:{emoji}")
    builder.adjust(3, 3, 3)
    return builder.as_markup()


def rule_mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Только новые", callback_data="rule_mode:new_only")
    builder.button(text="Все сообщения", callback_data="rule_mode:all_messages")
    builder.adjust(1)
    return builder.as_markup()
