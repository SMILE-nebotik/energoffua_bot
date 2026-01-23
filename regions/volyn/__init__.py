from .worker import run_update as update_data
from database.models import Schedule
import json
import database.db as db
from sqlalchemy import select

code = "volyn"
name = "Волинська область"

async def get_schedule(group_code: str, date_str: str):
    async with db.get_session() as session:
        stmt = select(Schedule).where(
            Schedule.region == code,
            Schedule.group_code == group_code,
            Schedule.date == date_str
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        
        if record:
            return {
                "hours": json.loads(record.hours_data),
                "updated_at": record.site_updated_at
            }
    return None