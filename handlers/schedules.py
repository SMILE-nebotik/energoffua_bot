import logging
import json
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import pytz
from sqlalchemy import select

import database.db as db
from database.models import User, Schedule
from regions.registry import get_region

router = Router()
KYIV_TZ = pytz.timezone('Europe/Kyiv')
logger = logging.getLogger(__name__)

def format_day_block(date_title, schedule_list, update_time=None):
    """
    Старий добрий візуал: шкала 48 символів, розрахунок годин та інтервали.
    """
    if not schedule_list:
        return f"📅 {date_title}\n⚪ Дані відсутні.\n"
    
    # Якщо прийшло 24 години (новий формат), розширюємо до 48 для сумісності з візуалом
    if len(schedule_list) == 24:
        extended_list = []
        for status in schedule_list:
            extended_list.extend([status, status])
        schedule_list = extended_list

    off_slots = schedule_list.count('off')
    total_off_hours = off_slots * 0.5
    if total_off_hours.is_integer(): total_off_hours = int(total_off_hours)
    
    timeline_chars = []
    for i in range(0, 48, 2):
        s1 = schedule_list[i]
        s2 = schedule_list[i+1] if i+1 < 48 else 'on'
        
        if s1 == 'off' and s2 == 'off': timeline_chars.append("🟥")
        elif s1 == 'on' and s2 == 'on': timeline_chars.append("🟩")
        else: timeline_chars.append("🟧")
            
    timeline_visual = "".join(timeline_chars)

    intervals = []
    start_index = None
    for i, status in enumerate(schedule_list):
        if status == 'off':
            if start_index is None: start_index = i
        else:
            if start_index is not None:
                s_h, s_m = start_index // 2, "00" if start_index % 2 == 0 else "30"
                e_h, e_m = i // 2, "00" if i % 2 == 0 else "30"
                intervals.append(f"🕰 {int(s_h):02d}:{s_m} - {int(e_h):02d}:{e_m}")
                start_index = None
                
    if start_index is not None:
         s_h, s_m = start_index // 2, "00" if start_index % 2 == 0 else "30"
         intervals.append(f"🕰 {int(s_h):02d}:{s_m} - 24:00")
         
    intervals_text = "\n".join(intervals) if intervals else "🎉 Світло має бути весь день!"
    
    text = (
        f"📅 {date_title}\n"
        f"{timeline_visual}\n"
        f"`00..04..08..12..16..20..24`\n\n"
        f"{intervals_text}\n\n"
        f"📊 Всього без світла: {total_off_hours} год."
    )
    if update_time: 
        text += f"\n🕒 Оновлено: {update_time}"
    return text

async def send_schedule(message, user_id, group, region_code, is_edit=False, is_personal=True):
    # Нормалізація назви регіону для пошуку в БД
    db_region = region_code.replace("Львівська область", "lviv").replace("Волинська область", "volyn")
    reg_obj = get_region(db_region)
    
    if not reg_obj:
        await message.answer("⚠️ Помилка: Регіон не знайдено.")
        return

    now_kyiv = datetime.now(KYIV_TZ)
    today_str = now_kyiv.strftime("%Y-%m-%d")
    tomorrow_str = (now_kyiv + timedelta(days=1)).strftime("%Y-%m-%d")

    header = f"📍 {reg_obj.name} | Черга {group}\n\n"
    body = ""

    async with db.get_session() as session:
        # СЬОГОДНІ
        stmt_t = select(Schedule).where(Schedule.region == db_region, Schedule.group_code == group, Schedule.date == today_str)
        res_t = await session.execute(stmt_t)
        rec_t = res_t.scalar_one_or_none()
        if rec_t:
            body += format_day_block(f"СЬОГОДНІ ({today_str})", json.loads(rec_t.hours_data), rec_t.site_updated_at)
        else:
            body += f"📅 СЬОГОДНІ ({today_str})\n⚪ Даних ще немає.\n"

        # ЗАВТРА
        stmt_tm = select(Schedule).where(Schedule.region == db_region, Schedule.group_code == group, Schedule.date == tomorrow_str)
        res_tm = await session.execute(stmt_tm)
        rec_tm = res_tm.scalar_one_or_none()
        if rec_tm:
            body += "\n\n" + format_day_block(f"ЗАВТРА ({tomorrow_str})", json.loads(rec_tm.hours_data), rec_tm.site_updated_at)

    full_text = header + body
    builder = InlineKeyboardBuilder()
    refresh_cb = "show_my_graph" if is_personal else f"check_group_{group}"
    builder.button(text="🔄 Оновлюємо", callback_data=refresh_cb)
    builder.button(text="🔙 Меню", callback_data="back_to_menu")
    builder.adjust(1)

    try:
        if is_edit:
            await message.edit_text(full_text, parse_mode="Markdown", reply_markup=builder.as_markup())
        else:
            await message.answer(full_text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"Send error: {e}")

@router.callback_query(F.data == "show_my_graph")
async def show_my_graph(callback: types.CallbackQuery):
    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user or not user.region:
            await callback.answer("⚠️ Оберіть область", show_alert=True)
            return
        await send_schedule(callback.message, user.user_id, user.group_number, user.region, is_edit=True, is_personal=True)
    await callback.answer()

@router.callback_query(F.data == "check_other_menu")
async def check_other_menu_handler(callback: types.CallbackQuery):
    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user: return
        reg_obj = get_region(user.region.replace("Львівська область", "lviv").replace("Волинська область", "volyn"))
        
        builder = InlineKeyboardBuilder()
        for g in reg_obj.get_groups():
            builder.button(text=g, callback_data=f"check_group_{g}")
        builder.adjust(4)
        builder.row(types.InlineKeyboardButton(text="🔙 Меню", callback_data="back_to_menu"))
        await callback.message.edit_text(f"🔎 **Інша черга** ({reg_obj.name})", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("check_group_"))
async def show_specific_group(callback: types.CallbackQuery):
    group = callback.data.replace("check_group_", "")
    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        if user:
            await send_schedule(callback.message, user.user_id, group, user.region, is_edit=True, is_personal=False)
    await callback.answer()