import aiosqlite
import json
from config import DB_NAME

async def create_table():
    async with aiosqlite.connect(DB_NAME) as db:
        # Додали notification_mode
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                group_number TEXT,
                alert_time TEXT DEFAULT '19:00',
                notification_mode TEXT DEFAULT 'no_night'
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS schedule_cache (
                date TEXT, 
                group_code TEXT,
                hours_data TEXT, 
                site_updated_at TEXT, 
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, group_code)
            )
        ''')
        await db.commit()

# Оновлення налаштувань сповіщень
async def update_notification_mode(user_id: int, mode: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET notification_mode = ? WHERE user_id = ?', (mode, user_id))
        await db.commit()

# Отримуємо тепер і режим сповіщень
async def get_all_users_full():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT user_id, group_number, alert_time, notification_mode FROM users') as cursor:
            return await cursor.fetchall()

# --- Решта функцій (add_user, get_user_data, save_schedule...) залишаються ТАКИМИ Ж ЯК БУЛИ ---
# Просто скопіюй їх з попереднього варіанту, вони не змінилися.
# Нижче дублюю для повноти картини тільки ті, що треба:

async def add_user(user_id: int, username: str, group_number: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO users (user_id, username, group_number) 
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET group_number = excluded.group_number
        ''', (user_id, username, group_number))
        await db.commit()

async def update_alert_time(user_id: int, alert_time: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET alert_time = ? WHERE user_id = ?', (alert_time, user_id))
        await db.commit()

async def get_user_data(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT group_number, alert_time FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def save_schedule_cache(date_str: str, schedule_dict: dict, site_updated_at: str = None):
    async with aiosqlite.connect(DB_NAME) as db:
        for group, hours in schedule_dict.items():
            await db.execute('''
                INSERT INTO schedule_cache (date, group_code, hours_data, site_updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date, group_code) DO UPDATE SET 
                hours_data = excluded.hours_data,
                site_updated_at = excluded.site_updated_at,
                updated_at = CURRENT_TIMESTAMP
            ''', (date_str, group, json.dumps(hours), site_updated_at))
        await db.commit()

async def get_schedule_for_group(date_str: str, group: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT hours_data, site_updated_at FROM schedule_cache WHERE date = ? AND group_code = ?', (date_str, group)) as cursor:
            row = await cursor.fetchone()
            if row:
                return (json.loads(row[0]), row[1])
            return None