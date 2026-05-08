from aiogram import Dispatcher
from .employee import router as employee_router
from .restaurant_admin import router as restaurant_router
from .super_admin import router as super_admin_router


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(super_admin_router)
    dp.include_router(restaurant_router)
    dp.include_router(employee_router)
