from __future__ import annotations
import secrets
from decimal import Decimal
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, update, func, extract
from db.models import User, InviteCode, MenuItem, Category, Order, OrderItem, CancelRequest, Setting, DailyStat
from db.connection import async_session_maker
from keyboards.inline import cancel_request_keyboard
from config import settings
from utils.time_utils import parse_cutoff, get_next_order_date, parse_working_sats, encode_working_sats
from services.google_sheets import generate_monthly_report

router = Router(name="super_admin")


def _is_super(user: User | None) -> bool:
    return user is not None and user.role == "super_admin"


# ── /invite <имя> — генерация именного инвайт-кода ──────────────────────────

@router.message(Command("invite"))
async def cmd_invite(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    args = (command.args or "").strip().rsplit(maxsplit=1)
    if not args:
        await message.answer("Использование: /invite Имя  или  /invite Имя 601")
        return

    initial_debt = Decimal("0")
    if len(args) == 2:
        try:
            initial_debt = Decimal(args[1].replace(",", "."))
            label = args[0].strip()
        except Exception:
            label = (command.args or "").strip()
    else:
        label = args[0].strip()

    if not label:
        await message.answer("Использование: /invite Имя  или  /invite Имя 601")
        return

    code = secrets.token_urlsafe(12)
    async with async_session_maker() as session:
        session.add(InviteCode(code=code, label=label, initial_debt=initial_debt, created_by=message.from_user.id))
        await session.commit()

    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={code}"
    await message.answer(
        f"✅ Инвайт для <b>{label}</b>:\n\n<code>{code}</code>\n\nСсылка:\n{link}",
        parse_mode="HTML",
    )


# ── /inviteadmin <имя> — инвайт для администратора заведения ─────────────────

@router.message(Command("inviteadmin"))
async def cmd_inviteadmin(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    label = (command.args or "").strip()
    if not label:
        await message.answer("Использование: /inviteadmin Имя")
        return

    code = secrets.token_urlsafe(12)
    async with async_session_maker() as session:
        session.add(InviteCode(
            code=code,
            label=label,
            role="restaurant_admin",
            created_by=message.from_user.id,
        ))
        await session.commit()

    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={code}"
    await message.answer(
        f"🍴 Инвайт администратора заведения для <b>{label}</b>:\n\n"
        f"<code>{code}</code>\n\nСсылка:\n{link}",
        parse_mode="HTML",
    )


# ── /setrole <user_id> <role> — назначение роли ──────────────────────────────

@router.message(Command("setrole"))
async def cmd_setrole(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    args = (command.args or "").split()
    if len(args) != 2:
        await message.answer("Использование: /setrole <telegram_id> <employee|restaurant_admin|super_admin>")
        return

    try:
        target_id = int(args[0].strip("<>"))
    except ValueError:
        await message.answer("❌ Неверный telegram_id.")
        return

    role = args[1].strip("<>")
    if role not in ("employee", "restaurant_admin", "super_admin"):
        await message.answer("❌ Роль должна быть: employee, restaurant_admin или super_admin.")
        return

    async with async_session_maker() as session:
        res = await session.execute(select(User).where(User.telegram_id == target_id))
        target = res.scalar_one_or_none()
        if not target:
            await message.answer("❌ Пользователь не найден в системе.")
            return
        target.role = role
        await session.commit()

    from utils.commands import set_user_commands
    await set_user_commands(message.bot, target_id, role)

    await message.answer(f"✅ Роль пользователя {target_id} изменена на *{role}*.", parse_mode="Markdown")


# ── /price <название> <новая_цена> — изменение цены ─────────────────────────

@router.message(Command("price"))
async def cmd_price(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    args = (command.args or "").rsplit(maxsplit=1)
    if len(args) != 2:
        await message.answer("Использование: /price <название блюда> <новая цена>")
        return

    name, price_str = args
    try:
        new_price = Decimal(price_str.replace(",", "."))
    except Exception:
        await message.answer("❌ Неверный формат цены.")
        return

    async with async_session_maker() as session:
        res = await session.execute(select(MenuItem).where(MenuItem.name.ilike(name.strip())))
        item = res.scalar_one_or_none()
        if not item:
            await message.answer(f'❌ Блюдо "{name}" не найдено.')
            return
        item.price = new_price
        await session.commit()

    await message.answer(f'✅ Цена *"{item.name}"* обновлена: *{new_price} ₴*.', parse_mode="Markdown")


# ── Отмена любого FSM-состояния ─────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("❌ Действие отменено.")


# ── FSM добавления нового блюда /additem ────────────────────────────────────

class AddItemStates(StatesGroup):
    name = State()
    description = State()
    price = State()
    category = State()


@router.message(Command("additem"))
async def cmd_additem(message: Message, state: FSMContext, db_user: User | None):
    if not _is_super(db_user):
        return

    await message.answer("📝 Введите *название* нового блюда:", parse_mode="Markdown")
    await state.set_state(AddItemStates.name)


@router.message(AddItemStates.name)
async def additem_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите *описание* (или отправьте `-` чтобы пропустить):", parse_mode="Markdown")
    await state.set_state(AddItemStates.description)


@router.message(AddItemStates.description)
async def additem_description(message: Message, state: FSMContext):
    desc = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=desc)
    await message.answer("Введите *цену* в гривнах (например: 120):", parse_mode="Markdown")
    await state.set_state(AddItemStates.price)


@router.message(AddItemStates.price)
async def additem_price(message: Message, state: FSMContext):
    try:
        price = Decimal(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("❌ Введите корректную цену (число).")
        return

    async with async_session_maker() as session:
        res = await session.execute(select(Category).where(Category.is_active == True).order_by(Category.sort_order))
        cats = res.scalars().all()

    cats_text = "\n".join(f"{c.id}. {c.name}" for c in cats)
    await state.update_data(price=str(price))
    await message.answer(f"Выберите *категорию* (введите номер):\n\n{cats_text}", parse_mode="Markdown")
    await state.set_state(AddItemStates.category)


@router.message(AddItemStates.category)
async def additem_category(message: Message, state: FSMContext):
    try:
        cat_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите номер категории.")
        return

    data = await state.get_data()
    async with async_session_maker() as session:
        cat_res = await session.execute(select(Category).where(Category.id == cat_id))
        cat = cat_res.scalar_one_or_none()
        if not cat:
            await message.answer("❌ Категория не найдена.")
            return

        item = MenuItem(
            name=data["name"],
            description=data.get("description"),
            price=Decimal(data["price"]),
            category_id=cat_id,
        )
        session.add(item)
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Блюдо *{data['name']}* добавлено в категорию *{cat.name}*.",
        parse_mode="Markdown",
    )


# ── /cutoff <HH:MM> — изменение дедлайна ────────────────────────────────────

@router.message(Command("cutoff"))
async def cmd_cutoff(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    time_str = (command.args or "").strip()
    try:
        h, m = parse_cutoff(time_str)
    except Exception:
        await message.answer("Использование: /cutoff 17:00")
        return

    if not (0 <= h <= 23 and 0 <= m <= 59):
        await message.answer("Использование: /cutoff 17:00")
        return

    async with async_session_maker() as session:
        res = await session.execute(select(Setting).where(Setting.key == "cutoff_time"))
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = time_str
        else:
            session.add(Setting(key="cutoff_time", value=time_str))
        await session.commit()

    # Обновляем планировщик
    from services.scheduler import reschedule_jobs
    await reschedule_jobs(message.bot, h, m)

    await message.answer(f"✅ Дедлайн приёма заказов изменён на *{time_str}*.", parse_mode="Markdown")


# ── /report [MM.YYYY] — выгрузка в Google Sheets ────────────────────────────

@router.message(Command("report"))
async def cmd_report(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    args = (command.args or "").strip()
    from datetime import date
    if args:
        try:
            parts = args.split(".")
            month, year = int(parts[0]), int(parts[1])
        except Exception:
            await message.answer("Использование: /report или /report 05.2026")
            return
    else:
        today = date.today()
        month, year = today.month, today.year

    wait_msg = await message.answer("⏳ Формирую отчёт, подождите...")
    try:
        url = await generate_monthly_report(month, year)
        await wait_msg.edit_text(f"✅ Отчёт за {month:02d}.{year} готов:\n{url}")
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка при создании отчёта: {e}")


# ── /balances [MM.YYYY] — отчёт по расходам в боте ─────────────────────────

@router.message(Command("balances"))
async def cmd_balances(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    args = (command.args or "").strip()
    from datetime import date as _date
    if args:
        try:
            parts = args.split(".")
            month, year = int(parts[0]), int(parts[1])
        except Exception:
            await message.answer("Использование: /balances или /balances 05.2026")
            return
    else:
        today = _date.today()
        month, year = today.month, today.year

    async with async_session_maker() as session:
        res = await session.execute(
            select(
                User.full_name,
                User.team,
                func.sum(Order.total_price),
                func.count(Order.order_date.distinct()),
            )
            .join(Order, Order.user_id == User.id)
            .where(
                extract("month", Order.order_date) == month,
                extract("year", Order.order_date) == year,
                Order.status != "cancelled",
            )
            .group_by(User.id, User.full_name, User.team)
            .order_by(User.team, func.sum(Order.total_price).desc())
        )
        rows = res.all()

    MONTHS_RU = ["Январь","Февраль","Март","Апрель","Май","Июнь",
                 "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]

    if not rows:
        await message.answer(f"📊 Заказов за {MONTHS_RU[month-1]} {year} нет.")
        return

    # Группируем по командам
    from itertools import groupby
    teams: dict[str, list] = {}
    for name, team, food_sum, days in rows:
        key = team or "Без команды"
        display_total = float(food_sum) + int(days) * 10
        teams.setdefault(key, []).append((name, display_total))

    TEAM_ORDER = ["Тапок", "СС", "Танк", "Без команды"]
    lines = [f"📊 <b>{MONTHS_RU[month-1]} {year}</b>\n"]
    grand_total = 0.0

    for team_name in TEAM_ORDER:
        members = teams.get(team_name)
        if not members:
            continue
        team_total = sum(t for _, t in members)
        grand_total += team_total
        lines.append(f"<b>— {team_name} —</b>")
        for name, display_total in members:
            lines.append(f"• {name} — <b>{display_total:.0f} ₴</b>")
        lines.append(f"<i>Итого {team_name}: {team_total:.0f} ₴</i>\n")

    lines.append(f"<b>Всего: {grand_total:.0f} ₴</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /setteam <имя> <команда> — назначить команду ────────────────────────────

@router.message(Command("setteam"))
async def cmd_setteam(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    args = (command.args or "").rsplit(maxsplit=1)
    if len(args) != 2:
        await message.answer("Использование: /setteam <имя> <Тапок|СС|Танк>")
        return

    name, team = args[0].strip(), args[1].strip()
    if team not in ("Тапок", "СС", "Танк"):
        await message.answer("❌ Команда должна быть: Тапок, СС или Танк")
        return

    async with async_session_maker() as session:
        res = await session.execute(select(User).where(User.full_name.ilike(name)))
        user = res.scalar_one_or_none()
        if not user:
            await message.answer(f'❌ Пользователь "{name}" не найден.')
            return
        user.team = team
        await session.commit()

    await message.answer(f'✅ <b>{user.full_name}</b> → команда <b>{team}</b>', parse_mode="HTML")


# ── /addorder — ручное добавление заказа супер-админом ──────────────────────

class AddOrderStates(StatesGroup):
    select_user = State()
    select_items = State()


@router.message(Command("addorder"))
async def cmd_addorder(message: Message, state: FSMContext, db_user: User | None):
    if not _is_super(db_user):
        return

    async with async_session_maker() as session:
        res = await session.execute(
            select(User)
            .where(User.role == "employee", User.is_active == True)
            .order_by(User.full_name)
        )
        users = res.scalars().all()

    if not users:
        await message.answer("Нет зарегистрированных сотрудников.")
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for u in users:
        builder.button(text=u.full_name, callback_data=f"ao_user:{u.id}")
    builder.adjust(1)

    await message.answer("Выберите сотрудника:", reply_markup=builder.as_markup())
    await state.set_state(AddOrderStates.select_user)


@router.callback_query(AddOrderStates.select_user, F.data.startswith("ao_user:"))
async def ao_select_user(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])

    async with async_session_maker() as session:
        user_res = await session.execute(select(User).where(User.id == user_id))
        user = user_res.scalar_one_or_none()

        items_res = await session.execute(
            select(MenuItem)
            .join(Category, MenuItem.category_id == Category.id)
            .where(MenuItem.is_active == True, MenuItem.is_stop_list == False, Category.is_active == True)
            .order_by(Category.sort_order, MenuItem.name)
        )
        items = items_res.scalars().all()

    if not items:
        await callback.answer("Нет доступных блюд.", show_alert=True)
        return

    await state.update_data(user_id=user_id, user_name=user.full_name, selected={})

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=f"{item.name} — {item.price:.0f}₴", callback_data=f"ao_item:{item.id}")
    builder.button(text="✅ Оформить заказ", callback_data="ao_done")
    builder.adjust(1)

    await callback.message.edit_text(
        f"Заказ для <b>{user.full_name}</b>\n\nВыберите блюда (нажмите несколько раз для увеличения количества):",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await state.set_state(AddOrderStates.select_items)
    await callback.answer()


@router.callback_query(AddOrderStates.select_items, F.data.startswith("ao_item:"))
async def ao_add_item(callback: CallbackQuery, state: FSMContext):
    item_id = str(callback.data.split(":")[1])
    data = await state.get_data()
    selected: dict = data.get("selected", {})
    selected[item_id] = selected.get(item_id, 0) + 1
    await state.update_data(selected=selected)

    async with async_session_maker() as session:
        res = await session.execute(select(MenuItem).where(MenuItem.id == int(item_id)))
        item = res.scalar_one_or_none()

    if item is None:
        await callback.answer("Блюдо недоступно.", show_alert=True)
        return
    await callback.answer(f"✓ {item.name} ×{selected[item_id]}")


@router.callback_query(AddOrderStates.select_items, F.data == "ao_done")
async def ao_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id: int = data["user_id"]
    user_name: str = data["user_name"]
    selected: dict = data.get("selected", {})

    if not selected:
        await callback.answer("Не выбрано ни одного блюда!", show_alert=True)
        return

    async with async_session_maker() as session:
        wsat_res = await session.execute(select(Setting).where(Setting.key == "working_saturdays"))
        wsat_row = wsat_res.scalar_one_or_none()
        cutoff_res = await session.execute(select(Setting).where(Setting.key == "cutoff_time"))
        cutoff_row = cutoff_res.scalar_one_or_none()
        working_sats = parse_working_sats(wsat_row.value if wsat_row else "")
        h, m = parse_cutoff(cutoff_row.value if cutoff_row else "17:00")
    order_date = get_next_order_date(cutoff_hour=h, cutoff_minute=m, working_sats=working_sats)

    async with async_session_maker() as session:
        item_ids = [int(k) for k in selected]
        items_res = await session.execute(select(MenuItem).where(MenuItem.id.in_(item_ids)))
        items_map = {str(item.id): item for item in items_res.scalars().all()}

        total = sum(items_map[k].price * qty for k, qty in selected.items() if k in items_map)

        max_num_res = await session.execute(
            select(func.max(Order.daily_number)).where(
                Order.order_date == order_date,
                Order.status != "cancelled",
            )
        )
        daily_number = (max_num_res.scalar() or 0) + 1

        order = Order(
            user_id=user_id,
            order_date=order_date,
            status="locked",
            total_price=total,
            daily_number=daily_number,
        )
        session.add(order)
        await session.flush()

        for str_id, qty in selected.items():
            if str_id not in items_map:
                continue
            item = items_map[str_id]
            session.add(OrderItem(
                order_id=order.id,
                menu_item_id=item.id,
                item_name=item.name,
                price=item.price,
                quantity=qty,
            ))

        user_res = await session.execute(select(User).where(User.id == user_id))
        user = user_res.scalar_one_or_none()
        if user:
            other_orders = await session.execute(
                select(func.count(Order.id)).where(
                    Order.user_id == user_id,
                    Order.order_date == order_date,
                    Order.status != "cancelled",
                    Order.id != order.id,
                )
            )
            delivery = Decimal("10") if (other_orders.scalar() or 0) == 0 else Decimal("0")
            user.balance_debt = (user.balance_debt or Decimal(0)) + total + delivery

        await session.commit()

    items_text = "\n".join(
        f"• {items_map[k].name}" + (f" ×{v}" if v > 1 else "")
        for k, v in selected.items() if k in items_map
    )
    await callback.message.edit_text(
        f"✅ Заказ №{daily_number} для <b>{user_name}</b> создан!\n\n"
        f"📅 {order_date.strftime('%d.%m.%Y')}\n\n"
        f"{items_text}\n\n"
        f"💰 Итого: {float(total):.0f} ₴",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


# ── Модерация запросов на отмену ────────────────────────────────────────────

@router.callback_query(F.data.startswith("cancel_approve:"))
async def on_cancel_approve(callback: CallbackQuery, db_user: User | None):
    if not _is_super(db_user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        res = await session.execute(
            select(CancelRequest).where(CancelRequest.id == request_id, CancelRequest.status == "pending")
        )
        req = res.scalar_one_or_none()
        if not req:
            await callback.answer("Запрос уже обработан.", show_alert=True)
            return

        from datetime import datetime, timezone
        req.status = "approved"
        req.resolved_by = callback.from_user.id
        req.resolved_at = datetime.now(timezone.utc)

        order_res = await session.execute(select(Order).where(Order.id == req.order_id))
        order = order_res.scalar_one_or_none()
        if order:
            order.status = "cancelled"
            user_res = await session.execute(select(User).where(User.id == order.user_id))
            user = user_res.scalar_one_or_none()
            if user:
                remaining = await session.execute(
                    select(func.count(Order.id)).where(
                        Order.user_id == order.user_id,
                        Order.order_date == order.order_date,
                        Order.status != "cancelled",
                        Order.id != order.id,
                    )
                )
                refund = order.total_price + (Decimal("10") if (remaining.scalar() or 0) == 0 else Decimal("0"))
                user.balance_debt = max(Decimal(0), user.balance_debt - refund)

        await session.commit()

        # Уведомляем сотрудника
        if order and user:
            try:
                await callback.bot.send_message(
                    user.telegram_id,
                    "✅ Ваш запрос на отмену заказа *одобрен*. Заказ отменён.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ *Отмена подтверждена*", parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_reject:"))
async def on_cancel_reject(callback: CallbackQuery, db_user: User | None):
    if not _is_super(db_user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        res = await session.execute(
            select(CancelRequest).where(CancelRequest.id == request_id, CancelRequest.status == "pending")
        )
        req = res.scalar_one_or_none()
        if not req:
            await callback.answer("Запрос уже обработан.", show_alert=True)
            return

        from datetime import datetime, timezone
        req.status = "rejected"
        req.resolved_by = callback.from_user.id
        req.resolved_at = datetime.now(timezone.utc)

        order_res = await session.execute(select(Order).where(Order.id == req.order_id))
        order = order_res.scalar_one_or_none()
        if order and order.status == "cancel_requested":
            order.status = "locked"

        await session.commit()

        if order:
            user_res = await session.execute(select(User).where(User.id == order.user_id))
            user = user_res.scalar_one_or_none()
            if user:
                try:
                    await callback.bot.send_message(
                        user.telegram_id,
                        "❌ Ваш запрос на отмену заказа *отклонён*. Заказ остаётся в силе.",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ *Отмена отклонена*", parse_mode="Markdown"
    )
    await callback.answer()


# ── /deliver <дата> [такси] — отметить заказы как доставленные ───────────────

@router.message(Command("deliver"))
async def cmd_deliver(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    from datetime import date as date_type
    args = (command.args or "").strip().split()
    if not args:
        await message.answer("Использование: /deliver 09.05 или /deliver 09.05 150")
        return

    try:
        parts = args[0].split(".")
        day, month = int(parts[0]), int(parts[1])
        year = int(parts[2]) if len(parts) > 2 else date_type.today().year
        target = date_type(year, month, day)
    except Exception:
        await message.answer("❌ Неверный формат даты. Используй: /deliver 09.05")
        return

    taxi: Decimal | None = None
    if len(args) >= 2:
        try:
            taxi = Decimal(args[1].replace(",", "."))
        except Exception:
            await message.answer("❌ Неверная сумма такси. Пример: /deliver 09.05 150")
            return

    from sqlalchemy.orm import selectinload
    async with async_session_maker() as session:
        res = await session.execute(
            select(Order)
            .where(
                Order.order_date == target,
                Order.status.in_(["locked", "cancel_requested"]),
            )
            .options(selectinload(Order.user), selectinload(Order.items))
        )
        orders = res.scalars().all()

        if not orders:
            await message.answer(f"Нет активных заказов на {target.strftime('%d.%m.%Y')}.")
            return

        for order in orders:
            order.status = "delivered"

        if taxi is not None:
            stat_res = await session.execute(select(DailyStat).where(DailyStat.order_date == target))
            stat = stat_res.scalar_one_or_none()
            if stat:
                stat.taxi_cost = taxi
            else:
                session.add(DailyStat(order_date=target, taxi_cost=taxi))

        await session.commit()

    date_str = target.strftime("%d.%m.%Y")
    for order in orders:
        if not order.user:
            continue
        num = order.daily_number or order.id
        items_lines = "\n".join(
            f"• {item.item_name}" + (f" ×{item.quantity}" if item.quantity > 1 else "")
            for item in order.items
        )
        total = sum(float(item.price) * item.quantity for item in order.items)
        user_text = (
            f"✅ <b>Заказ №{num} доставлен!</b>\n\n"
            f"📅 {date_str}\n\n"
            f"{items_lines}\n\n"
            f"💰 Сумма: {total:.0f} ₴"
        )
        try:
            await message.bot.send_message(order.user.telegram_id, user_text, parse_mode="HTML")
        except Exception:
            pass

    taxi_text = f"\n🚕 Такси: <b>{taxi:.0f} ₴</b>" if taxi is not None else ""
    await message.answer(
        f"✅ {len(orders)} заказ(ов) на {date_str} отмечены как <b>доставлены</b>.{taxi_text}",
        parse_mode="HTML",
    )


# ── /worksat — управление рабочими субботами ─────────────────────────────────

@router.message(Command("worksat"))
async def cmd_worksat(message: Message, command: CommandObject, db_user: User | None):
    if not _is_super(db_user):
        return

    from datetime import date as date_type

    async with async_session_maker() as session:
        res = await session.execute(select(Setting).where(Setting.key == "working_saturdays"))
        row = res.scalar_one_or_none()
        current = parse_working_sats(row.value if row else "")

        arg = (command.args or "").strip()

        if not arg:
            # Показываем список ближайших рабочих суббот
            today = date_type.today()
            upcoming = sorted(d for d in current if d >= today)
            if upcoming:
                lines = "\n".join(f"• {d.strftime('%d.%m.%Y')}" for d in upcoming)
                text = f"📅 <b>Рабочие субботы:</b>\n{lines}"
            else:
                text = "📅 Рабочих суббот не запланировано."
            text += "\n\n<i>Чтобы добавить/убрать: /worksat YYYY-MM-DD</i>"
            await message.answer(text, parse_mode="HTML")
            return

        try:
            target = date_type.fromisoformat(arg)
        except ValueError:
            await message.answer("❌ Неверный формат даты. Используй: /worksat 2026-05-09")
            return

        if target.weekday() != 5:
            await message.answer("❌ Указанная дата не является субботой.")
            return

        if target in current:
            current.discard(target)
            action = f"❌ {target.strftime('%d.%m.%Y')} убрана из рабочих суббот."
        else:
            current.add(target)
            action = f"✅ {target.strftime('%d.%m.%Y')} добавлена как рабочая суббота."

        new_value = encode_working_sats(current)
        if row:
            row.value = new_value
        else:
            session.add(Setting(key="working_saturdays", value=new_value))
        await session.commit()

    await message.answer(action)
