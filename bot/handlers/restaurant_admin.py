from __future__ import annotations
from datetime import date
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.models import User, MenuItem, Order
from db.connection import async_session_maker
from utils.time_utils import get_next_order_date, parse_working_sats, parse_cutoff
from db.models import Setting

router = Router(name="restaurant_admin")


def _is_admin(user: User | None) -> bool:
    return user is not None and user.role in ("restaurant_admin", "super_admin")


async def _next_order_date() -> date:
    from sqlalchemy import select as sa_select
    async with async_session_maker() as session:
        wsat_res = await session.execute(sa_select(Setting).where(Setting.key == "working_saturdays"))
        wsat_row = wsat_res.scalar_one_or_none()
        cutoff_res = await session.execute(sa_select(Setting).where(Setting.key == "cutoff_time"))
        cutoff_row = cutoff_res.scalar_one_or_none()
    working_sats = parse_working_sats(wsat_row.value if wsat_row else "")
    h, m = parse_cutoff(cutoff_row.value if cutoff_row else "17:00")
    return get_next_order_date(cutoff_hour=h, cutoff_minute=m, working_sats=working_sats)


def _parse_date_arg(args: str, today: date) -> date | None:
    if not args:
        return today
    try:
        parts = args.split(".")
        day, month = int(parts[0]), int(parts[1])
        year = today.year if len(parts) < 3 else int(parts[2])
        if len(parts) < 3 and month < today.month:
            year += 1
        return date(year, month, day)
    except Exception:
        return None


# ── Общая логика (вызывается и командами, и кнопками) ───────────────────────

async def _do_orders(message: Message, target_date: date, show_names: bool = True) -> None:
    async with async_session_maker() as session:
        query = (
            select(Order)
            .where(Order.order_date == target_date, Order.status != "cancelled")
            .options(selectinload(Order.items))
            .order_by(Order.daily_number.asc())
        )
        if show_names:
            query = query.options(selectinload(Order.user))
        res = await session.execute(query)
        orders = res.scalars().all()

    date_str = target_date.strftime("%d.%m.%Y")
    if not orders:
        await message.answer(f"📋 Заказов на {date_str} нет.")
        return

    lines = [f"📋 <b>Заказы на {date_str}</b>  —  {len(orders)} шт.\n"]
    for order in orders:
        num = order.daily_number or order.id
        header = f"<b>№{num}</b>"
        if show_names:
            user_name = order.user.full_name if order.user else f"#{order.user_id}"
            header += f" — {user_name}"
        lines.append(header)
        items_total = 0.0
        for item in order.items:
            s = float(item.price) * item.quantity
            items_total += s
            qty = f"×{item.quantity}  " if item.quantity > 1 else ""
            lines.append(f"  • {item.item_name} {qty}— {s:.0f} ₴")
        lines.append(f"  <i>Итого: {items_total:.0f} ₴</i>\n")

    await message.answer("\n".join(lines), parse_mode="HTML")


async def _do_portions(message: Message, target_date: date) -> None:
    async with async_session_maker() as session:
        res = await session.execute(
            select(Order)
            .where(Order.order_date == target_date, Order.status != "cancelled")
            .options(selectinload(Order.items))
        )
        orders = res.scalars().all()

    date_str = target_date.strftime("%d.%m.%Y")
    if not orders:
        await message.answer(f"📊 Заказов на {date_str} нет.")
        return

    counter: dict[str, int] = {}
    for order in orders:
        for item in order.items:
            counter[item.item_name] = counter.get(item.item_name, 0) + item.quantity

    sorted_items = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    total_portions = sum(counter.values())

    lines = [f"📊 <b>Порции на {date_str}</b>\n"]
    for name, qty in sorted_items:
        lines.append(f"• {name} — <b>{qty} шт.</b>")
    lines.append(f"\nЗаказов: {len(orders)}  |  Порций: {total_portions}")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ── Кнопки Reply-клавиатуры ─────────────────────────────────────────────────

@router.message(F.text == "📋 Заказы")
async def btn_orders(message: Message, db_user: User | None):
    if not _is_admin(db_user):
        return
    await _do_orders(message, await _next_order_date(), show_names=db_user.role == "super_admin")


@router.message(F.text == "📊 Порции")
async def btn_portions(message: Message, db_user: User | None):
    if not _is_admin(db_user):
        return
    await _do_portions(message, await _next_order_date())


# ── Команды (поддерживают указание даты) ────────────────────────────────────

@router.message(Command("orders"))
async def cmd_orders(message: Message, command: CommandObject, db_user: User | None):
    if not _is_admin(db_user):
        return
    today = await _next_order_date()
    target_date = _parse_date_arg((command.args or "").strip(), today)
    if target_date is None:
        await message.answer("Использование: /orders или /orders 07.05")
        return
    await _do_orders(message, target_date, show_names=db_user.role == "super_admin")


@router.message(Command("portions"))
async def cmd_portions(message: Message, command: CommandObject, db_user: User | None):
    if not _is_admin(db_user):
        return
    today = await _next_order_date()
    target_date = _parse_date_arg((command.args or "").strip(), today)
    if target_date is None:
        await message.answer("Использование: /portions или /portions 07.05")
        return
    await _do_portions(message, target_date)


