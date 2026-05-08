from __future__ import annotations
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

EMPLOYEE_COMMANDS = [
    BotCommand(command="start",  description="Открыть приложение"),
    BotCommand(command="mydebt", description="Мой баланс"),
]

RESTAURANT_ADMIN_COMMANDS = [
    BotCommand(command="start",    description="Панель администратора"),
]

SUPER_ADMIN_COMMANDS = [
    BotCommand(command="start",        description="Открыть приложение"),
    BotCommand(command="mydebt",       description="Мой баланс"),
    BotCommand(command="orders",       description="Заказы на сегодня"),
    BotCommand(command="portions",     description="Сводка порций по блюдам"),
    BotCommand(command="invite",       description="Создать инвайт-код"),
    BotCommand(command="inviteadmin",  description="Инвайт для администратора заведения"),
    BotCommand(command="setrole",      description="Назначить роль пользователю"),
    BotCommand(command="price",        description="Изменить цену блюда"),
    BotCommand(command="additem",      description="Добавить блюдо в меню"),
    BotCommand(command="cutoff",       description="Изменить время дедлайна"),
    BotCommand(command="deliver",      description="Отметить заказы доставленными"),
    BotCommand(command="worksat",      description="Управление рабочими субботами"),
    BotCommand(command="report",       description="Отчёт в Google Sheets"),
    BotCommand(command="balances",     description="Расходы сотрудников за месяц"),
    BotCommand(command="addorder",     description="Добавить заказ вручную"),
    BotCommand(command="setteam",      description="Назначить команду пользователю"),
    BotCommand(command="cancel",       description="Отменить текущее действие"),
]

_COMMANDS_BY_ROLE = {
    "employee":        EMPLOYEE_COMMANDS,
    "restaurant_admin": RESTAURANT_ADMIN_COMMANDS,
    "super_admin":     SUPER_ADMIN_COMMANDS,
}


async def set_bot_commands(bot: Bot) -> None:
    from sqlalchemy import select
    from db.connection import async_session_maker
    from db.models import User

    await bot.set_my_commands(EMPLOYEE_COMMANDS, scope=BotCommandScopeDefault())

    async with async_session_maker() as session:
        res = await session.execute(
            select(User).where(
                User.role.in_(("restaurant_admin", "super_admin")),
                User.is_active == True,
            )
        )
        admins = res.scalars().all()

    for user in admins:
        commands = _COMMANDS_BY_ROLE.get(user.role, EMPLOYEE_COMMANDS)
        try:
            await bot.set_my_commands(
                commands,
                scope=BotCommandScopeChat(chat_id=user.telegram_id),
            )
        except Exception:
            pass


async def set_user_commands(bot: Bot, telegram_id: int, role: str) -> None:
    commands = _COMMANDS_BY_ROLE.get(role, EMPLOYEE_COMMANDS)
    try:
        if role == "employee":
            await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=telegram_id))
        else:
            await bot.set_my_commands(
                commands,
                scope=BotCommandScopeChat(chat_id=telegram_id),
            )
    except Exception:
        pass
