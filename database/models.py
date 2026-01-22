from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    region = Column(String, default="volyn")
    group_number = Column(String)
    alert_time = Column(String, default="08:00")
    notification_mode = Column(String, default="no_night") #базово "no_night"

class Schedule(Base):
    __tablename__ = "schedules"

    date = Column(String)
    region = Column(String, default="volyn") # кеш областей
    group_code = Column(String)
    hours_data = Column(Text)  # JSON
    site_updated_at = Column(String, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        PrimaryKeyConstraint('date', 'region', 'group_code'),
    )