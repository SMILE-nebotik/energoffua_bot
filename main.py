import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Імпорти модулів проекту
from core.config import config
from core.logger import setup_logger
import database.db as db

# Імпорти хендлерів
from handlers import common, user_settings, schedules, admin

# Імпорти логіки регіонів та сервісів
from regions.registry import get_active_regions_list
from services.broadcaster import notify_changes
from services.checker import check_and_notify_upcoming_outages

# Ініціалізація логера перед усім іншим
setup_logger()
logger = logging.getLogger(__name__)

async def scheduled_updates(bot: Bot):
    logger.info("[Scheduler] Start scheduled data update...")
    
    # Отримуємо тільки активні регіони (де is_active=True)
    regions = get_active_regions_list()
    
    for region in regions:
        try:
            logger.info(f"[Scheduler] Updating region: {region.name}")
            
            # Запускаємо воркер регіону (Selenium/Request логіка)
            # Він повертає список груп, у яких змінився графік
            changed_groups = await region.update_data()
            
            if changed_groups:
                logger.info(f"[Scheduler] Changes detected in {region.code}: {changed_groups}")
                # Викликаємо сервіс розсилки
                await notify_changes(bot, region.code, changed_groups)
            else:
                logger.info(f"[Scheduler] No changes for {region.name}.")
                
        except Exception as e:
            logger.error(f"[Scheduler] Update failed for {region.code}: {e}", exc_info=True)

async def main():
    """
    Точка входу в програму.
    """
    # 1. Ініціалізація бази даних
    await db.init_db()
    logger.info("[Main] Database initialized.")

    # 2. Налаштування бота
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()

    # 3. Реєстрація роутерів (порядок має значення!)
    dp.include_router(admin.router)         # Адмінка
    dp.include_router(common.router)        # /start, загальні кнопки
    dp.include_router(user_settings.router) # Налаштування регіону/групи
    dp.include_router(schedules.router)     # Відображення графіків

    # 4. Налаштування планувальника (APScheduler)
    scheduler = AsyncIOScheduler()

    # ЗАДАЧА 1: Оновлення даних з сайтів (кожні 30 хвилин)
    # Cron trigger: запускати в 00 та 30 хвилин кожної години
    scheduler.add_job(scheduled_updates, 'cron', minute='0,30', args=[bot])

    # ЗАДАЧА 2: Перевірка наближення відключень (кожні 60 секунд)
    # Перевіряє, чи не буде вимкнення через 15 хв
    scheduler.add_job(check_and_notify_upcoming_outages, 'interval', seconds=60, args=[bot])

    scheduler.start()
    logger.info("[Main] Scheduler started.")

    # 5. Запуск Polling (отримання повідомлень від Telegram)
    # Видаляємо вебхук, щоб уникнути конфліктів, і починаємо слухати
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
        # Фікс для Windows пізніше нахуй знесу
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Main] Bot stopped manually.")