import cv2
import numpy as np
from PIL import Image
import pytesseract
import io
import re

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- КООРДИНАТИ ---
TOP_TABLE_START_X = 205
TOP_TABLE_START_Y = 447

BOT_TABLE_START_X = 205
BOT_TABLE_START_Y = 1337

# Оновлені кроки (те, що ми підібрали)
LOCAL_STEP_X = 66.0 
LOCAL_STEP_Y = 60.5

# Область дати
DATE_AREA = (0, 0, 1000, 400) 

def get_info_from_image(image_bytes):
    """Витягує дату та час оновлення з картинки через OCR"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        date_crop = img.crop(DATE_AREA)
        text = pytesseract.image_to_string(date_crop, lang='ukr+eng', config='--psm 6')
        text = text.replace("\n", " ")
        print(f"🔍 OCR текст: '{text}'")
        
        found_date = None
        found_time = None

        # Шукаємо дату (dd.mm.yyyy)
        date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
        if date_match:
            found_date = date_match.group(1)

        # Шукаємо час (HH:MM)
        time_match = re.search(r"(\d{2}:\d{2})", text)
        if time_match:
            found_time = time_match.group(1)
            
        return found_date, found_time
        
    except Exception as e:
        print(f"⚠️ Помилка OCR: {e}")
        return None, None

def parse_image(image_bytes, debug=False):
    """Парсить пікселі на графіку і повертає словник {група: [статуси]}"""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None: 
        print("❌ Помилка: не вдалося прочитати зображення")
        return None

    schedule = {}
    
    for row in range(12):
        group_num = (row // 2) + 1
        subgroup_num = (row % 2) + 1
        group_name = f"{group_num}.{subgroup_num}"
        row_data = []
        
        for col in range(48):
            # Визначаємо координати (верхня чи нижня таблиця)
            if col < 24:
                start_x, start_y = TOP_TABLE_START_X, TOP_TABLE_START_Y
                current_col = col
            else:
                start_x, start_y = BOT_TABLE_START_X, BOT_TABLE_START_Y
                current_col = col - 24
            
            # Розрахунок точки
            x = int(start_x + (current_col * LOCAL_STEP_X))
            y = int(start_y + (row * LOCAL_STEP_Y))
            
            # Перевірка меж
            if y >= img.shape[0] or x >= img.shape[1]:
                row_data.append('unknown')
                continue

            # Отримуємо колір пікселя
            pixel = img[y, x]
            b, g, r = pixel
            brightness = (int(r) + int(g) + int(b)) / 3
            
            # Логіка: світло > 160 (білий), темно <= 160 (кольоровий/сірий)
            if brightness > 160: 
                status = 'on'
            else:
                status = 'off'

            row_data.append(status)
        schedule[group_name] = row_data
        
    return schedule