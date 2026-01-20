import asyncio
import logging
from datetime import datetime, timedelta
import pytz

from middlewares import AntiFloodMiddleware
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import API_TOKEN, ADMIN_IDS
import database
import handlers
import services 


logging.basicConfig(level=logging.INFO)
KYIV_TZ = pytz.timezone('Europe/Kyiv')

# перевірка години
def is_night_time():
    hour = datetime.now(KYIV_TZ).hour
    return hour >= 23 or hour < 7

# Щоденний звіт
async def check_daily_alert(bot: Bot):
    now_kyiv = datetime.now(KYIV_TZ).strftime("%H:%M")
    today_str = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")
    
    users = await database.get_all_users_full()
    
    for user_id, group, alert_time, mode in users:
        if mode == 'off': continue
        
        if alert_time == now_kyiv:
            data = await database.get_schedule_for_group(today_str, group)
            if data:
                schedule, updated_at = data
                text = handlers.format_schedule_text(schedule, updated_at)
                try:
                    await bot.send_message(user_id, f"Ваш щоденний звіт ({group}):\n\n{text}")
                except Exception as e:
                    logging.error(f"Помилка відправки {user_id}: {e}")

# апдейт бази і сооб про зміни
async def scheduled_update_and_notify(bot: Bot):
    try:
        changed_groups = await services.update_schedule_database()
        
        if changed_groups is None:
            return

        if changed_groups:
            logging.info(f"Виявлено зміни в групах: {changed_groups}")
            today_str = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")
            
            users = await database.get_all_users_full()
            
            for user_id, group, _, mode in users:
                if group in changed_groups:
                    if mode == 'off': continue
                    if mode == 'no_night' and is_night_time(): continue
                    
                    data = await database.get_schedule_for_group(today_str, group)
                    if data:
                        schedule, updated_at = data
                        text = handlers.format_schedule_text(schedule, updated_at)
                        
                        try:
                            await bot.send_message(
                                user_id,
                                f"⚠️ **УВАГА! ГРАФІК ЗМІНЕНО!**\n"
                                f"Оновлені дані для черги {group}:\n\n{text}"
                            )
                        except Exception as e:
                            logging.error(f"Failed to notify change {user_id}: {e}")
                            
    except Exception as e:
        logging.error(f"Global update error: {e}")
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"\n помилка: {e}")
            except: pass


# попередження за 15 хвилин
async def check_upcoming_outages(bot: Bot):
    now_kyiv = datetime.now(KYIV_TZ)
    future_time = now_kyiv + timedelta(minutes=15)
    future_time_str = future_time.strftime("%H:%M")
    today_str = now_kyiv.strftime("%Y-%m-%d")
    
    hour = future_time.hour
    minute = future_time.minute
    cell_index = hour * 2 + (1 if minute >= 30 else 0)
    
    if cell_index > 47: return

    users = await database.get_all_users_full()
    
    for user_id, group, _, mode in users:
        if mode == 'off': continue
        if mode == 'no_night' and is_night_time(): continue

        data = await database.get_schedule_for_group(today_str, group)
        if data:
            schedule, _ = data
            if len(schedule) > cell_index:
                status_future = schedule[cell_index]
                status_now = 'on'
                if cell_index > 0: status_now = schedule[cell_index - 1]
                
                if status_future == 'off' and status_now == 'on':
                    if minute == 45 or minute == 15:
                        try:
                            await bot.send_message(
                                user_id, 
                                f"⚠️ **Увага!**\nЧерез 15 хвилин ({future_time_str}) планується відключення!"
                            )
                        except: pass

async def main():
    await database.create_table()
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    dp.message.middleware(AntiFloodMiddleware(time_limit=1)) # 1 секунда затримки
    dp.include_router(handlers.router)

    scheduler = AsyncIOScheduler(timezone=KYIV_TZ)

    scheduler.add_job(scheduled_update_and_notify, 'cron', minute='0,30', args=[bot])
    scheduler.add_job(check_upcoming_outages, 'cron', minute='*', args=[bot])
    scheduler.add_job(check_daily_alert, 'cron', minute='*', args=[bot])
    scheduler.add_job(services.backup_database, 'cron', hour=3, minute=0) # щоденний бекап о 3:00
    
    scheduler.start()
    
    print("start ex")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("bot stopped")