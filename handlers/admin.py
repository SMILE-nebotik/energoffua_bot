import asyncio
import os
import signal
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
from services.broadcaster import notify_changes
from core.browser import kill_zombie_processes, clean_temp_files

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id): return

    async with db.get_session() as session:
        result = await session.execute(select(User))
        users_count = len(result.scalars().all())

    builder = ReplyKeyboardBuilder()
    builder.button(text="Оновити базу")
    builder.button(text="Розсилка")
    builder.button(text="🔄 Перезапустити бота")
    builder.adjust(2, 1)
    
    await message.answer(
        f"⚙️ **Адмін-панель**\n👤 Користувачів у базі: {users_count}", 
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="Markdown"
    )

# restart bot
@router.message(F.text == "🔄 Перезапустити бота")
async def admin_restart_bot(message: types.Message):
    if not is_admin(message.from_user.id): return

    await message.answer("♻️ Бот перезавантажується... (Systemd запустить його знову)")
    
    await asyncio.sleep(1)
    os.kill(os.getpid(), signal.SIGTERM)

# udate database
@router.message(F.text == "Оновити базу")
async def admin_force_update(message: types.Message):
    if not is_admin(message.from_user.id): return

    await message.answer("Починаю повне оновлення (це займе час)...")
    
    report = []
    regions = get_active_regions_list()
    
    for region in regions:
        kill_zombie_processes()
        clean_temp_files()
        
        try:
            await message.answer(f"🔄 Оновлюю: {region.name}...")
            changes = await region.update_data()
            
            status = f"✅ {region.name}: "
            if changes:
                status += f"ЗМІНИ! ({len(changes)} груп)"
                await notify_changes(message.bot, region.code, changes)
            else:
                status += "Без змін"
            
            report.append(status)
            
        except Exception as e:
            report.append(f"❌ {region.name}: Помилка ({e})")
        
        await asyncio.sleep(2)
    
    kill_zombie_processes()
    
    await message.answer("\n".join(report))

# broadcast message
@router.message(F.text == "Розсилка")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("Напиши текст оголошення чи /cancel:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AdminState.waiting_for_broadcast)

@router.message(Command("cancel"), AdminState.waiting_for_broadcast)
async def cancel_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await cmd_admin(message)

@router.message(AdminState.waiting_for_broadcast)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    text = message.text
    bot = message.bot
    
    async with db.get_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
    
    count = 0
    await message.answer(f"Починаю розсилку на {len(users)} юзерів...")
    
    for user in users:
        try:
            await bot.send_message(user.user_id, f"📢 **ОГОЛОШЕННЯ**\n\n{text}", parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
            
    await message.answer(f"Успішно: {count} з {len(users)}")
    await state.clear()
    await cmd_admin(message)