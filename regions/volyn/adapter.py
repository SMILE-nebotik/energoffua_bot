from regions.base import BaseRegion
import database.db as db
from database.models import Schedule
from sqlalchemy import select
import json
import logging

# Імпортуємо воркер
from regions.volyn import worker

class VolynRegion(BaseRegion):
    code = "volyn"
    name = "Волинська область"
    is_active = True

    def get_groups(self) -> list[str]:
        return ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", 
                "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]

    async def get_schedule(self, group: str, date: str) -> dict | None:
        async with db.get_session() as session:
            stmt = select(Schedule).where(
                Schedule.date == date,
                Schedule.region == self.code,
                Schedule.group_code == group
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            
            if record:
                return {
                    "hours": json.loads(record.hours_data),
                    "updated_at": record.site_updated_at
                }
            return None

    # ПІДКЛЮЧАЄМО ВОРКЕР
    async def update_data(self) -> list[str]:
        logging.info("🔄 Запуск оновлення даних для Волині...")
        return await worker.run_update()