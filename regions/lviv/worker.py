import asyncio
import logging
import json
from datetime import datetime
import pytz
from sqlalchemy import select
import time

# Import shared core utilities
from core.browser import get_safe_driver
# Note: cleanup functions removed from here

import database.db as db
from database.models import Schedule
from . import parser

logger = logging.getLogger(__name__)
KYIV_TZ = pytz.timezone('Europe/Kyiv')

PAGE_URL = "https://poweron.loe.lviv.ua/"

def _download_text_page():
    """
    Downloads HTML content from Lviv Oblenergo (Text Version).
    """
    # Cleanup removed from here to avoid killing active sessions
    
    driver = None
    page_source = None
    
    try:
        # Use shared driver with fixed version 144
        driver = get_safe_driver(version_main=144, headless=True)
        driver.set_page_load_timeout(30)
        
        logger.info(f"[LvivWorker] Opening: {PAGE_URL}")
        driver.get(PAGE_URL)
        
        # Text sites load fast, but a small wait ensures safety
        time.sleep(2)
        
        page_source = driver.page_source
        logger.info(f"[LvivWorker] Downloaded {len(page_source)} bytes.")

    except Exception as e:
        logger.error(f"[LvivWorker] Download failed: {e}")
    finally:
        if driver:
            try: driver.quit()
            except: pass
            
    return page_source

def download_with_retries():
    """Retry logic."""
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        content = _download_text_page()
        if content:
            return content
        logger.warning(f"[LvivWorker] Attempt {attempt} failed, retrying...")
        
    logger.error("[LvivWorker] Failed to update data after retries.")
    return None

async def update_data():
    """
    Main update function.
    """
    html_content = await asyncio.to_thread(download_with_retries)
    if not html_content: return []

    target_date, update_time, schedule_data = parser.parse_lviv_text_data(html_content)
    
    if not schedule_data:
        logger.warning("[LvivWorker] Parser returned empty schedule.")
        return []

    if not target_date:
        target_date = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")
        logger.warning(f"[LvivWorker] Date not found in text, using system date: {target_date}")
    
    if not update_time:
        update_time = datetime.now(KYIV_TZ).strftime("%H:%M")

    logger.info(f"[LvivWorker] Processing schedule for DATE: {target_date} (Updated: {update_time})")

    changed_groups = []
    
    async with db.get_session() as session:
        for group_id, hours_list in schedule_data.items():
            stmt = select(Schedule).where(
                Schedule.date == target_date,
                Schedule.region == "lviv",
                Schedule.group_code == group_id
            )
            result = await session.execute(stmt)
            old_record = result.scalar_one_or_none()
            
            new_json = json.dumps(hours_list)
            
            if old_record:
                if old_record.hours_data != new_json:
                    old_record.hours_data = new_json
                    old_record.site_updated_at = update_time
                    changed_groups.append(group_id)
            else:
                session.add(Schedule(
                    date=target_date, 
                    region="lviv", 
                    group_code=group_id,
                    hours_data=new_json, 
                    site_updated_at=update_time
                ))
                changed_groups.append(group_id)
        
        await session.commit()

    if changed_groups:
        logger.info(f"📢 [Lviv] Changes detected for groups: {changed_groups}")
        
    return changed_groups