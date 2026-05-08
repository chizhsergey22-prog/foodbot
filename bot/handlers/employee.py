from __future__ import annotations
import secrets
from decimal import Decimal
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from db.models import User, InviteCode, Order, CancelRequest
from db.connection import async_session_maker
from keyboards.inline import miniapp_keyboard, restaurant_admin_keyboard
from config import settings

router = Router(name="employee")


class RegStates(StatesGroup):
    waiting_code = State()


# ── /start ──────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User | None, state: FSMContext):
    await state.clear()  # сбрасываем любое активное FSM-состояние

    if db_user and db_user.is_active:
        await _send_welcome(message, db_user)
        return

    # Суперадмин без записи в БД (не должно случиться после middleware, но на всякий)
    if message.from_user.id in settings.super_admin_list:
        await message.answer("Вы зарегистрированы как суперадминистратор.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        await _process_invite(message, args[1].strip(), state)
    else:
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Для доступа к системе введите инвайт-код, "
            "который вам выдал администратор:"
        )
        await state.set_state(RegStates.waiting_code)


@router.message(RegStates.waiting_code)
async def process_code_input(message: Message, state: FSMContext):
    await _process_invite(message, message.text.strip(), state)


async def _process_invite(message: Message, code: str, state: FSMContext):
    from datetime import datetime, timezone
    async with async_session_maker() as session:
        res = await session.execute(
            select(InviteCode).where(InviteCode.code == code, InviteCode.is_used == False)
        )
        invite = res.scalar_one_or_none()

        if not invite:
            await message.answer("❌ Неверный или уже использованный код. Попробуйте ещё раз:")
            return

        if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
            await message.answer("❌ Срок действия кода истёк. Запросите новый у администратора.")
            return

        # Регистрируем пользователя (имя и роль берём из инвайта)
        full_name = invite.label or message.from_user.full_name or "Сотрудник"
        user = User(
            telegram_id=message.from_user.id,
            full_name=full_name,
            username=message.from_user.username,
            role=invite.role or "employee",
            balance_debt=invite.initial_debt or Decimal(0),
        )
        session.add(user)
        invite.is_used = True
        invite.used_by = message.from_user.id
        await session.commit()
        await session.refresh(user)

    await state.clear()
    await _send_welcome(message, user)


async def _send_welcome(message: Message, user: User):
    role_emoji = {"super_admin": "👑", "restaurant_admin": "🍴", "employee": "👤"}.get(user.role, "👤")

    if user.role == "restaurant_admin":
        await message.answer(
            f"🍴 Привет, {user.full_name}!\n\n"
            "Панель администратора ресторана:",
            reply_markup=restaurant_admin_keyboard(),
        )
        return

    await message.answer(
        f"{role_emoji} Привет, {user.full_name}!\n\n"
        "Нажмите кнопку ниже, чтобы открыть меню и оформить заказ на завтра:",
        reply_markup=miniapp_keyboard(settings.MINI_APP_URL),
    )


# ── Команда /mydebt — личный долг ───────────────────────────────────────────

@router.message(Command("mydebt"))
async def cmd_mydebt(message: Message, db_user: User | None):
    if not db_user:
        await message.answer("Сначала пройдите регистрацию: /start")
        return
    await message.answer(
        f"💰 Ваш текущий накопленный долг: *{db_user.balance_debt} ₴*",
        parse_mode="Markdown",
    )
