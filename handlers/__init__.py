from aiogram import Router
from . import common, user_settings, schedules, admin

main_router = Router()

main_router.include_router(common.router)
main_router.include_router(user_settings.router)
main_router.include_router(schedules.router)
main_router.include_router(admin.router)