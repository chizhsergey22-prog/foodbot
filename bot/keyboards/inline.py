from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def miniapp_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽 Открыть заказ обеда", web_app=WebAppInfo(url=url))]
    ])


def cancel_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"cancel_approve:{request_id}"),
        InlineKeyboardButton(text="❌ Отклонить",   callback_data=f"cancel_reject:{request_id}"),
    ]])


def restaurant_admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Заказы"), KeyboardButton(text="📊 Порции")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def confirm_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да",  callback_data=f"{action}_yes:{item_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"{action}_no:{item_id}"),
    ]])
