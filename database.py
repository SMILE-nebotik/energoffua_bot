import json
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update, delete
from models import Base, User, Schedule
from config import DB_NAME

# Налаштування підключення (використовуємо драйвер aiosqlite)
DATABASE_URL = f"sqlite+aiosqlite:///{DB_NAME}"

# Створюємо двигун (Engine)
engine = create_async_engine(DATABASE_URL, echo=False)

# Фабрика сесій (те, чим ми будемо робити запити)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# --- Ініціалізація ---
async def create_table():
    # В ORM ми просто просимо двигун створити всі таблиці, описані в Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- Робота з Юзерами ---
async def add_user(user_id: int, username: str, group_number: str):
    async with async_session() as session:
        async with session.begin():
            # Створюємо об'єкт
            new_user = User(
                user_id=user_id, 
                username=username, 
                group_number=group_number
            )
            # merge = Insert or Update
            await session.merge(new_user) 
            # commit відбувається автоматично при виході з context manager (session.begin)

async def update_alert_time(user_id: int, alert_time: str):
    async with async_session() as session:
        async with session.begin():
            # Оновлюємо конкретне поле через запит
            stmt = update(User).where(User.user_id == user_id).values(alert_time=alert_time)
            await session.execute(stmt)

async def update_notification_mode(user_id: int, mode: str):
    async with async_session() as session:
        async with session.begin():
            stmt = update(User).where(User.user_id == user_id).values(notification_mode=mode)
            await session.execute(stmt)

async def get_user_data(user_id: int):
    async with async_session() as session:
        # Робимо SELECT об'єкта User
        user = await session.get(User, user_id)
        if user:
            return (user.group_number, user.alert_time)
        return None

async def get_all_users_full():
    async with async_session() as session:
        # SELECT * FROM users
        result = await session.execute(select(User))
        users = result.scalars().all() # Отримуємо список об'єктів User
        
        # Перетворюємо об'єкти назад у кортежі, щоб не ламати main.py
        # Хоча в ідеалі в main.py краще працювати з об'єктами: user.user_id
        return [(u.user_id, u.group_number, u.alert_time, u.notification_mode) for u in users]

# --- Робота з Графіками ---
async def save_schedule_cache(date_str: str, schedule_dict: dict, site_updated_at: str = None):
    async with async_session() as session:
        async with session.begin():
            for group, hours in schedule_dict.items():
                # Створюємо об'єкт графіка
                schedule_obj = Schedule(
                    date=date_str,
                    group_code=group,
                    hours_data=json.dumps(hours),
                    site_updated_at=site_updated_at
                )
                # merge знайде запис за (date, group_code) і оновить його, або створить новий
                await session.merge(schedule_obj)

async def get_schedule_for_group(date_str: str, group: str):
    async with async_session() as session:
        # Складний SELECT з фільтрацією
        stmt = select(Schedule).where(
            Schedule.date == date_str, 
            Schedule.group_code == group
        )
        result = await session.execute(stmt)
        # scalar_one_or_none повертає один об'єкт або нічого
        sch = result.scalar_one_or_none()
        
        if sch:
            return (json.loads(sch.hours_data), sch.site_updated_at)
        return None