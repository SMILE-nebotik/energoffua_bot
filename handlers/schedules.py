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

# Налаштуємо логгер для цього файлу
logger = logging.getLogger(__name__)

def format_schedule_text(schedule_list, update_time=None):
    if not schedule_list: return "Дані відсутні."
    off_slots = schedule_list.count('off')
    total_off_hours = off_slots * 0.5
    if total_off_hours.is_integer(): total_off_hours = int(total_off_hours)
    
    timeline = ""
    for i in range(0, 48, 2):
        s1 = schedule_list[i]
        s2 = schedule_list[i+1] if i+1 < 48 else 'on'
        timeline += "🟥" if s1 == 'off' or s2 == 'off' else "🟩"
    
    timeline_legend = "`00..04..08..12..16..20..24`"
    
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
    
    text = f"{timeline}\n{timeline_legend}\n\n{intervals_text}\n\n📊 **Всього без світла:** {total_off_hours} год."
    if update_time: text += f"\n🕒 Оновлено на сайті: {update_time}"
    return text

async def send_schedule(message, user_id, group, region_code, is_edit=False, is_personal=True):
    logger.info(f"📤 Відправка графіка: User={user_id}, Group={group}, Region={region_code}")
    
    reg_obj = get_region(region_code)
    if not reg_obj:
        logger.error(f"❌ Регіон {region_code} не знайдено в реєстрі!")
        await message.answer("⚠️ Помилка: Регіон не підтримується.")
        return

    now_kyiv = datetime.now(KYIV_TZ)
    today_str = now_kyiv.strftime("%Y-%m-%d")
    tomorrow_str = (now_kyiv + timedelta(days=1)).strftime("%Y-%m-%d")

    data_today = await reg_obj.get_schedule(group, today_str)
    
    response = f"📍 **{reg_obj.name}** | Черга **{group}**\n\n"
    
    if data_today:
        response += f"📅 **СЬОГОДНІ ({today_str})**\n"
        response += format_schedule_text(data_today['hours'], data_today['updated_at'])
        response += "\n\n"
    else:
        response += f"📅 **СЬОГОДНІ ({today_str})**\nДаних ще немає.\n\n"

    data_tomorrow = await reg_obj.get_schedule(group, tomorrow_str)
    if data_tomorrow:
        response += f"📅 **ЗАВТРА ({tomorrow_str})**\n"
        response += format_schedule_text(data_tomorrow['hours'], data_tomorrow['updated_at'])

    builder = InlineKeyboardBuilder()
    refresh_callback = "show_my_graph" if is_personal else f"check_group_{group}"
    
    builder.button(text="🔄 Оновити", callback_data=refresh_callback)
    
    if is_personal:
        builder.button(text="🔙 Меню", callback_data="back_to_menu")
    else:
        builder.button(text="🔙 До списку", callback_data="check_other_menu")

    if is_edit:
        try:
            await message.edit_text(response, parse_mode="Markdown", reply_markup=builder.as_markup())
        except Exception as e:
            logger.warning(f"⚠️ Не вдалося відредагувати повідомлення (можливо текст той самий): {e}")
            # Якщо не вийшло редагувати, відправимо нове (іноді краще так)
            # await message.answer(response, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        await message.answer(response, parse_mode="Markdown", reply_markup=builder.as_markup())

# --- ОБРОБКА КНОПКИ "Мій графік" ---
@router.callback_query(F.data == "show_my_graph")
async def show_my_graph(callback: types.CallbackQuery):
    await callback.answer()
    logger.info(f"🖱 Натиснуто 'Мій графік' користувачем {callback.from_user.id}")
    
    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        
        if not user:
            logger.warning(f"❌ Користувача {callback.from_user.id} немає в базі!")
            await callback.message.answer("⚠️ Ваші дані не знайдено. Натисніть /start")
            return
            
        if not user.region:
            logger.warning(f"❌ У користувача {callback.from_user.id} немає регіону!")
            await callback.message.answer("⚠️ Регіон не налаштовано. Оберіть 'Змінити дані' в налаштуваннях.")
            return

        await send_schedule(callback.message, user.user_id, user.group_number, user.region, is_edit=True, is_personal=True)

# --- МЕНЮ ВИБОРУ ІНШОЇ ГРУПИ ---
@router.callback_query(F.data == "check_other_menu")
async def check_other_menu_handler(callback: types.CallbackQuery):
    await callback.answer()
    logger.info(f"🖱 Натиснуто 'Інша черга' користувачем {callback.from_user.id}")

    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user: 
            await callback.message.answer("Спочатку /start")
            return
        
        reg_obj = get_region(user.region)
        if not reg_obj:
            logger.error(f"❌ Регіон {user.region} не знайдено!")
            await callback.message.answer("Помилка регіону")
            return
        
        builder = InlineKeyboardBuilder()
        for g in reg_obj.get_groups():
            builder.button(text=g, callback_data=f"check_group_{g}")
        builder.adjust(4)
        builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
        
        await callback.message.edit_text(
            f"🔎 **Перевірка іншої черги** ({reg_obj.name})\nОберіть групу:",
            reply_markup=builder.as_markup()
        )

# --- ПОКАЗ ІНШОЇ ГРУПИ ---
@router.callback_query(F.data.startswith("check_group_"))
async def show_specific_group(callback: types.CallbackQuery):
    await callback.answer()
    group = callback.data.replace("check_group_", "")
    logger.info(f"🖱 Перегляд іншої групи: {group}")
    
    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user: return

        await send_schedule(callback.message, user.user_id, group, user.region, is_edit=True, is_personal=False)