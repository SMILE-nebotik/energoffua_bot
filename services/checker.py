# delete this later
import logging
import asyncio
from datetime import datetime, timedelta
import pytz
from aiogram import Bot
from sqlalchemy import select

import database.db as db
from database.models import User, Schedule
from regions.registry import get_region

logger = logging.getLogger(__name__)
KYIV_TZ = pytz.timezone('Europe/Kyiv')

async def check_and_notify_upcoming_outages(bot: Bot):
    """Перевіряє, чи буде відключення через 15-20 хвилин"""
    now = datetime.now(KYIV_TZ)

    if now.minute not in [14, 44]:
        return
    # Дивимось на 15 хвилин вперед
    check_time = now + timedelta(minutes=15)
    
    # Визначаємо індекс у масиві (48 слотів по 30 хв)
    # 00:00 -> індекс 0, 00:30 -> індекс 1, і т.д.
    current_slot_idx = now.hour * 2 + (1 if now.minute >= 30 else 0)
    next_slot_idx = check_time.hour * 2 + (1 if check_time.minute >= 30 else 0)

    # Якщо статус не змінився (було ON і залишилося ON), то нічого не робимо.
    # Нас цікавить тільки перехід ON -> OFF
    if current_slot_idx == next_slot_idx:
        return 

    async with db.get_session() as session:
        # Беремо всіх активних юзерів
        result = await session.execute(select(User).where(User.notification_mode != "off"))
        users = result.scalars().all()

        for user in users:
            # Перевірка режиму тиші
            if user.notification_mode == "no_night":
                if 23 <= now.hour or now.hour < 7:
                    continue

            # Отримуємо графік для цього юзера
            reg_obj = get_region(user.region)
            if not reg_obj: continue
            
            today_str = now.strftime("%Y-%m-%d")
            sched_data = await reg_obj.get_schedule(user.group_number, today_str)
            
            if not sched_data: continue
            
            hours = sched_data['hours']
            
            # Логіка: зараз 'on', а в наступному слоті 'off'
            if hours[current_slot_idx] == 'on' and hours[next_slot_idx] == 'off':
                try:
                    await bot.send_message(
                        user.user_id,
                        f"🔌 **Попередження!**\nЧерез ~15 хвилин за вашим графіком ({user.group_number}) планується **відключення** світла."
                    )
                    await asyncio.sleep(0.05) # Захист від спаму
                except Exception as e:
                    logger.error(f"Error sending reminder to {user.user_id}: {e}")