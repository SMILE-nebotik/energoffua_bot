import os
import time
import requests
import asyncio
import logging
import json
from datetime import datetime
import pytz 

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from core.config import config
import database.db as db
from database.models import Schedule
from sqlalchemy import select
from . import parser 

# Налаштування логера
logger = logging.getLogger(__name__)

KYIV_TZ = pytz.timezone('Europe/Kyiv')
PAGE_URL = "https://energy.volyn.ua/spozhyvacham/perervy-u-elektropostachanni/hrafik-vidkliuchen/"

def download_original_image():
    """Покращена функція скачування картинки"""
    logger.info("🚀 [Worker] Запуск Chrome (Stealth Mode)...")
    
    options = Options()
    # Обов'язкові налаштування для сервера (без екрану)
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Маскуємося під звичайний браузер Windows
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = None
    file_content = None
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        logger.info(f"🌐 [Worker] Відкриваю сторінку: {PAGE_URL}")
        driver.get(PAGE_URL)
        
        # Чекаємо 15 секунд, щоб сайт точно прогрузився
        time.sleep(15) 
        
        target_url = None

        # --- СПОСІБ 1: Шукаємо картинку прямо на сторінці ---
        logger.info("🔎 [Worker] Шукаю картинку...")
        all_imgs = driver.find_elements(By.TAG_NAME, "img")
        for img in all_imgs:
            try:
                src = img.get_attribute("src")
                # Шукаємо ключові слова в посиланні
                if src and ("GPV" in src or "grafik" in src.lower() or "uploads" in src):
                    target_url = src
                    logger.info(f"✨ [Worker] Знайдено (Спосіб 1): {src}")
                    break
            except: continue

        # --- СПОСІБ 2: Якщо не знайшли, ліземо всередину фреймів ---
        if not target_url:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            logger.info(f"🔎 [Worker] Спосіб 1 не спрацював. Перевіряю {len(iframes)} фреймів...")
            
            for i in range(len(iframes)):
                try:
                    driver.switch_to.default_content()
                    frames = driver.find_elements(By.TAG_NAME, "iframe")
                    driver.switch_to.frame(frames[i])
                    
                    inner_imgs = driver.find_elements(By.TAG_NAME, "img")
                    for img in inner_imgs:
                        src = img.get_attribute("src")
                        if src and ("GPV" in src or "grafik" in src.lower()):
                            target_url = src
                            logger.info(f"✨ [Worker] Знайдено у фреймі #{i}: {src}")
                            break
                except: pass
                if target_url: break

        # --- Скачуємо файл ---
        if target_url:
            session = requests.Session()
            # Беремо куки з браузера, щоб сайт думав, що ми той самий користувач
            for cookie in driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            
            # Додаємо такий самий User-Agent
            headers = {"User-Agent": options.arguments[-1].split("=")[1]}
            
            resp = session.get(target_url, headers=headers, timeout=30)
            if resp.status_code == 200:
                file_content = resp.content
                logger.info(f"📥 [Worker] Файл успішно завантажено ({len(file_content)} байт)!")
            else:
                logger.error(f"❌ [Worker] Помилка скачування файлу: {resp.status_code}")
        else:
            # Робимо фото екрану, щоб зрозуміти, що бачить бот
            debug_file = os.path.join(config.BASE_DIR, "debug_error.png")
            driver.save_screenshot(debug_file)
            logger.error(f"❌ [Worker] Картинку не знайдено! Скріншот збережено в {debug_file}")

    except Exception as e:
        logger.error(f"❌ [Worker] Помилка Selenium: {e}")
    finally:
        if driver: 
            try: driver.quit()
            except: pass
            
    return file_content

async def run_update():
    """Логіка оновлення бази"""
    # 1. Скачуємо
    image_bytes = await asyncio.to_thread(download_original_image)
    
    if not image_bytes:
        return []
    
    # 2. Парсимо дату і час
    ocr_date_str, ocr_time_str = await asyncio.to_thread(parser.get_info_from_image, image_bytes)
    
    target_date = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")
    if ocr_date_str:
        try:
            d, m, y = ocr_date_str.split('.')
            target_date = f"{y}-{m}-{d}"
        except: pass

    if not ocr_time_str:
         ocr_time_str = datetime.now(KYIV_TZ).strftime("%H:%M")

    # 3. Розпізнаємо графік (квадратики)
    new_schedule = await asyncio.to_thread(parser.parse_image, image_bytes)
    if not new_schedule: return []

    changed_groups = []

    # 4. Зберігаємо в базу
    async with db.get_session() as session:
        for group_id, hours_data in new_schedule.items():
            stmt = select(Schedule).where(
                Schedule.date == target_date,
                Schedule.region == "volyn",
                Schedule.group_code == group_id
            )
            result = await session.execute(stmt)
            old_record = result.scalar_one_or_none()
            
            is_changed = False
            
            if old_record:
                old_hours = json.loads(old_record.hours_data)
                if old_hours != hours_data:
                    is_changed = True
                    old_record.hours_data = json.dumps(hours_data)
                    old_record.site_updated_at = ocr_time_str
            else:
                new_record = Schedule(
                    date=target_date,
                    region="volyn",
                    group_code=group_id,
                    hours_data=json.dumps(hours_data),
                    site_updated_at=ocr_time_str
                )
                session.add(new_record)
                if target_date == datetime.now(KYIV_TZ).strftime("%Y-%m-%d"):
                    is_changed = True

            if is_changed:
                changed_groups.append(group_id)
        
        await session.commit()
    
    if changed_groups:
        logger.info(f"📢 [Update] Є зміни в групах: {changed_groups}")
    else:
        logger.info("✅ [Update] Графік актуальний, змін немає.")
    
    return changed_groups