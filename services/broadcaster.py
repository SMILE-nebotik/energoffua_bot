import logging
import asyncio
from aiogram import Bot
from sqlalchemy import select
from datetime import datetime
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

    today_str = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")

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
        data = await reg_obj.get_schedule(group, today_str)
        if data:
            block = format_day_block(f"СЬОГОДНІ ({today_str})", data['hours'], data['updated_at'])
            schedules_cache[group] = block

    count_sent = 0
    for user in users:
        if user.notification_mode == "no_night":
            current_hour = datetime.now(KYIV_TZ).hour
            if current_hour >= 23 or current_hour < 7:
                continue

        text_block = schedules_cache.get(user.group_number)
        if not text_block: continue

        msg_text = (
            f"⚠️ **УВАГА! ЗМІНА ГРАФІКА!**\n"
            f"📍 {reg_obj.name} | Черга {user.group_number}\n\n"
            f"{text_block}"
        )

        try:
            await bot.send_message(user.user_id, msg_text, parse_mode="Markdown")
            count_sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    logger.info(f"[Broadcaster] Надіслано: {count_sent}")