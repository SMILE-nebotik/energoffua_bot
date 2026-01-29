import logging
import asyncio
from aiogram import Bot
from sqlalchemy import select
from datetime import datetime, timedelta
import pytz

import database.db as db
from database.models import User
from handlers.schedules import format_day_block 
from regions.registry import get_region

logger = logging.getLogger(__name__)
KYIV_TZ = pytz.timezone('Europe/Kyiv')

async def notify_changes(bot: Bot, region_code: str, changed_groups: list[str]):
    if not changed_groups: return

    reg_obj = get_region(region_code)
    if not reg_obj: return

    # Отримуємо дати для перевірки
    now_dt = datetime.now(KYIV_TZ)
    today_str = now_dt.strftime("%Y-%m-%d")
    tomorrow_str = (now_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    async with db.get_session() as session:
        stmt = select(User).where(
            User.region == region_code,
            User.group_number.in_(changed_groups),
            User.notification_mode != "off"
        )
        result = await session.execute(stmt)
        users = result.scalars().all()

    if not users: return

    logger.info(f"[Broadcaster] Розсилка для {len(users)} юзерів ({region_code}).")


    schedules_cache = {}
    
    for group in changed_groups:
        # check for tomorrow and today
        data_tmr = await reg_obj.get_schedule(group, tomorrow_str)
        data_today = await reg_obj.get_schedule(group, today_str)

        msg_header = ""
        text_block = ""

        if data_tmr:
            # new schedule
            msg_header = f"📅 **З'ЯВИВСЯ ГРАФІК НА ЗАВТРА ({tomorrow_str})**"
            text_block = format_day_block(f"ЗАВТРА ({tomorrow_str})", data_tmr['hours'], data_tmr['updated_at'])
        elif data_today:
            # new schedule for today
            msg_header = "⚠️ **УВАГА! ЗМІНА ГРАФІКА!**"
            text_block = format_day_block(f"СЬОГОДНІ ({today_str})", data_today['hours'], data_today['updated_at'])
        else:
            continue
            
        schedules_cache[group] = (msg_header, text_block)

    count_sent = 0
    for user in users:
        if user.notification_mode == "no_night":
            current_hour = datetime.now(KYIV_TZ).hour
            if current_hour >= 23 or current_hour < 7:
                continue

        cache_item = schedules_cache.get(user.group_number)
        if not cache_item: continue
        
        header, body = cache_item

        msg_text = (
            f"{header}\n"
            f"📍 {reg_obj.name} | Черга {user.group_number}\n\n"
            f"{body}"
        )

        try:
            await bot.send_message(user.user_id, msg_text, parse_mode="Markdown")
            count_sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    logger.info(f"[Broadcaster] Надіслано: {count_sent}")