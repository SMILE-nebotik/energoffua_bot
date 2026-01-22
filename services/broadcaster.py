import logging
import asyncio
from aiogram import Bot
from sqlalchemy import select
from datetime import datetime
import pytz

import database.db as db
from database.models import User
from handlers.schedules import format_schedule_text
from regions.registry import get_region

logger = logging.getLogger(__name__)
KYIV_TZ = pytz.timezone('Europe/Kyiv')

async def notify_changes(bot: Bot, region_code: str, changed_groups: list[str]):
    """
    Розсилає повідомлення користувачам, чиї групи зазнали змін у графіку.
    """
    if not changed_groups:
        return

    reg_obj = get_region(region_code)
    if not reg_obj:
        logger.error(f"[Broadcaster] Регіон {region_code} не знайдено.")
        return

    # 1. Отримуємо актуальну дату для формування повідомлення
    today_str = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")

    # 2. Вибираємо користувачів з бази
    async with db.get_session() as session:
        # Шукаємо юзерів цього регіону, які підписані на змінені групи
        # і у яких НЕ вимкнені сповіщення ("off")
        stmt = select(User).where(
            User.region == region_code,
            User.group_number.in_(changed_groups),
            User.notification_mode != "off"
        )
        result = await session.execute(stmt)
        users = result.scalars().all()

    if not users:
        logger.info(f"[Broadcaster] Зміни є, але підписників у групах {changed_groups} немає.")
        return

    logger.info(f"[Broadcaster] Починаю розсилку для {len(users)} користувачів (Регіон: {region_code}).")

    # 3. Кешуємо графіки, щоб не робити запит в базу для кожного юзера
    # Словник: { "1.1": "Текст графіка...", "1.2": "Текст..." }
    schedules_cache = {}
    
    for group in changed_groups:
        data = await reg_obj.get_schedule(group, today_str)
        if data:
            schedules_cache[group] = format_schedule_text(data['hours'], data['updated_at'])

    # 4. Розсилка
    count_sent = 0
    for user in users:
        # Перевірка "Тихого режиму" (no_night)
        if user.notification_mode == "no_night":
            current_hour = datetime.now(KYIV_TZ).hour
            # Якщо зараз ніч (23:00 - 07:00), пропускаємо
            if current_hour >= 23 or current_hour < 7:
                continue

        text_schedule = schedules_cache.get(user.group_number)
        if not text_schedule:
            continue

        msg_text = (
            f"⚠️ **УВАГА! ЗМІНА ГРАФІКА!**\n"
            f"Область: {reg_obj.name}\n"
            f"Черга: {user.group_number}\n\n"
            f"{text_schedule}"
        )

        try:
            await bot.send_message(user.user_id, msg_text, parse_mode="Markdown")
            count_sent += 1
            # Пауза 0.05 сек, щоб не перевищити ліміти Telegram (30 повідомлень/сек)
            await asyncio.sleep(0.05)
        except Exception as e:
            # Часто буває, що юзер заблокував бота. Це не критична помилка.
            logger.warning(f"[Broadcaster] Не вдалося надіслати юзеру {user.user_id}: {e}")

    logger.info(f"[Broadcaster] Розсилку завершено. Успішно надіслано: {count_sent}/{len(users)}")