import os
import time
import requests
import asyncio
import logging
import json
from datetime import datetime
import pytz 

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from pyvirtualdisplay import Display

from core.config import config
import database.db as db
from database.models import Schedule
from sqlalchemy import select
from . import parser 

from core.browser import kill_zombie_processes, clean_temp_files

logger = logging.getLogger(__name__)
KYIV_TZ = pytz.timezone('Europe/Kyiv')
PAGE_URL = "https://energy.volyn.ua/spozhyvacham/perervy-u-elektropostachanni/hrafik-vidkliuchen/"

def _download_attempt():
    kill_zombie_processes()
    clean_temp_files()
    
    logger.info("start with vs display")
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    
    driver = None
    file_content = None
    
    try:
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        
        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(60)
        
        logger.info(f"[Worker] open: {PAGE_URL}")
        driver.get(PAGE_URL)
        time.sleep(10) 
        
        target_url = None

        # Пошук картинки
        imgs = driver.find_elements(By.TAG_NAME, "img")
        for img in imgs:
            try:
                src = img.get_attribute("src")
                if src and ("GPV" in src or "grafik" in src.lower()):
                    target_url = src
                    logger.info(f"✨ [Worker] Знайдено: {src}")
                    break
            except: continue

        if not target_url:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for i in range(len(iframes)):
                try:
                    driver.switch_to.frame(i)
                    inner_imgs = driver.find_elements(By.TAG_NAME, "img")
                    for img in inner_imgs:
                        s = img.get_attribute("src")
                        if s and ("GPV" in s or "grafik" in s.lower()):
                            target_url = s
                            break
                    driver.switch_to.default_content()
                except: driver.switch_to.default_content()
                if target_url: break

        if target_url:
            session = requests.Session()
            for cookie in driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            
            headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}
            resp = session.get(target_url, headers=headers, timeout=30)
            
            if resp.status_code == 200:
                file_content = resp.content
            else:
                logger.error(f"[Worker] HTTP Error: {resp.status_code}")
        else:
            logger.warning("[Worker] Картинку не знайдено в цій спробі.")

    except Exception as e:
        logger.error(f"[Worker] Помилка спроби: {e}")
    finally:
        if driver:
            try: driver.quit()
            except: pass
        try: display.stop()
        except: pass
            
    return file_content

def download_with_retries():
    """Головна функція з логікою повторних спроб"""
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        logger.info(f"[Worker] Спроба #{attempt} із {max_retries}...")
        
        content = _download_attempt()
        
        if content:
            logger.info("[Worker] Успіх")
            return content
        
        if attempt < max_retries:
            wait_time = 60
            logger.warning(f"[Worker] Невдача. Чекаю {wait_time}сек перед повтором...")
            time.sleep(wait_time)
    
    logger.error("[Worker] Дані не оновлено.")
    return None

async def run_update():
    # Використовуємо функцію з ретраями
    image_bytes = await asyncio.to_thread(download_with_retries)
    
    if not image_bytes: return []
    
    ocr_date_str, ocr_time_str = await asyncio.to_thread(parser.get_info_from_image, image_bytes)
    target_date = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")
    if ocr_date_str:
        try:
            d, m, y = ocr_date_str.split('.')
            target_date = f"{y}-{m}-{d}"
        except: pass

    if not ocr_time_str: ocr_time_str = datetime.now(KYIV_TZ).strftime("%H:%M")

    new_schedule = await asyncio.to_thread(parser.parse_image, image_bytes)
    if not new_schedule: return []

    changed_groups = []
    async with db.get_session() as session:
        for group_id, hours_data in new_schedule.items():
            stmt = select(Schedule).where(
                Schedule.date == target_date,
                Schedule.region == "volyn",
                Schedule.group_code == group_id
            )
            result = await session.execute(stmt)
            old_record = result.scalar_one_or_none()
            
            if old_record:
                if json.loads(old_record.hours_data) != hours_data:
                    old_record.hours_data = json.dumps(hours_data)
                    old_record.site_updated_at = ocr_time_str
                    changed_groups.append(group_id)
            else:
                session.add(Schedule(
                    date=target_date, region="volyn", group_code=group_id,
                    hours_data=json.dumps(hours_data), site_updated_at=ocr_time_str
                ))
                changed_groups.append(group_id)
        await session.commit()
    
    if changed_groups: logger.info(f"📢 [Update] Зміни: {changed_groups}")
    return changed_groups