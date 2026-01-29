import json
import logging
from sqlalchemy import select
from regions.base import BaseRegion
import database.db as db
from database.models import Schedule

# ВАЖЛИВО: Імпортуємо функцію оновлення з воркера
from .worker import update_data as worker_update_data

logger = logging.getLogger(__name__)

class LvivRegion(BaseRegion):
    code = "lviv"
    name = "Львівська область"
    is_active = True 

    def get_groups(self) -> list[str]:
        # Генеруємо групи 1.1 - 6.2
        groups = []
        for i in range(1, 7):
            for j in range(1, 3):
                groups.append(f"{i}.{j}")
        return groups

    async def get_schedule(self, group: str, date: str) -> dict | None:
        async with db.get_session() as session:
            stmt = select(Schedule).where(
                Schedule.region == self.code,
                Schedule.date == date,
                Schedule.group_code == group
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            
            if not record:
                return None
            try:
                return {
                    "hours": json.loads(record.hours_data),
                    "updated_at": record.site_updated_at
                }
            except Exception as e:
                logger.error(f"[LvivAdapter] JSON Error: {e}")
                return None

    # ВАЖЛИВО: Перевизначаємо метод оновлення, щоб викликати воркер
    async def update_data(self) -> list[str]:
        return await worker_update_data()