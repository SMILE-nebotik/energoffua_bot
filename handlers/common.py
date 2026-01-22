from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database.db as db
from database.models import User
from regions.registry import get_all_regions_list, get_region
from handlers.states import UserSetup

router = Router()

def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📅 Мій графік", callback_data="show_my_graph"),
        types.InlineKeyboardButton(text="🔍 Інша черга", callback_data="check_other_menu")
    )
    builder.row(
        types.InlineKeyboardButton(text="⚙️ Налаштування", callback_data="open_settings")
    )
    return builder.as_markup()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    async with db.get_session() as session:
        user = await session.get(User, message.from_user.id)
        
        if user:
            region_name = "Невідомо"
            reg_obj = get_region(user.region)
            if reg_obj:
                region_name = reg_obj.name
                
            await message.answer(
                f"👋 Привіт! Ваш регіон: **{region_name}**, черга: **{user.group_number}**.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown"
            )
        else:
            builder = InlineKeyboardBuilder()
            for reg in get_all_regions_list():
                callback = f"region_{reg.code}"
                if not reg.is_active:
                    callback = "region_inactive"
                builder.button(text=reg.name, callback_data=callback)
            builder.adjust(1)
            
            await message.answer("🇺🇦 Оберіть вашу область:", reply_markup=builder.as_markup())
            await state.set_state(UserSetup.choosing_region)

@router.callback_query(F.data == "region_inactive")
async def inactive_alert(callback: types.CallbackQuery):
    await callback.answer("🚧 В розробці. Оберіть іншу.", show_alert=True)

@router.callback_query(F.data == "back_to_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.answer() # <--- ДОДАНО: Миттєва реакція
    await callback.message.edit_text("🤖 Головне меню", reply_markup=get_main_menu_keyboard())