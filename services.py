import sys
import asyncio
import time
import os
import requests
import re
import logging
from datetime import datetime
import pytz 

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import image_parser
import database
from aiogram.types import FSInputFile

# Встановлюємо Київський час
KYIV_TZ = pytz.timezone('Europe/Kyiv')
PAGE_URL = "https://energy.volyn.ua/spozhyvacham/perervy-u-elektropostachanni/hrafik-vidkliuchen/"

def download_original_image():
    print("🚀 Старт перевірки сайту...")
    
    options = Options()
    # options.add_argument("--headless=new") # Можна увімкнути, якщо Tesseract працює
    profile_path = os.path.join(os.getcwd(), "chrome_profile")
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = None
    file_content = None
    found_date_str = None 
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        print(f"🔗 Перехід на: {PAGE_URL}")
        driver.get(PAGE_URL)
        time.sleep(5) 
        
        # --- ЕТАП 1: Шукаємо картинку в IFRAME ---
        target_url = None
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"🔎 Знайдено iframe: {len(iframes)}")
        
        for i, frame in enumerate(iframes):
            try:
                driver.switch_to.default_content()
                iframes = driver.find_elements(By.TAG_NAME, "iframe") 
                driver.switch_to.frame(iframes[i])
                
                # Шукаємо картинку
                imgs = driver.find_elements(By.TAG_NAME, "img")
                for img in imgs:
                    src = img.get_attribute("src")
                    if src and ("GPV" in src or "grafik" in src.lower() or src.endswith(".png")):
                        print(f"📸 Знайдено картинку: {src}")
                        target_url = src
                        break
            except Exception as e:
                print(f"⚠️ Помилка читання iframe {i}: {e}")
            
            if target_url: break

        # --- ЕТАП 2: Завантаження ---
        if target_url:
            session = requests.Session()
            headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}
            session.headers.update(headers)
            for cookie in driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            
            resp = session.get(target_url)
            if resp.status_code == 200:
                file_content = resp.content
                print("📥 Картинку завантажено успішно")
            else:
                print(f"❌ Помилка скачування: {resp.status_code}")
        else:
            print("❌ Не знайдено посилання на графік")

    except Exception as e:
        print(f"❌ Критична помилка Selenium: {e}")
    finally:
        if driver:
            driver.quit()
            
    return file_content

async def update_schedule_database():
    """
    Повертає список груп (['1.1', '2.1']), де графік змінився.
    Повертає None, якщо помилка.
    """
    image_bytes = await asyncio.to_thread(download_original_image)
    if not image_bytes: return None
    
    with open("schedule_screenshot.png", "wb") as f:
        f.write(image_bytes)
    
    ocr_date_str, ocr_time_str = await asyncio.to_thread(image_parser.get_info_from_image, image_bytes)
    
    target_date = None
    if ocr_date_str:
        try:
            d, m, y = ocr_date_str.split('.')
            target_date = f"{y}-{m}-{d}"
        except: pass
    
    if not target_date:
        target_date = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")

    # Якщо час не знайдено, ставимо поточний
    if not ocr_time_str:
         ocr_time_str = datetime.now(KYIV_TZ).strftime("%H:%M")

    print(f"📊 Аналіз змін для: {target_date}")
    new_parsed_data = await asyncio.to_thread(image_parser.parse_image, image_bytes, debug=True)
    
    changed_groups = []

    if new_parsed_data:
        # --- ЛОГІКА ПОРІВНЯННЯ ---
        for group_id, new_schedule in new_parsed_data.items():
            # Отримуємо старий графік з бази
            old_data = await database.get_schedule_for_group(target_date, group_id)
            
            save_it = True
            if old_data:
                old_schedule, _ = old_data
                # Якщо списки відрізняються - значить графік змінився!
                if old_schedule != new_schedule:
                    print(f"⚠️ ЗМІНА ГРАФІКУ для {group_id}!")
                    changed_groups.append(group_id)
                else:
                    save_it = True # Все одно оновлюємо (може змінився час оновлення)
            else:
                # Якщо даних не було, це не вважається "зміною" (це ініціалізація)
                pass

            if save_it:
                await database.save_schedule_cache(target_date, {group_id: new_schedule}, site_updated_at=ocr_time_str)
        
        print(f"💾 База оновлена. Змін виявлено у групах: {changed_groups}")
        return changed_groups # Повертаємо список змін
        
    return None

async def get_schedule_image_url():
    if os.path.exists("schedule_screenshot.png"):
        return FSInputFile("schedule_screenshot.png")
    return None