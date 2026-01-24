import json
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update, delete
from models import Base, User, Schedule
from config import DB_NAME

DATABASE_URL = f"sqlite+aiosqlite:///{DB_NAME}"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# init database
async def create_table():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# work with Users table
async def add_user(user_id: int, username: str, group_number: str):
    async with async_session() as session:
        async with session.begin():
            new_user = User(
                user_id=user_id, 
                username=username, 
                group_number=group_number
            )
            # merge = Insert or Update
            await session.merge(new_user) 

async def update_alert_time(user_id: int, alert_time: str):
    async with async_session() as session:
        async with session.begin():
            # update statement
            stmt = update(User).where(User.user_id == user_id).values(alert_time=alert_time)
            await session.execute(stmt)

async def update_notification_mode(user_id: int, mode: str):
    async with async_session() as session:
        async with session.begin():
            stmt = update(User).where(User.user_id == user_id).values(notification_mode=mode)
            await session.execute(stmt)

async def get_user_data(user_id: int):
    async with async_session() as session:
        user = await session.get(User, user_id)
        if user:
            return (user.group_number, user.alert_time)
        return None

async def get_all_users_full():
    async with async_session() as session:
        # SELECT * FROM users
        result = await session.execute(select(User))
        users = result.scalars().all()
        return [(u.user_id, u.group_number, u.alert_time, u.notification_mode) for u in users]

# --- Робота з Графіками ---
async def save_schedule_cache(date_str: str, schedule_dict: dict, site_updated_at: str = None):
    async with async_session() as session:
        async with session.begin():
            for group, hours in schedule_dict.items():
                schedule_obj = Schedule(
                    date=date_str,
                    group_code=group,
                    hours_data=json.dumps(hours),
                    site_updated_at=site_updated_at
                )
                await session.merge(schedule_obj)

async def get_schedule_for_group(date_str: str, group: str):
    async with async_session() as session:
        # Складний SELECT з фільтрацією
        stmt = select(Schedule).where(
            Schedule.date == date_str, 
            Schedule.group_code == group
        )
        result = await session.execute(stmt)
        sch = result.scalar_one_or_none()
        
        if sch:
            return (json.loads(sch.hours_data), sch.site_updated_at)
        return None