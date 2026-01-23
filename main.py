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

from handlers import common, user_settings, schedules, admin
from regions.registry import get_active_regions_list
from services.broadcaster import notify_changes
from services.checker import check_and_notify_upcoming_outages
from middlewares.throttling import ThrottlingMiddleware
from services.backup import backup_database
from services.monitoring import system_health_check

setup_logger()
logger = logging.getLogger(__name__)

# cehck root in bot
def check_security():
    if hasattr(os, 'getuid'):
        if os.getuid() == 0:
            logger.warning("[Security] Bot is running as ROOT! It is recommended to run as a standard user.")

async def scheduled_updates(bot: Bot):
    logger.info("[Scheduler] Start scheduled data update...")
    regions = get_active_regions_list()
    for region in regions:
        try:
            logger.info(f"[Scheduler] Updating region: {region.name}")
            changed_groups = await region.update_data()
            if changed_groups:
                logger.info(f"[Scheduler] Changes detected in {region.code}: {changed_groups}")
                await notify_changes(bot, region.code, changed_groups)
            else:
                logger.info(f"[Scheduler] No changes for {region.name}.")
        except Exception as e:
            logger.error(f"[Scheduler] Update failed for {region.code}: {e}", exc_info=True)

async def main():
    check_security()
    
    await db.init_db()
    logger.info("[Main] Database initialized.")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()

    # connect throttling middleware
    dp.message.middleware(ThrottlingMiddleware(rate_limit=1.0))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=1.0))

    # register routers
    dp.include_router(admin.router)
    dp.include_router(common.router)
    dp.include_router(user_settings.router)
    dp.include_router(schedules.router)

    scheduler = AsyncIOScheduler()

    # cehck awery 30 minutes for updates
    scheduler.add_job(scheduled_updates, 'cron', minute='0,30', args=[bot])
    
    # cehck every minute for upcoming outages
    scheduler.add_job(check_and_notify_upcoming_outages, 'interval', seconds=60, args=[bot])
    
    # monitoring system health every hour
    scheduler.add_job(system_health_check, 'interval', minutes=60, args=[bot])
    
    # backup database every day at 3:00 AM
    scheduler.add_job(backup_database, 'cron', hour=3, minute=0)

    scheduler.start()
    logger.info("[Main] Scheduler started.")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("[Main] Bot started polling.")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"[Main] Polling error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Main] Bot stopped manually.")