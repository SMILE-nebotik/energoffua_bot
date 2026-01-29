from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sqlalchemy import select

from core.config import config
import database.db as db
from database.models import User
from handlers.states import AdminState
from regions.registry import get_active_regions_list

router = Router()

# Перевірка на адміна
def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    # підрахунок користувачів
    async with db.get_session() as session:
        result = await session.execute(select(User))
        users_count = len(result.scalars().all())

    builder = ReplyKeyboardBuilder()
    builder.button(text="Оновити базу")
    builder.button(text="Розсилка")
    builder.adjust(2)
    
    await message.answer(
        f"Адмін-панель\n Користувачів у базі: {users_count}", 
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# оновлення бази командою
@router.message(F.text == "Оновити базу")
async def admin_force_update(message: types.Message):
    if not is_admin(message.from_user.id): return

    await message.answer("⏳ Починаю оновлення всіх активних регіонів...")
    
    report = []
    
    for region in get_active_regions_list():
        try:
            changes = await region.update_data()
            status = f"✅ {region.name}: "
            if changes:
                status += f"Зміни в {changes}"
            else:
                status += "Без змін"
            report.append(status)
        except Exception as e:
            report.append(f"❌ {region.name}: Помилка ({e})")
    
    await message.answer("\n".join(report))

# розсилка(закос під рекламу)
@router.message(F.text == "Розсилка")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    await message.answer("Напиши текст оголошення чи cancel для відміни:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AdminState.waiting_for_broadcast)

@router.message(Command("cancel"), AdminState.waiting_for_broadcast)
async def cancel_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Скасовано.")

@router.message(AdminState.waiting_for_broadcast)
async def admin_broadcast_send(message: types.Message, state: FSMContext, bot):
    text = message.text
    
    # Отримуємо всіх юзерів
    async with db.get_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
    
    count = 0
    await message.answer(f"Починаю розсилку на {len(users)} користувачів")
    
    for user in users:
        try:
            await bot.send_message(user.user_id, f"📢 **ОГОЛОШЕННЯ**\n\n{text}", parse_mode="Markdown")
            count += 1
        except Exception:
            pass
            
    await message.answer(f"Успішно надіслано: {count} з {len(users)}")
    await state.clear()