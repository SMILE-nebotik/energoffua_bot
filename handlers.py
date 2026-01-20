from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import database
import services
import config
from datetime import datetime, timedelta
import pytz 

router = Router()
KYIV_TZ = pytz.timezone('Europe/Kyiv')

# --- ВИЗНАЧЕННЯ СТАНІВ (Ось це було пропущено) ---
class UserSettings(StatesGroup):
    waiting_for_group = State()
    waiting_for_time = State()

class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# --- ДОПОМІЖНІ ФУНКЦІЇ ---
def format_schedule_text(schedule_list, update_time=None):
    if not schedule_list: return "Дані відсутні."
    
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
         
    result = "\n".join(intervals) if intervals else "🟢 Світло має бути весь день!"
    
    if update_time:
        result += f"\n\n🕒 *Інфо станом на {update_time}*"
        
    return result

# --- НАЛАШТУВАННЯ (/settings) ---

@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Завжди", callback_data="set_notify_always")
    builder.button(text="🌙 Тихий режим (без ночі)", callback_data="set_notify_no_night")
    builder.button(text="🔕 Вимкнути", callback_data="set_notify_off")
    builder.adjust(1)
    
    await message.answer(
        "⚙️ **Налаштування сповіщень:**\n\n"
        "🔔 **Завжди** — надсилати всі сповіщення (і зміни, і 15 хв).\n"
        "🌙 **Тихий режим** — не турбувати з 23:00 до 07:00 (рекомендовано).\n"
        "🔕 **Вимкнути** — я буду перевіряти графік тільки вручну.",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("set_notify_"))
async def on_notify_change(callback: types.CallbackQuery):
    mode = callback.data.replace("set_notify_", "")
    await database.update_notification_mode(callback.from_user.id, mode)
    
    mode_text = {
        "always": "🔔 Сповіщення увімкнено (24/7).",
        "no_night": "🌙 Тихий режим увімкнено (без сповіщень вночі).",
        "off": "🔕 Сповіщення вимкнено."
    }
    
    await callback.message.edit_text(f"✅ Налаштування збережено!\n{mode_text.get(mode)}")
    await callback.answer()

# --- АДМІНКА (/admin) ---

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    
    users = await database.get_all_users_full()
    count = len(users)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="Оновити базу")
    builder.button(text="Розсилка")
    builder.adjust(2)
    
    await message.answer(
        f"👨‍💻 **Адмін-панель**\n\n👥 Користувачів: {count}\n🤖 ID: {message.from_user.id}",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(F.text == "Оновити базу")
async def admin_force_update(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    await message.answer("🔄 Запускаю примусове оновлення...")
    
    try:
        changes = await services.update_schedule_database()
        if changes is not None:
            if changes:
                await message.answer(f"✅ Успішно! Зміни в групах: {changes}")
            else:
                await message.answer("✅ База оновлена, змін у графіках немає.")
        else:
            await message.answer("❌ Помилка оновлення (див. логи).")
    except Exception as e:
        await message.answer(f"Error: {e}")

@router.message(F.text == "Розсилка")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS: return
    await message.answer("Введіть текст повідомлення для всіх користувачів (або /cancel):")
    await state.set_state(AdminState.waiting_for_broadcast)

@router.message(AdminState.waiting_for_broadcast)
async def admin_broadcast_send(message: types.Message, state: FSMContext, bot):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Скасовано.")
        return

    users = await database.get_all_users_full()
    count = 0
    for user_id, _, _, _ in users:
        try:
            await bot.send_message(user_id, f"📢 **Оголошення:**\n\n{message.text}")
            count += 1
        except: pass
    
    await message.answer(f"✅ Надіслано {count} користувачам.")
    await state.clear()

# --- ОСНОВНИЙ ФУНКЦІОНАЛ (/start, /graph) ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    # Групи для вибору
    for g in ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]:
        builder.add(types.KeyboardButton(text=g))
    builder.adjust(4)
    await message.answer("Оберіть вашу чергу:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(UserSettings.waiting_for_group)

@router.message(UserSettings.waiting_for_group)
async def process_group(message: types.Message, state: FSMContext):
    # Зберігаємо юзера (за замовчуванням 'no_night')
    await database.add_user(message.from_user.id, message.from_user.full_name, message.text)
    await message.answer("Збережено! Введіть час для щоденного звіту (наприклад 08:00):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(UserSettings.waiting_for_time)

@router.message(UserSettings.waiting_for_time)
async def process_time(message: types.Message, state: FSMContext):
    await database.update_alert_time(message.from_user.id, message.text)
    await message.answer(f"Готово! \n⚙️ Налаштування сповіщень: /settings\n📊 Перевірити графік: /graph")
    await state.clear()

@router.message(Command("graph"))
async def send_graph(message: types.Message):
    user_data = await database.get_user_data(message.from_user.id)
    if not user_data:
        await message.answer("Спочатку натисніть /start")
        return

    group = user_data[0]
    
    now_kyiv = datetime.now(KYIV_TZ)
    today_str = now_kyiv.strftime("%Y-%m-%d")
    tomorrow_str = (now_kyiv + timedelta(days=1)).strftime("%Y-%m-%d")
    
    response = ""
    
    # --- СЬОГОДНІ ---
    data_today = await database.get_schedule_for_group(today_str, group)
    
    if data_today:
        schedule, updated_at = data_today
        text = format_schedule_text(schedule, updated_at)
        response += f"📅 **СЬОГОДНІ ({today_str})** | Черга {group}\n{text}\n\n"
    else:
        response += f"📅 **СЬОГОДНІ ({today_str})**\nДаних немає.\n\n"

    # --- ЗАВТРА ---
    data_tomorrow = await database.get_schedule_for_group(tomorrow_str, group)
    
    if data_tomorrow:
        schedule, updated_at = data_tomorrow
        text = format_schedule_text(schedule, updated_at)
        response += f"📅 **ЗАВТРА ({tomorrow_str})** | Черга {group}\n{text}"
    
    if not data_today and not data_tomorrow:
        await message.answer("Даних немає, спробуйте пізніше або натисніть /admin -> Оновити базу (якщо ви адмін).")
    else:
        await message.answer(response, parse_mode="Markdown")