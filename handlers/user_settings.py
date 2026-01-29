from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from sqlalchemy import update

import database.db as db
from database.models import User
from regions.registry import get_region, get_all_regions_list
from handlers.states import UserSetup
from handlers.common import get_main_menu_keyboard

router = Router()

# --- КРОК 1: Вибір області ---
@router.callback_query(F.data.startswith("region_"), UserSetup.choosing_region)
async def process_region_choice(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    region_code = callback.data.replace("region_", "")
    
    reg_obj = get_region(region_code)
    if not reg_obj:
        await callback.message.answer("❌ Помилка: Регіон не знайдено.")
        return

    # Зберігаємо код регіону
    await state.update_data(region=region_code)
    
    # Генеруємо кнопки черг для цього регіону
    builder = ReplyKeyboardBuilder()
    for g in reg_obj.get_groups():
        builder.add(types.KeyboardButton(text=g))
    builder.adjust(4) # По 4 в ряд
    
    await callback.message.answer(
        f"📍 Область: **{reg_obj.name}**\n👇 Оберіть вашу чергу:",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="Markdown"
    )
    await state.set_state(UserSetup.choosing_group)

# --- КРОК 2: Вибір групи та збереження (ТУТ ФІКС) ---
@router.message(UserSetup.choosing_group)
async def process_group_choice(message: types.Message, state: FSMContext):
    group = message.text.strip()
    data = await state.get_data()
    region_code = data.get("region", "volyn")
    
    reg_obj = get_region(region_code)
    
    # Валідація: чи є така група в цьому регіоні?
    if reg_obj and group not in reg_obj.get_groups():
        await message.answer("⚠️ Такої черги немає. Оберіть кнопку знизу.")
        return

    # === ФІКС: ПРИБИРАЄМО КЛАВІАТУРУ ===
    # Відправляємо пусте повідомлення з командою видалення кнопок
    loading_msg = await message.answer("⏳", reply_markup=types.ReplyKeyboardRemove())
    
    # Зберігаємо в базу
    async with db.get_session() as session:
        new_user = User(
            user_id=message.from_user.id,
            username=message.from_user.full_name,
            region=region_code,
            group_number=group,
            alert_time="00:00"
        )
        await session.merge(new_user)
        await session.commit()

    # Видаляємо повідомлення "⏳", щоб не смітити в чаті
    try:
        await loading_msg.delete()
    except:
        pass

    # ВІДПОВІДЬ ПІСЛЯ РЕЄСТРАЦІЇ (Шаблон з роботом)
    await message.answer(
        f"🤖 **Головне меню**\n"
        f"Обрана: **{reg_obj.name}**\n"
        f"Черга: **{group}**",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
    await state.clear()

# --- МЕНЮ НАЛАШТУВАНЬ ---
@router.callback_query(F.data == "open_settings")
async def open_settings_menu(callback: types.CallbackQuery):
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Сповіщати завжди", callback_data="set_notify_always")
    builder.button(text="🌙 Тихий режим", callback_data="set_notify_no_night")
    builder.button(text="🔕 Не сповіщати", callback_data="set_notify_off")
    builder.button(text="📝 Змінити дані", callback_data="reset_registration")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⚙️ **Налаштування**",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("set_notify_"))
async def set_notification_mode(callback: types.CallbackQuery):
    mode = callback.data.replace("set_notify_", "")
    
    async with db.get_session() as session:
        stmt = update(User).where(User.user_id == callback.from_user.id).values(notification_mode=mode)
        await session.execute(stmt)
        await session.commit()
    
    msg_map = {
        "always": "🔔 Завжди",
        "no_night": "🌙 Тихий",
        "off": "🔕 Вимкнено"
    }
    await callback.answer(msg_map.get(mode))
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    
    await callback.message.edit_text(
        f"✅ Налаштування оновлено: {msg_map.get(mode)}",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "reset_registration")
async def reset_user_data(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    for reg in get_all_regions_list():
        callback_data = f"region_{reg.code}" if reg.is_active else "region_inactive"
        builder.button(text=reg.name, callback_data=callback_data)
    builder.adjust(1)
    
    await callback.message.edit_text(
        "🔄 **Зміна даних**\nОберіть нову область:", 
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await state.set_state(UserSetup.choosing_region)