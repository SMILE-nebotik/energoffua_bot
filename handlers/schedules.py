import logging
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import pytz

import database.db as db
from database.models import User
from regions.registry import get_region
from handlers.common import get_main_menu_keyboard

router = Router()
KYIV_TZ = pytz.timezone('Europe/Kyiv')

logger = logging.getLogger(__name__)

def format_day_block(date_title, schedule_list, update_time=None):
    if not schedule_list:
        return f"📅 {date_title}\n⚪ Дані відсутні.\n"
    
    off_slots = schedule_list.count('off')
    total_off_hours = off_slots * 0.5
    if total_off_hours.is_integer(): total_off_hours = int(total_off_hours)
    
    timeline_chars = []
    for i in range(0, 48, 2):
        s1 = schedule_list[i]
        s2 = schedule_list[i+1] if i+1 < 48 else 'on'
        
        if s1 == 'off' and s2 == 'off':
            timeline_chars.append("🟥")
        elif s1 == 'on' and s2 == 'on':
            timeline_chars.append("🟩")
        else:
            timeline_chars.append("🟧")
            
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
         
    if not intervals:
        intervals_text = "🎉 Світло має бути весь день!"
    else:
        intervals_text = "\n".join(intervals)
    
    text = (
        f"📅 {date_title}\n"
        f"{timeline_visual}\n"
        f"`00..04..08..12..16..20..24`\n\n"
        f"{intervals_text}\n\n"
        f"📊 Всього без світла: {total_off_hours} год."
    )
    
    if update_time: 
        text += f"\n🕒 Оновлено на сайті: {update_time}"
        
    return text

async def send_schedule(message, user_id, group, region_code, is_edit=False, is_personal=True):
    reg_obj = get_region(region_code)
    if not reg_obj:
        await message.answer("⚠️ Помилка: Регіон не підтримується.")
        return

    now_kyiv = datetime.now(KYIV_TZ)
    today_str = now_kyiv.strftime("%Y-%m-%d")
    tomorrow_str = (now_kyiv + timedelta(days=1)).strftime("%Y-%m-%d")

    header = f"📍 {reg_obj.name} | Черга {group}\n\n"
    body = ""

    # Блок СЬОГОДНІ
    data_today = await reg_obj.get_schedule(group, today_str)
    if data_today:
        body += format_day_block(f"СЬОГОДНІ ({today_str})", data_today['hours'], data_today['updated_at'])
    else:
        body += f"📅 СЬОГОДНІ ({today_str})\n⚪ Даних ще немає.\n"

    # Блок ЗАВТРА (якщо є)
    data_tomorrow = await reg_obj.get_schedule(group, tomorrow_str)
    if data_tomorrow:
        body += "\n\n" + format_day_block(f"ЗАВТРА ({tomorrow_str})", data_tomorrow['hours'], data_tomorrow['updated_at'])

    full_text = header + body

    # Кнопки
    builder = InlineKeyboardBuilder()
    refresh_callback = "show_my_graph" if is_personal else f"check_group_{group}"
    
    builder.button(text="🔄 Оновити", callback_data=refresh_callback)
    
    if is_personal:
        builder.button(text="🔙 Меню", callback_data="back_to_menu")
    else:
        builder.button(text="🔙 Меню", callback_data="back_to_menu")

    try:
        if is_edit:
            await message.edit_text(full_text, parse_mode="Markdown", reply_markup=builder.as_markup())
        else:
            await message.answer(full_text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except Exception as e:
        if "message is not modified" not in str(e):
            logger.error(f"Send error: {e}")
            await message.answer(full_text.replace("`", ""), reply_markup=builder.as_markup())

@router.callback_query(F.data == "show_my_graph")
async def show_my_graph(callback: types.CallbackQuery):
    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user or not user.region:
            await callback.message.answer("⚠️ Спочатку оберіть область.")
            return
        await send_schedule(callback.message, user.user_id, user.group_number, user.region, is_edit=True, is_personal=True)
    await callback.answer()

@router.callback_query(F.data == "check_other_menu")
async def check_other_menu_handler(callback: types.CallbackQuery):
    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user: 
            await callback.message.answer("Спочатку /start")
            return
        reg_obj = get_region(user.region)
        if not reg_obj: return
        
        builder = InlineKeyboardBuilder()
        for g in reg_obj.get_groups():
            builder.button(text=g, callback_data=f"check_group_{g}")
        builder.adjust(4)
        builder.row(types.InlineKeyboardButton(text="🔙 Меню", callback_data="back_to_menu"))
        
        await callback.message.edit_text(f"🔎 **Перевірка іншої черги** ({reg_obj.name})", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("check_group_"))
async def show_specific_group(callback: types.CallbackQuery):
    group = callback.data.replace("check_group_", "")
    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user: return
        await send_schedule(callback.message, user.user_id, group, user.region, is_edit=True, is_personal=False)
    await callback.answer()