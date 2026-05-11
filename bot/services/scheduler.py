from __future__ import annotations
import logging
from decimal import Decimal
from datetime import date, datetime, timedelta
import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from db.models import Order, OrderItem, User, Setting
from db.connection import async_session_maker
from config import settings
from utils.time_utils import parse_cutoff, get_next_order_date, parse_working_sats

log = logging.getLogger(__name__)
kyiv_tz = pytz.timezone("Europe/Kyiv")


async def _get_working_sats() -> set:
    from datetime import date
    async with async_session_maker() as session:
        res = await session.execute(select(Setting).where(Setting.key == "working_saturdays"))
        row = res.scalar_one_or_none()
    return parse_working_sats(row.value if row else "")
scheduler = AsyncIOScheduler(timezone=kyiv_tz)
_bot: Bot | None = None


def setup_scheduler(bot: Bot, cutoff_h: int = 17, cutoff_m: int = 0) -> None:
    global _bot
    _bot = bot
    _add_jobs(cutoff_h, cutoff_m)
    scheduler.start()
    log.info("Планировщик запущен (дедлайн %02d:%02d Kyiv)", cutoff_h, cutoff_m)


async def reschedule_jobs(bot: Bot, cutoff_h: int, cutoff_m: int) -> None:
    global _bot
    _bot = bot
    for job_id in ("lock_orders", "send_summary", "send_reminder", "send_reminder_early", "open_notification"):
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    _add_jobs(cutoff_h, cutoff_m)
    log.info("Планировщик перенастроен на %02d:%02d", cutoff_h, cutoff_m)


_cutoff_str: str = "17:00"


def _add_jobs(h: int, m: int) -> None:
    global _cutoff_str
    _cutoff_str = f"{h:02d}:{m:02d}"

    scheduler.add_job(
        _lock_orders,
        CronTrigger(hour=h, minute=m, timezone=kyiv_tz),
        id="lock_orders",
        replace_existing=True,
    )

    # Отправка сводки через 1 минуту после дедлайна
    summary_m = (m + 1) % 60
    summary_h = h + 1 if m == 59 else h
    scheduler.add_job(
        _send_daily_summary,
        CronTrigger(hour=summary_h, minute=summary_m, timezone=kyiv_tz),
        id="send_summary",
        replace_existing=True,
    )

    # Напоминание за 15 минут до дедлайна (только пн–пт)
    reminder_m = m - 15
    reminder_h = h if reminder_m >= 0 else h - 1
    reminder_m = reminder_m % 60
    if reminder_h >= 0:
        scheduler.add_job(
            _send_cutoff_reminder,
            CronTrigger(hour=reminder_h, minute=reminder_m, day_of_week="mon-fri,sun", timezone=kyiv_tz),
            id="send_reminder",
            replace_existing=True,
        )

    # Раннее напоминание в 14:10 (пн–пт + вс)
    scheduler.add_job(
        _send_cutoff_reminder,
        CronTrigger(hour=14, minute=10, day_of_week="mon-fri,sun", timezone=kyiv_tz),
        id="send_reminder_early",
        replace_existing=True,
    )

    # Уведомление об открытии приёма заказов в 12:00 (пн–сб)
    scheduler.add_job(
        _send_open_notification,
        CronTrigger(hour=12, minute=0, day_of_week="mon-sat", timezone=kyiv_tz),
        id="open_notification",
        replace_existing=True,
    )


_DAY_ACC = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]


async def _send_open_notification() -> None:
    """В 12:00 уведомляет всех сотрудников об открытии приёма заказов."""
    if _bot is None:
        return

    working_sats = await _get_working_sats()
    today_kyiv = datetime.now(kyiv_tz).date()
    weekday = today_kyiv.weekday()  # 0=Пн … 5=Сб

    cutoff_day_suffix = ""  # уточнение дня дедлайна, если не сегодня

    if weekday in (0, 1, 2, 3):  # Пн–Чт: окно открывается сейчас для завтра
        order_date = today_kyiv + timedelta(days=1)
        open_now = True
    elif weekday == 4:  # Пятница
        tomorrow = today_kyiv + timedelta(days=1)
        if tomorrow in working_sats:  # рабочая суббота — окно открывается сейчас
            order_date = tomorrow
            open_now = True
        else:  # обычная суббота — окно откроется в {_cutoff_str} для понедельника
            order_date = today_kyiv + timedelta(days=3)
            open_now = False
    elif weekday == 5:  # Суббота
        if today_kyiv in working_sats:  # рабочая суббота — окно на понедельник уже открыто
            order_date = today_kyiv + timedelta(days=2)
            open_now = True
            cutoff_day_suffix = " воскресенья"  # дедлайн — воскресенье
        else:
            return  # обычная суббота — не отправляем
    else:
        return

    day_acc = _DAY_ACC[order_date.weekday()]
    date_str = order_date.strftime("%d.%m")

    if open_now:
        text = (
            f"🟢 Приём заказов на <b>{day_acc} {date_str}</b> открыт!\n\n"
            f"Оформи заказ до <b>{_cutoff_str}</b>{cutoff_day_suffix} 🍽"
        )
    else:
        text = (
            f"🔔 Сегодня в <b>{_cutoff_str}</b> откроется приём заказов "
            f"на <b>{day_acc} {date_str}</b>.\n\n"
            f"Не пропусти! 🍽"
        )

    async with async_session_maker() as session:
        res = await session.execute(
            select(User).where(User.role == "employee", User.is_active == True)
        )
        users = res.scalars().all()

    for user in users:
        try:
            await _bot.send_message(user.telegram_id, text, parse_mode="HTML")
        except Exception as e:
            log.error("Не удалось отправить уведомление об открытии %s: %s", user.telegram_id, e)


async def _send_cutoff_reminder() -> None:
    """Отправляет напоминание только тем сотрудникам, кто ещё не разместил заказ."""
    if _bot is None:
        return

    working_sats = await _get_working_sats()
    today_kyiv = datetime.now(kyiv_tz).date()
    tomorrow = today_kyiv + timedelta(days=1)
    while tomorrow.weekday() == 6 or (tomorrow.weekday() == 5 and tomorrow not in working_sats):
        tomorrow += timedelta(days=1)

    async with async_session_maker() as session:
        # ID сотрудников, у которых уже есть заказ на завтра
        ordered_res = await session.execute(
            select(Order.user_id).where(
                Order.order_date == tomorrow,
                Order.status != "cancelled",
            )
        )
        ordered_ids = {row[0] for row in ordered_res.all()}

        res = await session.execute(
            select(User).where(User.role == "employee", User.is_active == True)
        )
        users = res.scalars().all()

    text = (
        f"⏰ <b>Напоминание!</b>\n\n"
        f"Приём заказов на завтра заканчивается в <b>{_cutoff_str}</b>.\n"
        f"Если хотите заказать обед — поторопитесь! 🍽"
    )

    for user in users:
        if user.id in ordered_ids:
            continue
        try:
            await _bot.send_message(user.telegram_id, text, parse_mode="HTML")
        except Exception as e:
            log.error("Не удалось отправить напоминание %s: %s", user.telegram_id, e)


async def _lock_orders() -> None:
    """Блокирует все активные заказы на следующую дату доставки и добавляет долг."""
    working_sats = await _get_working_sats()
    today_kyiv = datetime.now(kyiv_tz).date()
    tomorrow = today_kyiv + timedelta(days=1)
    while tomorrow.weekday() == 6 or (tomorrow.weekday() == 5 and tomorrow not in working_sats):
        tomorrow += timedelta(days=1)

    async with async_session_maker() as session:
        res = await session.execute(
            select(Order)
            .where(Order.order_date == tomorrow, Order.status == "active")
            .options(selectinload(Order.user))
        )
        orders = res.scalars().all()

        # Pre-fill users that already have locked orders (created via /addorder)
        # to avoid charging delivery twice
        already_res = await session.execute(
            select(Order.user_id).where(Order.order_date == tomorrow, Order.status == "locked")
        )
        users_charged: set[int] = {row[0] for row in already_res.all()}

        for order in orders:
            order.status = "locked"
            if order.user:
                delivery = Decimal("10") if order.user_id not in users_charged else Decimal("0")
                users_charged.add(order.user_id)
                order.user.balance_debt = (order.user.balance_debt or Decimal(0)) + order.total_price + delivery

        # Перенумеровываем все незакрытые заказы без пропусков
        renumber_res = await session.execute(
            select(Order)
            .where(Order.order_date == tomorrow, Order.status != "cancelled")
            .order_by(Order.created_at.asc())
        )
        for i, order in enumerate(renumber_res.scalars().all(), start=1):
            order.daily_number = i

        await session.commit()
    log.info("Заблокировано заказов: %d", len(orders))


async def _send_daily_summary() -> None:
    """Отправляет кухонную сводку и чеки администратору ресторана."""
    if _bot is None:
        return

    working_sats = await _get_working_sats()
    today_kyiv = datetime.now(kyiv_tz).date()
    tomorrow = today_kyiv + timedelta(days=1)
    while tomorrow.weekday() == 6 or (tomorrow.weekday() == 5 and tomorrow not in working_sats):
        tomorrow += timedelta(days=1)

    async with async_session_maker() as session:
        # Включаем locked и cancel_requested — заказы ещё готовятся, отмена не одобрена
        res = await session.execute(
            select(Order)
            .where(
                Order.order_date == tomorrow,
                Order.status.in_(["locked", "cancel_requested"]),
            )
            .options(selectinload(Order.items), selectinload(Order.user))
            .order_by(Order.daily_number.asc())
        )
        orders = res.scalars().all()

        if not orders:
            log.info("Нет заказов на %s, сводка не отправляется.", tomorrow)
            return

        date_str = tomorrow.strftime("%d.%m.%Y")

        # 1. Кухонная сводка — количество каждого блюда
        dish_counts: dict[str, int] = {}
        for order in orders:
            for item in order.items:
                dish_counts[item.item_name] = dish_counts.get(item.item_name, 0) + item.quantity

        kitchen_lines = [f"🍳 <b>Кухонная сводка на {date_str}</b>\n"]
        for dish_name, qty in sorted(dish_counts.items(), key=lambda x: x[1], reverse=True):
            kitchen_lines.append(f"• {_esc(dish_name)} — <b>{qty} порц.</b>")
        kitchen_lines.append(f"\n<b>Всего заказов: {len(orders)}</b>")
        kitchen_text = "\n".join(kitchen_lines)

        # 2. Сборочные чеки — пронумерованные заказы (без имён)
        checks_lines = [f"📋 <b>Заказы на {date_str}</b>\n"]
        for order in orders:
            num = order.daily_number or order.id
            flag = " ⚠️" if order.status == "cancel_requested" else ""
            checks_lines.append(f"<b>Заказ №{num}</b>{flag}")
            for item in order.items:
                qty_str = f" ×{item.quantity}" if item.quantity > 1 else ""
                checks_lines.append(f"  • {_esc(item.item_name)}{qty_str}")
            checks_lines.append("")
        checks_text = "\n".join(checks_lines)

        # Получаем список администраторов ресторана и суперадминов
        admins_res = await session.execute(
            select(User).where(User.role.in_(["restaurant_admin", "super_admin"]), User.is_active == True)
        )
        admins = admins_res.scalars().all()

        # Получаем сотрудников, которые НЕ сделали заказ
        ordered_ids = {order.user_id for order in orders}
        employees_res = await session.execute(
            select(User).where(User.role == "employee", User.is_active == True)
        )
        non_ordering = [u for u in employees_res.scalars().all() if u.id not in ordered_ids]

    for admin in admins:
        try:
            await _bot.send_message(admin.telegram_id, kitchen_text, parse_mode="HTML")
            for chunk in _split_message(checks_text):
                await _bot.send_message(admin.telegram_id, chunk, parse_mode="HTML")
        except Exception as e:
            log.error("Не удалось отправить сводку %s: %s", admin.telegram_id, e)

    # Уведомляем каждого пользователя о финальном номере заказа
    for order in orders:
        if not order.user:
            continue
        num = order.daily_number or order.id
        items_lines = "\n".join(
            f"• {_esc(item.item_name)}" + (f" ×{item.quantity}" if item.quantity > 1 else "")
            for item in order.items
        )
        items_total = sum(float(item.price) * item.quantity for item in order.items)
        user_text = (
            f"🔔 <b>Заказ №{num} сформирован!</b>\n\n"
            f"📅 Дата доставки: {date_str}\n\n"
            f"{items_lines}\n\n"
            f"💰 Сумма: {items_total:.0f} ₴"
        )
        try:
            await _bot.send_message(order.user.telegram_id, user_text, parse_mode="HTML")
        except Exception as e:
            log.error("Не удалось уведомить пользователя %s: %s", order.user.telegram_id, e)

    # Уведомляем сотрудников, которые не оформили заказ
    no_order_text = (
        f"ℹ️ Приём заказов на <b>{date_str}</b> завершён.\n\n"
        f"Вы не оформили заказ на этот день.\n"
        f"Форма заказа откроется утром следующего рабочего дня."
    )
    for emp in non_ordering:
        try:
            await _bot.send_message(emp.telegram_id, no_order_text, parse_mode="HTML")
        except Exception as e:
            log.error("Не удалось уведомить сотрудника %s: %s", emp.telegram_id, e)


def _esc(text: str) -> str:
    """Экранирует HTML-спецсимволы в именах пользователей и блюдах."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _split_message(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks
