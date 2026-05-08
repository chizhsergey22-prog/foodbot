from __future__ import annotations
import json
from datetime import date, timedelta
from decimal import Decimal
import pytz
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, extract, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from db.models import Order, OrderItem, User, Setting, CancelRequest
from dependencies import CurrentUser, DbSession
from config import settings

router = APIRouter(prefix="/orders", tags=["orders"])


def _cart_key(user_id: int) -> str:
    return f"cart:{user_id}"


def _get_redis():
    import redis.asyncio as aioredis
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


# ── Оформление заказа ────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_order(user: CurrentUser, session: DbSession):
    # Проверяем дедлайн
    from routers.cart import _get_order_date_and_lock, _load_settings
    cutoff_str, working_sats = await _load_settings(session)
    order_date, is_locked = _get_order_date_and_lock(cutoff_str, working_sats)

    if is_locked:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Приём заказов завершён")

    # Берём корзину из Redis
    redis = _get_redis()
    try:
        raw = await redis.get(_cart_key(user.id))
    finally:
        await redis.aclose()

    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Корзина пуста")

    cart_items = json.loads(raw)
    if not cart_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Корзина пуста")


    # Порядковый номер заказа за день с retry на случай гонки
    total = Decimal(0)
    order = None
    for attempt in range(5):
        max_res = await session.execute(
            select(func.max(Order.daily_number)).where(Order.order_date == order_date)
        )
        daily_number = (max_res.scalar() or 0) + 1
        order = Order(user_id=user.id, order_date=order_date, status="active", daily_number=daily_number)
        session.add(order)
        try:
            async with session.begin_nested():
                await session.flush()
            break
        except IntegrityError:
            session.expunge(order)
            if attempt == 4:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось создать заказ")

    for ci in cart_items:
        price = Decimal(str(ci["price"]))
        qty = ci["quantity"]
        item = OrderItem(
            order_id=order.id,
            menu_item_id=ci["menu_item_id"],
            item_name=ci["name"],
            quantity=qty,
            price=price,
        )
        session.add(item)
        total += price * qty

    order.total_price = total
    await session.commit()

    # Чистим корзину
    redis = _get_redis()
    try:
        await redis.delete(_cart_key(user.id))
    finally:
        await redis.aclose()

    # Уведомление пользователю в бот
    items_text = "\n".join(
        f"• {ci['name']}" + (f" ×{ci['quantity']}" if ci["quantity"] > 1 else "")
        for ci in cart_items
    )
    tg_text = (
        f"✅ <b>Заказ №{daily_number} оформлен!</b>\n\n"
        f"📅 Дата доставки: {order_date.strftime('%d.%m.%Y')}\n\n"
        f"{items_text}\n\n"
        f"💰 Итого: {float(total):.0f} ₴"
    )
    import aiohttp
    tg_url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as http:
        try:
            await http.post(tg_url, json={
                "chat_id": user.telegram_id,
                "text": tg_text,
                "parse_mode": "HTML",
            })
        except Exception:
            pass

    return {"order_id": order.id, "order_date": str(order_date), "total": float(total)}


# ── Текущий заказ ─────────────────────────────────────────────────────────────

class OrderItemOut(BaseModel):
    id: int
    menu_item_id: int | None
    item_name: str
    quantity: int
    price: float


class OrderOut(BaseModel):
    id: int
    daily_number: int | None
    order_date: date
    status: str
    total_price: float
    items: list[OrderItemOut]


@router.get("/current", response_model=list[OrderOut])
async def get_current_orders(user: CurrentUser, session: DbSession):
    from routers.cart import _get_order_date_and_lock, _load_settings
    cutoff_str, working_sats = await _load_settings(session)
    order_date, _ = _get_order_date_and_lock(cutoff_str, working_sats)

    res = await session.execute(
        select(Order)
        .where(Order.user_id == user.id, Order.order_date == order_date, Order.status != "cancelled")
        .options(selectinload(Order.items))
        .order_by(Order.created_at.asc())
    )
    orders = res.scalars().all()
    return [
        OrderOut(
            id=o.id,
            daily_number=o.daily_number,
            order_date=o.order_date,
            status=o.status,
            total_price=float(o.total_price),
            items=[OrderItemOut(id=i.id, menu_item_id=i.menu_item_id, item_name=i.item_name, quantity=i.quantity, price=float(i.price)) for i in o.items],
        )
        for o in orders
    ]


# ── История заказов ───────────────────────────────────────────────────────────

@router.get("/history", response_model=list[OrderOut])
async def get_order_history(user: CurrentUser, session: DbSession):
    res = await session.execute(
        select(Order)
        .where(Order.user_id == user.id)
        .options(selectinload(Order.items))
        .order_by(Order.order_date.desc())
        .limit(30)
    )
    orders = res.scalars().all()
    return [
        OrderOut(
            id=o.id,
            daily_number=o.daily_number,
            order_date=o.order_date,
            status=o.status,
            total_price=float(o.total_price),
            items=[OrderItemOut(id=i.id, menu_item_id=i.menu_item_id, item_name=i.item_name, quantity=i.quantity, price=float(i.price)) for i in o.items],
        )
        for o in orders
    ]


# ── Ежемесячная статистика ────────────────────────────────────────────────────

class MonthlyStats(BaseModel):
    month: int
    year: int
    total: float
    orders_count: int
    balance_debt: float


@router.get("/stats/monthly", response_model=MonthlyStats)
async def get_monthly_stats(user: CurrentUser, session: DbSession):
    import datetime
    now = datetime.datetime.now(pytz.timezone(settings.TIMEZONE))
    month, year = now.month, now.year

    res = await session.execute(
        select(
            func.sum(Order.total_price),
            func.count(Order.id),
            func.count(Order.order_date.distinct()),
        )
        .where(
            Order.user_id == user.id,
            extract("month", Order.order_date) == month,
            extract("year", Order.order_date) == year,
            Order.status != "cancelled",
        )
    )
    row = res.one()
    food_total = float(row[0] or 0)
    count = row[1] or 0
    days = row[2] or 0
    total = food_total + days * 10

    user_res = await session.execute(select(User).where(User.id == user.id))
    u = user_res.scalar_one()

    return MonthlyStats(month=month, year=year, total=total, orders_count=count, balance_debt=float(u.balance_debt))


# ── Запрос на отмену (после дедлайна) ────────────────────────────────────────

@router.post("/{order_id}/cancel-request", status_code=status.HTTP_202_ACCEPTED)
async def request_cancel(order_id: int, user: CurrentUser, session: DbSession):
    res = await session.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user.id)
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    if order.status == "active":
        # Долг ещё не начислен (начисляется планировщиком в дедлайн) — просто отменяем
        order.status = "cancelled"
        await session.commit()
        return {"status": "cancelled"}

    if order.status == "locked":
        existing = await session.execute(
            select(CancelRequest).where(CancelRequest.order_id == order_id, CancelRequest.status == "pending")
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Запрос уже отправлен")

        cr = CancelRequest(order_id=order_id, user_id=user.id)
        session.add(cr)
        order.status = "cancel_requested"
        await session.commit()
        await session.refresh(cr)

        # Уведомляем суперадминов через Telegram Bot API (без aiogram)
        admins = (await session.execute(
            select(User).where(User.role == "super_admin", User.is_active == True)
        )).scalars().all()

        text = (
            f"⚠️ <b>{user.full_name}</b> запрашивает отмену заказа №{order_id} "
            f"на {order.order_date.strftime('%d.%m.%Y')} "
            f"({float(order.total_price):.0f} ₴)\n"
            f"Запрос #: {cr.id}"
        )
        import aiohttp, json as _json
        kb = {"inline_keyboard": [[
            {"text": "✅ Подтвердить", "callback_data": f"cancel_approve:{cr.id}"},
            {"text": "❌ Отклонить",   "callback_data": f"cancel_reject:{cr.id}"},
        ]]}
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as http:
            for admin in admins:
                try:
                    await http.post(url, json={
                        "chat_id": admin.telegram_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": kb,
                    })
                except Exception:
                    pass

        return {"status": "cancel_requested", "request_id": cr.id}

    raise HTTPException(status_code=400, detail=f"Нельзя отменить заказ со статусом '{order.status}'")
