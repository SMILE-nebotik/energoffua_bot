import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import API_TOKEN
import database
import handlers
import services 

logging.basicConfig(level=logging.INFO)

async def check_and_send_mailing(bot: Bot):

    now = datetime.now().strftime("%H:%M")
    users = await database.get_all_users()
    today = datetime.now().strftime("%Y-%m-%d")
    
    for user_id, group, alert_time in users:
        if alert_time == now:
            # тримання з бази графіку
            schedule = await database.get_schedule_for_group(today, group)
            
            # оновлення якщо пусто
            if not schedule:
                print(f"Для {user_id} немає даних в базі. Оновлюю...")
                await services.update_schedule_database()
                schedule = await database.get_schedule_for_group(today, group)
            
            if schedule:
                text = handlers.format_schedule_text(schedule)
                try:
                    await bot.send_message(user_id, f"Попередження графік для {group}:\n\n{text}")
                except Exception as e:
                    logging.error(f"Не вдалося надіслати повідомлення: {e}")

async def main():
    await database.create_table()
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    dp.include_router(handlers.router)

    scheduler = AsyncIOScheduler()
    

    # оновлення бази кожну годину в 15 по
    scheduler.add_job(services.update_schedule_database, 'cron', minute=15)
    
    # чек розсилки
    scheduler.add_job(check_and_send_mailing, 'cron', minute='*', args=[bot])
    
    scheduler.start()

    print("Запуск бота попитка оновити дан.")
    await services.update_schedule_database()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинений")