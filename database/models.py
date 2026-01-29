from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

# Обов'язково залишаємо цей клас, його шукає db.py
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    # Використовуємо BigInteger для Telegram ID
    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    region = Column(String, default="volyn")
    group_number = Column(String, nullable=True)
    alert_time = Column(String, default="08:00")
    notification_mode = Column(String, default="no_night")

class Schedule(Base):
    __tablename__ = "schedules"

    # Складений первинний ключ (Primary Key) по даті, регіону та групі
    date = Column(String, primary_key=True)      # Формат YYYY-MM-DD
    region = Column(String, primary_key=True)    # lviv або volyn
    group_code = Column(String, primary_key=True) # 1.1, 2.2 і т.д.
    
    hours_data = Column(Text)                    # JSON рядок зі списком [on, off, ...]
    site_updated_at = Column(String, nullable=True) # Час з сайту (напр. 11:11)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Ми явно вказуємо PrimaryKeyConstraint, щоб SQLAlchemy не лаялась
    __table_args__ = (
        PrimaryKeyConstraint('date', 'region', 'group_code'),
    )