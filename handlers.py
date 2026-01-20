from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import database
import services
from datetime import datetime

router = Router()

class UserSettings(StatesGroup):
    waiting_for_group = State()
    waiting_for_time = State()

def format_schedule_text(schedule_list):
    if not schedule_list: return "Дані відсутні або ще не оновилися."
    
    intervals = []
    start_index = None
    
    for i, status in enumerate(schedule_list):
        if status == 'off':
            if start_index is None: start_index = i
        else:
            if start_index is not None:
                s_h = start_index // 2
                s_m = "00" if start_index % 2 == 0 else "30"
                e_h = i // 2
                e_m = "00" if i % 2 == 0 else "30"
                intervals.append(f"🔴 {s_h:02d}:{s_m} - {e_h:02d}:{e_m}")
                start_index = None
    
    if start_index is not None:
         s_h = start_index // 2
         s_m = "00" if start_index % 2 == 0 else "30"
         intervals.append(f"🔴 {s_h:02d}:{s_m} - 24:00")
         
    if not intervals: return "🟢 Світло буде весь день (можливо)!"
    return "\n".join(intervals)

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    # Групирупи на для викьору
    for g in ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]:
        builder.add(types.KeyboardButton(text=g))
    builder.adjust(4)
    await message.answer("Оберіть вашу чергу:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(UserSettings.waiting_for_group)

@router.message(UserSettings.waiting_for_group)
async def process_group(message: types.Message, state: FSMContext):
    await database.add_user(message.from_user.id, message.from_user.full_name, message.text)
    await message.answer("Збережено! Введіть час сповіщення (ГГ:ХХ):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(UserSettings.waiting_for_time)

@router.message(UserSettings.waiting_for_time)
async def process_time(message: types.Message, state: FSMContext):
    await database.update_alert_time(message.from_user.id, message.text)
    await message.answer(f"Готово! Перевірити зараз: /graph")
    await state.clear()

@router.message(Command("graph"))
async def send_graph(message: types.Message):
    user_data = await database.get_user_data(message.from_user.id)
    if not user_data:
        await message.answer("Спочатку /start")
        return

    group = user_data[0]
    today = datetime.now().strftime("%Y-%m-%d")
    
    # чек бази
    schedule_data = await database.get_schedule_for_group(today, group)
    
    # апдейт бази якщо пусто
    if not schedule_data:
        await message.answer("Шукаю свіжі дані...")
        await services.update_schedule_database()
        schedule_data = await database.get_schedule_for_group(today, group)
    
    if schedule_data:
        text = format_schedule_text(schedule_data)
        await message.answer(f"Графік для {group}:\n\n{text}")
    else:
        await message.answer("На жаль, не вдалося отримати дані. Можливо, сайт тимчасово недоступний.")