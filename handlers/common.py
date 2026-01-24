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
    builder.row(types.InlineKeyboardButton(text="⚡ Мій графік", callback_data="show_my_graph"))
    builder.row(
        types.InlineKeyboardButton(text="🔍 Інша черга", callback_data="check_other_menu"),
        types.InlineKeyboardButton(text="⚙️ Налаштування", callback_data="open_settings")
    )
    return builder.as_markup()

def get_menu_text(region_name, group_number):
    return (
        f"🤖 **Головне меню**\n"
        f"Обрана: **{region_name}**\n"
        f"Черга: **{group_number}**"
    )

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    async with db.get_session() as session:
        user = await session.get(User, message.from_user.id)
        
        if user:
            region_name = "Невідомо"
            reg_obj = get_region(user.region)
            if reg_obj: region_name = reg_obj.name
            
            await message.answer(
                get_menu_text(region_name, user.group_number),
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown"
            )
        else:
            builder = InlineKeyboardBuilder()
            for reg in get_all_regions_list():
                cb = f"region_{reg.code}" if reg.is_active else "region_inactive"
                builder.button(text=reg.name, callback_data=cb)
            builder.adjust(1)
            await message.answer("👋 **Вітаю!**\n👇 Оберіть вашу область:", reply_markup=builder.as_markup(), parse_mode="Markdown")
            await state.set_state(UserSetup.choosing_region)

@router.callback_query(F.data == "back_to_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.answer()
    async with db.get_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user:
            await cmd_start(callback.message, FSMContext(callback.bot.fsm.storage, callback.bot.fsm.resolve_key(callback)))
            return

        region_name = "Невідомо"
        reg_obj = get_region(user.region)
        if reg_obj: region_name = reg_obj.name

        text = get_menu_text(region_name, user.group_number)
        
        try:
            await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
        except:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "region_inactive")
async def inactive(c: types.CallbackQuery): await c.answer("В розробці", show_alert=True)