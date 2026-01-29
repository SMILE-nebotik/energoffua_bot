import asyncio
import logging
import sys
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import config
from core.logger import setup_logger
import database.db as db

from handlers import admin, schedules, user_settings, common
from regions.registry import get_active_regions_list
from services.broadcaster import notify_changes
from services.checker import check_and_notify_upcoming_outages
from middlewares.throttling import ThrottlingMiddleware
from services.backup import backup_database
from services.monitoring import system_health_check
from core.browser import kill_zombie_processes, clean_temp_files

setup_logger()
logger = logging.getLogger(__name__)

async def scheduled_updates(bot: Bot):
    """Оновлення даних для всіх регіонів послідовно."""
    logger.info("[Scheduler] Початок планового оновлення...")
    regions = get_active_regions_list()
    
    for region in regions:
        kill_zombie_processes()
        clean_temp_files()
        try:
            logger.info(f"[Scheduler] Оновлюю: {region.name}")
            changed_groups = await region.update_data()
            if changed_groups:
                logger.info(f"[Scheduler] Зміни в {region.code}: {changed_groups}")
                await notify_changes(bot, region.code, changed_groups)
        except Exception as e:
            logger.error(f"[Scheduler] Помилка в {region.name}: {e}")
        await asyncio.sleep(2)
    
    kill_zombie_processes()
    logger.info("[Scheduler] Всі регіони оброблено.")

async def main():
    await db.init_db()
    logger.info("[Main] База даних ініціалізована.")

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()

    # Мідлварі
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=0.5))

    # ПРАВИЛЬНИЙ порядок роутерів
    dp.include_router(admin.router)
    dp.include_router(schedules.router)
    dp.include_router(user_settings.router)
    dp.include_router(common.router)

    # Шедулер
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_updates, 'cron', minute='0,30', args=[bot])
    scheduler.add_job(check_and_notify_upcoming_outages, 'interval', seconds=60, args=[bot])
    scheduler.add_job(system_health_check, 'interval', minutes=60, args=[bot])
    scheduler.add_job(backup_database, 'cron', hour=3, minute=0)
    
    scheduler.start()
    logger.info("[Main] Шедулер запущено.")

    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск оновлення при старті
    asyncio.create_task(scheduled_updates(bot))

    logger.info("[Main] Бот почав опитування.")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"[Main] Помилка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Main] Бот зупинений.")