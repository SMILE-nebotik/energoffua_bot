import asyncio
import logging
from datetime import datetime, timedelta
import pytz # бібла для часових поясів

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import API_TOKEN
import database
import handlers
import services 

logging.basicConfig(level=logging.INFO)

# Київський час константа
KYIV_TZ = pytz.timezone('Europe/Kyiv')

# Функція 1: Перевірка "Будильника" (фіксований час юзера)
async def check_daily_alert(bot: Bot):
    now_kyiv = datetime.now(KYIV_TZ).strftime("%H:%M")
    today_str = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")
    
    users = await database.get_all_users()
    
    for user_id, group, alert_time in users:
        # Якщо час співпадає з тим, що виставив юзер
        if alert_time == now_kyiv:
            schedule = await database.get_schedule_for_group(today_str, group)
            if schedule:
                text = handlers.format_schedule_text(schedule)
                try:
                    await bot.send_message(user_id, f"Ваш щоденний звіт ({group}):\n\n{text}")
                except Exception as e:
                    logging.error(f"Помилка відправки {user_id}: {e}")

# Функція 2: Попередження за 15 хвилин до відключення
async def check_upcoming_outages(bot: Bot):
    # Беремо час, який буде через 15 хвилин
    now_kyiv = datetime.now(KYIV_TZ)
    future_time = now_kyiv + timedelta(minutes=15)
    
    future_time_str = future_time.strftime("%H:%M")
    today_str = now_kyiv.strftime("%Y-%m-%d")
    
    # Вираховуємо індекс клітинки (0-47) для цього майбутнього часу
    # година * 2 + (1 якщо хвилини >= 30)
    hour = future_time.hour
    minute = future_time.minute
    # Округлюємо до найближчого слота (00 або 30)
    cell_index = hour * 2 + (1 if minute >= 30 else 0)
    
    # Якщо вийшли за межі дня (наприклад 24:00), пропускаємо
    if cell_index > 47: return

    users = await database.get_all_users()
    
    for user_id, group, _ in users:
        schedule = await database.get_schedule_for_group(today_str, group)
        
        if schedule and len(schedule) > cell_index:
            # Логіка: Якщо ЗАРАЗ (cell_index - 1) світло Є, а ЧЕРЕЗ 15 хв (cell_index) буде OFF
            # Тобто попереджаємо про початок відключення
            status_future = schedule[cell_index]
            
            # Перевіряємо попередню клітинку, щоб не спамити, якщо воно ВЖЕ вимкнене
            status_now = 'on' # за замовчуванням
            if cell_index > 0:
                status_now = schedule[cell_index - 1]
            
            # Якщо світло зникне
            if status_future == 'off' and status_now == 'on':
                # Додаткова перевірка: чи це рівно за 15 хв?
                # Оскільки функція запускається щохвилини, треба перевірити хвилини
                # Якщо зараз 10:45, а відключення в 11:00 (xx:00), то ми пишемо.
                # Відключення бувають в :00 або :30.
                # Значить попереджаємо в :45 або :15.
                if minute == 45 or minute == 15:
                    try:
                        await bot.send_message(
                            user_id, 
                            f"⚠️ **Увага!**\nЧерез 15 хвилин ({future_time_str}) планується відключення світла!"
                        )
                    except Exception as e:
                        logging.error(f"Помилка 15хв {user_id}: {e}")


async def main():
    await database.create_table()
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    dp.include_router(handlers.router)

    # київський час завжди
    scheduler = AsyncIOScheduler(timezone=KYIV_TZ)

    # 1. Оновлення бази з сайту: кожну годину в 00 та 30 хвилин (раз в пів години)
    scheduler.add_job(services.update_schedule_database, 'cron', minute='0,30')
    
    # 2. Розсилка за часом користувача (щохвилини перевіряємо чи настав час)
    scheduler.add_job(check_daily_alert, 'cron', minute='*', args=[bot])
    
    # 3. Попередження за 15 хвилин (теж щохвилини чек)
    scheduler.add_job(check_upcoming_outages, 'cron', minute='*', args=[bot])
    
    scheduler.start()

    print("Запуск бота попитка оновити дан.")
    # Примусове оновлення при старті (можна закоментувати при відладці)
    await services.update_schedule_database()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинений")