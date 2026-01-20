# хуйня для того щоб парсити сайт з графіком відключень
import sys
import asyncio
import time
import os
import requests
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import image_parser
import database
from aiogram.types import FSInputFile

PAGE_URL = "https://energy.volyn.ua/spozhyvacham/perervy-u-elektropostachanni/hrafik-vidkliuchen/"

def download_original_image():
    print("старт чеку сайту")
    
    options = Options()
    # options.add_argument("--headless=new") # якшо офнути не працює тому поки я не добавлю новий костиль не вирубати закоментування
    profile_path = os.path.join(os.getcwd(), "chrome_profile")
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    
    driver = None
    file_content = None
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        print(f"чек сайту {PAGE_URL}")
        driver.get(PAGE_URL)
        time.sleep(15) 
        
        target_url = None

        # пошук по силкам
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and (".jpg" in href.lower() or ".png" in href.lower() or "google.com/file" in href) and "logo" not in href:
                    if "GPV" in href or "grafik" in href.lower() or "drive" in href:
                        target_url = href
                        print(f"\ лінк {href}")
                        break
            except: continue
            
        # чек айфреймів якщо нема
        if not target_url:
            print("\nскан афйремів")
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"Знайдено iframe: {len(iframes)}")
            
            for i, frame in enumerate(iframes):
                try:
                    driver.switch_to.default_content()
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    driver.switch_to.frame(iframes[i])
                    
                    print(f" успіх{i+1}...")
                    
                    imgs = driver.find_elements(By.TAG_NAME, "img")
                    for img in imgs:
                        src = img.get_attribute("src")
                        if src and ("GPV" in src or "grafik" in src.lower() or src.endswith(".png")):
                            print(f"є {src}")
                            target_url = src
                            break
                except Exception as e:
                    print(f"Не успіх {e}")
                
                if target_url: break

        # установлення 
        if target_url:
            print(f"скачака з {target_url}")
            session = requests.Session()
            
            # Копіюємо заголовки і куки
            headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}
            session.headers.update(headers)
            for cookie in driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            
            resp = session.get(target_url)
            if resp.status_code == 200:
                file_content = resp.content
                print("успіш скачаки")
            else:
                print(f"не скачалось {resp.status_code}")
        else:
            print("нема файлів для скачки")

    except Exception as e:
        print(f"xd поплач помилка {e}")
    finally:
        if driver:
            print("закр хром")
            driver.quit()
            
    return file_content

async def update_schedule_database():
    image_bytes = await asyncio.to_thread(download_original_image)
    
    if not image_bytes: return False
    
    # Зберігаємо оригінал
    with open("schedule_screenshot.png", "wb") as f:
        f.write(image_bytes)
    
    # Пробуємо OCR
    date_text = image_parser.get_date_from_image(image_bytes)
    target_date = datetime.now().strftime("%Y-%m-%d")
    
    if date_text:
        import re
        match = re.search(r'(\d{2})\.(\d{2})', date_text)
        if match:
            day, month = match.groups()
            target_date = f"2026-{month}-{day}"
            print(f"📅 Дата розпізнана: {target_date}")

    print(f"аналіз")
    parsed_data = image_parser.parse_image(image_bytes, debug=True)
    
    if parsed_data:
        await database.save_schedule_cache(target_date, parsed_data)
        print("апдейт бази успішний")
        return True
    return False

async def get_schedule_image_url():
    if os.path.exists("schedule_screenshot.png"):
        return FSInputFile("schedule_screenshot.png")
    return None