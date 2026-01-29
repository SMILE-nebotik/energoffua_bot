import logging
import asyncio
import time
import json
from datetime import datetime
import pytz

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from pyvirtualdisplay import Display
from sqlalchemy import select

from core.browser import kill_zombie_processes, clean_temp_files
import database.db as db
from database.models import Schedule
from . import parser

logger = logging.getLogger(__name__)
KYIV_TZ = pytz.timezone('Europe/Kyiv')
PAGE_URL = "https://poweron.loe.lviv.ua/"

def fetch_html_content():
    """Завантажує HTML сторінку з сайту Львівобленерго."""
    kill_zombie_processes()
    clean_temp_files()
    
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    
    driver = None
    html_source = None
    
    try:
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(60)
        
        logger.info(f"[Lviv] Connecting to {PAGE_URL}")
        driver.get(PAGE_URL)
        
        # Чекаємо завантаження скриптів/таблиці
        time.sleep(10)
        
        # Отримуємо чистий HTML
        html_source = driver.page_source
        logger.info(f"[Lviv] Page downloaded. Size: {len(html_source)} bytes")

    except Exception as e:
        logger.error(f"[Lviv] Download error: {e}")
    finally:
        if driver:
            try: driver.quit()
            except: pass
        try: display.stop()
        except: pass
            
    return html_source

async def update_data():
    """Основна функція оновлення даних для регіону Львів."""
    html_content = await asyncio.to_thread(fetch_html_content)
    
    if not html_content:
        return []

    # Парсимо HTML (логіка в parser.py)
    # Повертає словник: {'1.1': {'00-01': 'no', ...}, ...}
    new_schedule = await asyncio.to_thread(parser.parse_lviv_html, html_content)
    
    if not new_schedule:
        logger.warning("[Lviv] Failed to parse schedule from HTML.")
        return []

    changed_groups = []
    today_str = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")
    update_time = datetime.now(KYIV_TZ).strftime("%H:%M")

    async with db.get_session() as session:
        for group_code, hours_data in new_schedule.items():
            stmt = select(Schedule).where(
                Schedule.date == today_str,
                Schedule.region == "lviv",
                Schedule.group_code == group_code
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            
            json_data = json.dumps(hours_data)
            
            if record:
                if record.hours_data != json_data:
                    record.hours_data = json_data
                    record.site_updated_at = update_time
                    changed_groups.append(group_code)
            else:
                session.add(Schedule(
                    date=today_str,
                    region="lviv",
                    group_code=group_code,
                    hours_data=json_data,
                    site_updated_at=update_time
                ))
                changed_groups.append(group_code)
        
        await session.commit()
    
    return changed_groups