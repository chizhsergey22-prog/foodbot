from __future__ import annotations
from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from db.connection import async_session_maker
from db.models import User
from config import settings


class AuthMiddleware(BaseMiddleware):
    """
    Добавляет объект db_user в data для каждого апдейта.
    Суперадмины из конфига регистрируются автоматически.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if tg_user is None:
            return await handler(event, data)

        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == tg_user.id)
            )
            db_user = result.scalar_one_or_none()

            # Авто-регистрация суперадмина из конфига
            if db_user is None and tg_user.id in settings.super_admin_list:
                db_user = User(
                    telegram_id=tg_user.id,
                    full_name=tg_user.full_name or "SuperAdmin",
                    username=tg_user.username,
                    role="super_admin",
                )
                session.add(db_user)
                await session.commit()
                await session.refresh(db_user)

        data["db_user"] = db_user
        return await handler(event, data)
