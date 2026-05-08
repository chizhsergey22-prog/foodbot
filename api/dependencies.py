from __future__ import annotations
from typing import Annotated
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.connection import get_session
from db.models import User
from utils.tg_auth import validate_init_data
from config import settings


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Telegram auth")

    init_data = authorization[4:]
    data = validate_init_data(init_data, settings.BOT_TOKEN)

    tg_user = data.get("user")
    if not tg_user or not isinstance(tg_user, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No user in init data")

    telegram_id = tg_user.get("id")
    if not telegram_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No user id")

    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not registered")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_session)]
