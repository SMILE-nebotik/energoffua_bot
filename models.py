from sqlalchemy import Column, Integer, String, Text, DateTime, PrimaryKeyConstraint, BigInteger
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func

# Створюємо базовий клас, від якого будуть наслідуватися всі таблиці
class Base(DeclarativeBase):
    pass

# Описуємо таблицю користувачів як Клас
class User(Base):
    __tablename__ = "users"

    # Атрибути класу = Колонки в базі
    # BigInteger краще для Telegram ID (вони довгі)
    user_id = Column(BigInteger, primary_key=True) 
    username = Column(String, nullable=True)
    group_number = Column(String)
    alert_time = Column(String, default="19:00")
    notification_mode = Column(String, default="no_night")

    def __repr__(self):
        return f"<User(id={self.user_id}, group={self.group_number})>"

# Описуємо таблицю графіків
class Schedule(Base):
    __tablename__ = "schedule_cache"

    date = Column(String)
    group_code = Column(String)
    hours_data = Column(Text)  # JSON зберігаємо як текст
    site_updated_at = Column(String, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Складений первинний ключ (унікальна пара дата + група)
    __table_args__ = (
        PrimaryKeyConstraint('date', 'group_code'),
    )