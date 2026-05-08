import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import select
from config import settings
from db.connection import async_session_maker
from db.models import Setting
from handlers import register_handlers
from middlewares.auth import AuthMiddleware
from services.scheduler import setup_scheduler
from utils.time_utils import parse_cutoff

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def get_cutoff_from_db() -> tuple[int, int]:
    async with async_session_maker() as session:
        res = await session.execute(select(Setting).where(Setting.key == "cutoff_time"))
        setting = res.scalar_one_or_none()
        if setting:
            return parse_cutoff(setting.value)
    return parse_cutoff(settings.DEFAULT_CUTOFF_TIME)


async def main():
    storage = RedisStorage.from_url(settings.REDIS_URL)
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties())
    dp = Dispatcher(storage=storage)

    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    register_handlers(dp)

    from utils.commands import set_bot_commands
    await set_bot_commands(bot)

    cutoff_h, cutoff_m = await get_cutoff_from_db()
    setup_scheduler(bot, cutoff_h, cutoff_m)

    log.info("Бот запущен")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
