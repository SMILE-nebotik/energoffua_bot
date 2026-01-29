from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
import database
import services
import config
from datetime import datetime, timedelta
import pytz 
import re

router = Router()
KYIV_TZ = pytz.timezone('Europe/Kyiv')

class UserSettings(StatesGroup):
    waiting_for_group = State()
    waiting_for_time = State()

class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# formatting function for schedule text
def format_schedule_text(schedule_list, update_time=None):
    if not schedule_list: return "Дані відсутні."
    
    off_slots = schedule_list.count('off')
    total_off_hours = off_slots * 0.5
    
    timeline = ""
    for i in range(0, 48, 2):
        s1 = schedule_list[i]
        s2 = schedule_list[i+1] if i+1 < 48 else 'on'
        if s1 == 'off' or s2 == 'off':
            timeline += "🟥"
        else:
            timeline += "🟩"
    
    timeline_legend = "`00..04..08..12..16..20..24`"

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
                intervals.append(f"🕰 {s_h:02d}:{s_m} - {e_h:02d}:{e_m}")
                start_index = None
    if start_index is not None:
         s_h = start_index // 2
         s_m = "00" if start_index % 2 == 0 else "30"
         intervals.append(f"🕰 {s_h:02d}:{s_m} - 24:00")
         
    intervals_text = "\n".join(intervals) if intervals else "🎉 Світло має бути весь день!"
    
    result = (
        f"{timeline}\n{timeline_legend}\n\n"
        f"{intervals_text}\n\n"
        f"📊 **Всього без світла:** {total_off_hours} год."
    )
    
    if update_time:
        result += f"\n🕒 Оновлено: {update_time}"
        
    return result

# менюшка
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

# start for new user
@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_data = await database.get_user_data(message.from_user.id)
    if user_data:
        await message.answer(
            f"👋 Привіт, {message.from_user.first_name}!\n"
            f"Я моніторю графік для черги **{user_data[0]}**.\n\n"
            "Що хочете зробити?",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        builder = ReplyKeyboardBuilder()
        for g in ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]:
            builder.add(types.KeyboardButton(text=g))
        builder.adjust(4)
        await message.answer("👋 Привіт! Оберіть вашу чергу:", reply_markup=builder.as_markup(resize_keyboard=True))
        await state.set_state(UserSettings.waiting_for_group)

@router.message(UserSettings.waiting_for_group)
async def process_group(message: types.Message, state: FSMContext):
    await database.add_user(message.from_user.id, message.from_user.full_name, message.text)
    await message.answer("Збережено! Введіть час для щоденного звіту (наприклад 08:00):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(UserSettings.waiting_for_time)

@router.message(UserSettings.waiting_for_time)
async def process_time(message: types.Message, state: FSMContext):
    raw_input = message.text.strip()
    
    # validation and normalization
    normalized_input = re.sub(r"[.,\s-]+", ":", raw_input)
    hours, minutes = 0, 0
    
    try:
        if ":" in normalized_input:
            parts = normalized_input.split(":")
            if len(parts) == 2:
                hours = int(parts[0])
                minutes = int(parts[1])
            else:
                raise ValueError
        else:
            if normalized_input.isdigit() and len(normalized_input) <= 2:
                 hours = int(normalized_input)
                 minutes = 0
            elif normalized_input.isdigit() and len(normalized_input) in [3, 4]:
                hours = int(normalized_input[:-2])
                minutes = int(normalized_input[-2:])
            else:
                raise ValueError
        # перевірка валідності часу
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            await message.answer("❌ Час має бути реальним (00-23 години, 00-59 хвилини). Спробуйте ще раз.")
            return

    except ValueError:
        await message.answer(
            "❌ Не зміг розпізнати час.\n"
            "Спробуйте простіші варіанти:\n"
            "• `08:00` або `8:00`\n"
            "• `8.30`\n"
            "• Просто `8` (для 08:00)"
        )
        return

    # перероб для бази
    formatted_time = f"{hours:02d}:{minutes:02d}"
    
    await database.update_alert_time(message.from_user.id, formatted_time)
    
    await message.answer(
        f"✅ Прийнято! Ваш час звіту: **{formatted_time}**\n"
        f"Налаштування завершено.",
        reply_markup=get_main_menu_keyboard()
    )
    await state.clear()

@router.callback_query(F.data == "show_my_graph")
@router.message(Command("graph"))
async def show_my_graph_handler(event: types.Message | types.CallbackQuery):
    if isinstance(event, types.CallbackQuery):
        message = event.message
        user_id = event.from_user.id
        await event.answer("Оновлюю дані...") 
    else:
        message = event
        user_id = event.from_user.id

    user_data = await database.get_user_data(user_id)
    if not user_data:
        await message.answer("Спочатку натисніть /start")
        return

    group = user_data[0]
    await send_schedule_message(message, group, is_personal=True)

async def send_schedule_message(message: types.Message, group: str, is_personal: bool):
    now_kyiv = datetime.now(KYIV_TZ)
    today_str = now_kyiv.strftime("%Y-%m-%d")
    tomorrow_str = (now_kyiv + timedelta(days=1)).strftime("%Y-%m-%d")
    
    response = ""
    
    data_today = await database.get_schedule_for_group(today_str, group)
    if data_today:
        schedule, updated_at = data_today
        text = format_schedule_text(schedule, updated_at)
        response += f"📅 **СЬОГОДНІ ({today_str})** | Черга {group}\n{text}\n\n"
    else:
        response += f"📅 **СЬОГОДНІ ({today_str})**\nДаних немає.\n\n"

    data_tomorrow = await database.get_schedule_for_group(tomorrow_str, group)
    if data_tomorrow:
        schedule, updated_at = data_tomorrow
        text = format_schedule_text(schedule, updated_at)
        response += f"📅 **ЗАВТРА ({tomorrow_str})** | Черга {group}\n{text}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Оновити", callback_data="show_my_graph" if is_personal else f"check_group_{group}")
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    
    if not response: response = "Даних немає."
    
    try:
        await message.edit_text(response, parse_mode="Markdown", reply_markup=builder.as_markup())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        
        # create new message if edit fails
        await message.answer(response, parse_mode="Markdown", reply_markup=builder.as_markup())
    except Exception:
        await message.answer(response, parse_mode="Markdown", reply_markup=builder.as_markup())

# чек іншої черги
@router.callback_query(F.data == "check_other_menu")
async def check_other_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    groups = ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]
    for g in groups:
        builder.add(types.InlineKeyboardButton(text=g, callback_data=f"check_group_{g}"))
    builder.adjust(4)
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    
    await callback.message.edit_text("🔎 Оберіть чергу для перегляду:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("check_group_"))
async def check_specific_group(callback: types.CallbackQuery):
    group = callback.data.replace("check_group_", "")
    await send_schedule_message(callback.message, group, is_personal=False)
    await callback.answer("Завантажено!")

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    user_data = await database.get_user_data(callback.from_user.id)
    group_info = f"Черга: **{user_data[0]}**" if user_data else "Черга не обрана"
    
    await callback.message.edit_text(
        f"🤖 **Головне меню**\n{group_info}",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()

# settings
@router.callback_query(F.data == "open_settings")
async def open_settings_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Завжди", callback_data="set_notify_always")
    builder.button(text="🌙 Тихий режим", callback_data="set_notify_no_night")
    builder.button(text="🔕 Вимкнути", callback_data="set_notify_off")
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⚙️ **Налаштування сповіщень:**\n\n"
        "🔔 **Завжди** — надсилати всі сповіщення.\n"
        "🌙 **Тихий режим** — не турбувати з 23:00 до 07:00.\n"
        "🔕 **Вимкнути** — перевірка тільки вручну.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_notify_"))
async def on_notify_change(callback: types.CallbackQuery):
    mode = callback.data.replace("set_notify_", "")
    await database.update_notification_mode(callback.from_user.id, mode)
    
    mode_text = {
        "always": "🔔 Сповіщення увімкнено (24/7).",
        "no_night": "🌙 Тихий режим увімкнено.",
        "off": "🔕 Сповіщення вимкнено."
    }
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu"))

    await callback.message.edit_text(f"✅ Збережено!\n{mode_text.get(mode)}", reply_markup=builder.as_markup())
    await callback.answer()

# -admins
@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    users = await database.get_all_users_full()
    count = len(users)
    builder = ReplyKeyboardBuilder()
    builder.button(text="Оновити базу")
    builder.button(text="Розсилка")
    builder.adjust(2)
    await message.answer(f"Адмін-панель\n Користувачів: {count}", reply_markup=builder.as_markup(resize_keyboard=True))

@router.message(F.text == "Оновити базу")
async def admin_force_update(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    await message.answer("початок оновлення бази...")
    try:
        changes = await services.update_schedule_database()
        msg = f"Зміни є в групах{changes}" if changes else "База успішно оновлена змін нема"
        await message.answer(msg)
    except Exception as e:
        await message.answer(f"Error: {e}")

@router.message(F.text == "Розсилка")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS: return
    await message.answer("Текст розсилки (або /cancel):")
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
    await message.answer(f"Успішно надіслано користувачам в кількості: {count} ")
    await state.clear()