import sys
import asyncio
import time
import os
import requests
import re
import logging
from datetime import datetime
import pytz # бібла для часових поясів

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
    print("старт чеку сайту")
    
    options = Options()
    # options.add_argument("--headless=new") # розкоментуй це, коли все буде працювати ідеально
    profile_path = os.path.join(os.getcwd(), "chrome_profile")
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    
    driver = None
    file_content = None
    found_date_str = None # сюди запишемо дату яку знайдем на сайті
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        print(f"чек сайту {PAGE_URL}")
        driver.get(PAGE_URL)
        time.sleep(10) # даємо час провантажитися
        
        target_url = None

        # Спершу шукаємо iframe, бо на скріні видно, що графік там
        print("\nскан iframe...")
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"Знайдено iframe: {len(iframes)}")
        
        for i, frame in enumerate(iframes):
            try:
                driver.switch_to.default_content()
                # Оновлюємо список фреймів, бо DOM міг змінитись
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                driver.switch_to.frame(iframes[i])
                
                print(f"Перевірка iframe {i+1}...")
                time.sleep(2) # чекаємо поки прогрузиться вміст фрейму

                # --- НОВА ЛОГІКА ПОШУКУ ДАТИ В IFRAME ---
                try:
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    # Шукаємо фразу "ГПВ на 20.01.2026"
                    # Регулярка шукає: або "ГПВ на DD.MM.YYYY", або просто дату
                    date_match = re.search(r"ГПВ.*?(\d{2}\.\d{2}\.\d{4})", body_text)
                    if not date_match:
                        # Якщо не знайшли з "ГПВ", шукаємо просто дату
                        date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", body_text)

                    if date_match:
                        found_date_raw = date_match.group(1) # отримали string 20.01.2026
                        d, m, y = found_date_raw.split('.')
                        found_date_str = f"{y}-{m}-{d}" # Формат для бази YYYY-MM-DD
                        print(f"Знайдено дату в iframe: {found_date_str}")
                except Exception as e:
                    print(f"Помилка пошуку тексту дати: {e}")


                imgs = driver.find_elements(By.TAG_NAME, "img")
                for img in imgs:
                    src = img.get_attribute("src")
                    # Шукаємо картинку, яка схожа на графік
                    if src and ("GPV" in src or "grafik" in src.lower() or src.endswith(".png")):
                        print(f"Знайдено картинку: {src}")
                        target_url = src
                        break
            except Exception as e:
                print(f"Помилка при обробці iframe: {e}")
            
            if target_url: break

        # Завантаження файлу
        if target_url:
            print(f"Качаємо з {target_url}")
            session = requests.Session()
            
            # Копіюємо заголовки і куки
            headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}
            session.headers.update(headers)
            for cookie in driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            
            resp = session.get(target_url)
            if resp.status_code == 200:
                file_content = resp.content
                print("Успішно завантажено")
            else:
                print(f"Помилка завантаження: {resp.status_code}")
        else:
            print("Не знайдено посилання на картинку")

    except Exception as e:
        print(f"Критична помилка Selenium: {e}")
    finally:
        if driver:
            print("Закриваємо Chrome")
            driver.quit()
            
    return file_content, found_date_str

async def update_schedule_database():
    # Отримуємо картинку і дату з сайту
    result = await asyncio.to_thread(download_original_image)
    if not result: 
        return False
        
    image_bytes, found_date = result
    
    if not image_bytes: return False
    
    # Зберігаємо оригінал
    with open("schedule_screenshot.png", "wb") as f:
        f.write(image_bytes)
    
    # Визначаємо дату: або ту що знайшли на сайті, або поточну Київську
    if found_date:
        target_date = found_date
    else:
        # Якщо на сайті дати нема, беремо "Сьогодні" по Києву
        target_date = datetime.now(KYIV_TZ).strftime("%Y-%m-%d")
        print(f"⚠️ Дату на сайті не знайдено, використовуємо системну: {target_date}")

    print(f"Аналіз точок для дати: {target_date}")
    # Парсимо
    parsed_data = image_parser.parse_image(image_bytes, debug=True)
    
    if parsed_data:
        # Зберігаємо в базу під конкретною датою
        await database.save_schedule_cache(target_date, parsed_data)
        print(f"Апдейт бази успішний на {target_date}")
        return True
    return False

async def get_schedule_image_url():
    if os.path.exists("schedule_screenshot.png"):
        return FSInputFile("schedule_screenshot.png")
    return None