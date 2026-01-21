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

import shutil
import os
from datetime import datetime
from config import DB_NAME

async def backup_database():
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    backup_filename = f"{DB_NAME.replace('.db', '')}_{date_str}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        await asyncio.to_thread(shutil.copy2, DB_NAME, backup_path)
        print(f"успішщний бекап: {backup_path}")
        # потім якшо не забуду добавити авто очистку старих бекапів
    except Exception as e:
        print(f"помилка бекапу {e}")

KYIV_TZ = pytz.timezone('Europe/Kyiv')
PAGE_URL = "https://energy.volyn.ua/spozhyvacham/perervy-u-elektropostachanni/hrafik-vidkliuchen/"

def download_original_image():
    print("24 початок скачування картинки...")
    
    options = Options()
    # options.add_argument("--headless=new") # не трогати поки я не знайду інший костиль поеи воно тримається на цьому костилі
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
        driver.get(PAGE_URL)
        time.sleep(5) 
        
        # пошук iframe з картинкою
        target_url = None
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"пошук айфреймів: {len(iframes)}")
        
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
                        print(f"є картинка: {src}")
                        target_url = src
                        break
            except Exception as e:
                print(f"нема картинки{i}: {e}")
            
            if target_url: break

        # скачка
        if target_url:
            session = requests.Session()
            headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}
            session.headers.update(headers)
            for cookie in driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            
            resp = session.get(target_url)
            if resp.status_code == 200:
                file_content = resp.content
                print("успіх скачування картинки")
            else:
                print(f"помилка 82 {resp.status_code}")
        else:
            print("помилка 84: картинка не знайдена")

    except Exception as e:
        print(f"помилка 87 селеніума{e}")
    finally:
        if driver:
            driver.quit()
            
    return file_content

async def update_schedule_database():
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

    # установка часу оновлення якшо не зловився з картинки
    if not ocr_time_str:
         ocr_time_str = datetime.now(KYIV_TZ).strftime("%H:%M")

    print(f"чек змін {target_date}")
    new_parsed_data = await asyncio.to_thread(image_parser.parse_image, image_bytes, debug=True)
    
    changed_groups = []

    if new_parsed_data:
        for group_id, new_schedule in new_parsed_data.items():
            old_data = await database.get_schedule_for_group(target_date, group_id)
            
            save_it = True
            if old_data:
                old_schedule, _ = old_data
                if old_schedule != new_schedule:
                    print(f"є зміни попередження {group_id}!")
                    changed_groups.append(group_id)
                else:
                    save_it = True
            else:
                pass

            if save_it:
                await database.save_schedule_cache(target_date, {group_id: new_schedule}, site_updated_at=ocr_time_str)
        
        print(f"апдейт успішний {changed_groups}")
        return changed_groups
        
    return None

async def get_schedule_image_url():
    if os.path.exists("schedule_screenshot.png"):
        return FSInputFile("schedule_screenshot.png")
    return None