from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from sqlalchemy import update
import re

import database.db as db
from database.models import User
from regions.registry import get_region, get_all_regions_list
from handlers.states import UserSetup
from handlers.common import get_main_menu_keyboard

router = Router()

# --- РЕЄСТРАЦІЯ ---
@router.callback_query(F.data.startswith("region_"), UserSetup.choosing_region)
async def process_region_choice(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer() # <--- ДОДАНО
    region_code = callback.data.replace("region_", "")
    reg_obj = get_region(region_code)
    
    if not reg_obj:
        await callback.message.answer("Помилка регіону")
        return

    await state.update_data(region=region_code)
    
    builder = ReplyKeyboardBuilder()
    for g in reg_obj.get_groups():
        builder.add(types.KeyboardButton(text=g))
    builder.adjust(4)
    
    await callback.message.answer(
        f"📍 Ви обрали: {reg_obj.name}\nТепер оберіть вашу чергу:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.set_state(UserSetup.choosing_group)

@router.message(UserSetup.choosing_group)
async def process_group_choice(message: types.Message, state: FSMContext):
    await state.update_data(group=message.text)
    await message.answer(
        "✅ Прийнято! Введіть час для ранкового звіту (наприклад 08:00):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(UserSetup.choosing_time)

@router.message(UserSetup.choosing_time)
async def process_time_choice(message: types.Message, state: FSMContext):
    raw_input = message.text.strip()
    normalized = re.sub(r"[.,\s-]+", ":", raw_input)
    try:
        if ":" not in normalized: normalized += ":00"
        h, m = map(int, normalized.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59): raise ValueError
        final_time = f"{h:02d}:{m:02d}"
    except:
        await message.answer("❌ Невірний формат. Введіть наприклад 08:00")
        return

    data = await state.get_data()
    
    async with db.get_session() as session:
        new_user = User(
            user_id=message.from_user.id,
            username=message.from_user.full_name,
            region=data['region'],
            group_number=data['group'],
            alert_time=final_time
        )
        await session.merge(new_user)
        await session.commit()

    await message.answer(
        f"✅ Налаштування завершено!\nРегіон: {data['region']}\nЧерга: {data['group']}\nЧас: {final_time}",
        reply_markup=get_main_menu_keyboard()
    )
    await state.clear()

# --- НАЛАШТУВАННЯ ---
@router.callback_query(F.data == "open_settings")
async def open_settings_menu(callback: types.CallbackQuery):
    await callback.answer() # <--- ДОДАНО
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Завжди", callback_data="set_notify_always")
    builder.button(text="🌙 Тихий режим (23-07 off)", callback_data="set_notify_no_night")
    builder.button(text="🔕 Вимкнути сповіщення", callback_data="set_notify_off")
    builder.button(text="📝 Змінити дані (Реєстрація)", callback_data="reset_registration")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⚙️ **Налаштування**\nОберіть режим сповіщень або змініть дані про чергу:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("set_notify_"))
async def set_notification_mode(callback: types.CallbackQuery):
    await callback.answer() # <--- ДОДАНО
    mode = callback.data.replace("set_notify_", "")
    mode_names = {
        "always": "🔔 Всі сповіщення увімкнено.",
        "no_night": "🌙 Тихий режим (без сповіщень вночі).",
        "off": "🔕 Сповіщення вимкнено (тільки ручна перевірка)."
    }
    
    async with db.get_session() as session:
        stmt = update(User).where(User.user_id == callback.from_user.id).values(notification_mode=mode)
        await session.execute(stmt)
        await session.commit()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    
    await callback.message.edit_text(
        f"✅ Налаштування збережено!\n{mode_names.get(mode, mode)}",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "reset_registration")
async def reset_user_data(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    for reg in get_all_regions_list():
        callback_data = f"region_{reg.code}" if reg.is_active else "region_inactive"
        builder.button(text=reg.name, callback_data=callback_data)
    builder.adjust(1)
    
    await callback.message.answer(
        "🔄 **Починаємо спочатку!**\nОберіть вашу область:", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(UserSetup.choosing_region)