import asyncio
import logging
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.checker import check_and_notify_upcoming_outages

# Імпорти наших модулів
from core.config import config
import database.db as db
from handlers import main_router
from regions.registry import get_active_regions_list

# Налаштування логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

async def scheduled_updates():
    """Ця функція запускається планувальником"""
    logging.info("⏰ Початок планового оновлення даних...")
    
    for region in get_active_regions_list():
        try:
            logging.info(f"🔄 Оновлення регіону: {region.name}")
            changes = await region.update_data()
            if changes:
                logging.info(f"📢 Знайдено зміни в {region.code}: {changes}")
                # Тут пізніше додамо services.broadcaster.notify_users(region.code, changes)
        except Exception as e:
            logging.error(f"❌ Помилка оновлення {region.code}: {e}")

async def main():
    # 1. Ініціалізація БД
    await db.init_db()
    logging.info("база даних ініціалізована")

    # 2. Бот і Диспетчер
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(main_router)

    # 3. Планувальник
    scheduler = AsyncIOScheduler()
    # Оновлюємо дані кожні 30 хвилин (або як налаштуєш)
    scheduler.add_job(scheduled_updates, 'cron', minute='0,30')
    # ПЕРЕВІРКА ВІДКЛЮЧЕНЬ (кожної хвилини)
    scheduler.add_job(check_and_notify_upcoming_outages, 'interval', minutes=1, args=[bot])
    scheduler.start()

    # 4. Запуск
    logging.info("бот стартанув")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("бот стопнутий вручну")