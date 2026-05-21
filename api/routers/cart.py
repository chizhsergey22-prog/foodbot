from __future__ import annotations
import json
from datetime import date, timedelta
import pytz
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy import select
from db.models import MenuItem, Setting, Order
from dependencies import CurrentUser, DbSession
from config import settings

router = APIRouter(prefix="/cart", tags=["cart"])

CART_TTL = 60 * 60 * 24 * 3  # 3 дня


# Redis is now managed via request.app.state.redis


def _cart_key(user_id: int) -> str:
    return f"cart:{user_id}"


def _get_order_date_and_lock(cutoff_str: str, working_sats: set[date] | None = None) -> tuple[date, bool, str]:
    """Определяет дату заказа, заблокирована ли корзина, и когда откроется."""
    h, m = cutoff_str.split(":")
    cutoff_h, cutoff_m = int(h), int(m)
    OPEN_H = 12

    tz = pytz.timezone(settings.TIMEZONE)
    import datetime as dt_mod
    now = dt_mod.datetime.now(tz)
    today = now.date()
    weekday = today.weekday()  # 0=Пн … 4=Пт, 5=Сб, 6=Вс

    after_cutoff = (now.hour, now.minute) >= (cutoff_h, cutoff_m)
    before_open  = (now.hour, now.minute) <  (OPEN_H, 0)

    wsat = working_sats or set()
    opens_at = ""

    if weekday == 4:  # Пятница
        tomorrow = today + timedelta(days=1)
        if tomorrow in wsat:
            # Рабочая суббота: окно 12–17
            order_date = tomorrow
            is_locked = before_open or after_cutoff
            if is_locked:
                opens_at = f"сегодня в {OPEN_H:02d}:00" if before_open else f"завтра в {OPEN_H:02d}:00"
        else:
            order_date = today + timedelta(days=3)  # Пн
            is_locked = before_open  # opens 12:00 Fri, closes Sun 17:00
            if is_locked:
                opens_at = f"сегодня в {OPEN_H:02d}:00"
    elif weekday == 5:  # Сб → Пн, без ограничений
        order_date = today + timedelta(days=2)
        is_locked = False
    elif weekday == 6:  # Вс → Пн, до 17:00
        order_date = today + timedelta(days=1)
        is_locked = after_cutoff
        if is_locked:
            opens_at = f"завтра в {OPEN_H:02d}:00"
    else:  # Пн–Чт: окно 12–17
        order_date = today + timedelta(days=1)
        is_locked = before_open or after_cutoff
        if is_locked:
            opens_at = f"сегодня в {OPEN_H:02d}:00" if before_open else f"завтра в {OPEN_H:02d}:00"

    return order_date, is_locked, opens_at


class CartItem(BaseModel):
    menu_item_id: int
    name: str
    price: float
    quantity: int


class CartResponse(BaseModel):
    order_date: date
    is_locked: bool
    opens_at: str
    items: list[CartItem]
    total: float


def _parse_working_sats(value: str) -> set[date]:
    result: set[date] = set()
    for s in value.split(","):
        s = s.strip()
        if s:
            try:
                from datetime import date as date_cls
                result.add(date_cls.fromisoformat(s))
            except ValueError:
                pass
    return result


async def _load_settings(session) -> tuple[str, set[date]]:
    res = await session.execute(
        select(Setting).where(Setting.key.in_(["cutoff_time", "working_saturdays"]))
    )
    smap = {s.key: s.value for s in res.scalars().all()}
    cutoff_str = smap.get("cutoff_time", "17:00")
    working_sats = _parse_working_sats(smap.get("working_saturdays", ""))
    return cutoff_str, working_sats


@router.get("/", response_model=CartResponse)
async def get_cart(request: Request, user: CurrentUser, session: DbSession):
    cutoff_str, working_sats = await _load_settings(session)
    order_date, is_locked, opens_at = _get_order_date_and_lock(cutoff_str, working_sats)

    redis = request.app.state.redis
    raw = await redis.get(_cart_key(user.id))

    items: list[CartItem] = []
    if raw:
        items = [CartItem(**i) for i in json.loads(raw)]

    total = sum(i.price * i.quantity for i in items)
    return CartResponse(order_date=order_date, is_locked=is_locked, opens_at=opens_at, items=items, total=total)


class UpdateCartBody(BaseModel):
    items: list[CartItem]


@router.put("/", response_model=CartResponse)
async def update_cart(body: UpdateCartBody, request: Request, user: CurrentUser, session: DbSession):
    cutoff_str, working_sats = await _load_settings(session)
    order_date, is_locked, opens_at = _get_order_date_and_lock(cutoff_str, working_sats)

    if is_locked:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Cart is locked after cutoff time")

    # Проверяем, что блюда существуют и не в стоп-листе
    valid_items = []
    for item in body.items:
        r = await session.execute(
            select(MenuItem).where(
                MenuItem.id == item.menu_item_id,
                MenuItem.is_active == True,
            )
        )
        menu_item = r.scalar_one_or_none()
        if menu_item and item.quantity > 0:
            valid_items.append(CartItem(
                menu_item_id=menu_item.id,
                name=menu_item.name,
                price=float(menu_item.price),
                quantity=item.quantity,
            ))

    redis = request.app.state.redis
    if valid_items:
        await redis.set(_cart_key(user.id), json.dumps([i.model_dump() for i in valid_items]), ex=CART_TTL)
    else:
        await redis.delete(_cart_key(user.id))

    total = sum(i.price * i.quantity for i in valid_items)
    return CartResponse(order_date=order_date, is_locked=is_locked, opens_at=opens_at, items=valid_items, total=total)


@router.delete("/")
async def clear_cart(request: Request, user: CurrentUser, session: DbSession):
    cutoff_str, working_sats = await _load_settings(session)
    _, is_locked, _opens = _get_order_date_and_lock(cutoff_str, working_sats)

    if is_locked:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Cart is locked after cutoff time")

    redis = request.app.state.redis
    await redis.delete(_cart_key(user.id))

    return {"status": "cleared"}
