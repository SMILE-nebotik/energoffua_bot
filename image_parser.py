import cv2
import numpy as np
from PIL import Image
import pytesseract
import io


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Верхня таблиця
TOP_TABLE_START_X = 205
TOP_TABLE_START_Y = 447

# Нижня таблиця
BOT_TABLE_START_X = 205
BOT_TABLE_START_Y = 1337

# шаг по x i y 
STEP_X = 65 
STEP_Y = 61

# дата над таблицею (доробити)
DATE_AREA = (50, 50, 1500, 400) 

def get_date_from_image(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes))


        date_crop = img.crop(DATE_AREA)

        text = pytesseract.image_to_string(date_crop, lang='ukr+eng')
        return text
    except Exception as e:
        print(f"ПОмиклка орс {e}")
        return None

def parse_image(image_bytes, debug=False):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None: return None

    schedule = {}
    
    # кроки перевірки
    LOCAL_STEP_X = 65
    LOCAL_STEP_Y = 61

    for row in range(12):
        group_num = (row // 2) + 1
        subgroup_num = (row % 2) + 1
        group_name = f"{group_num}.{subgroup_num}"
        row_data = []
        
        for col in range(48):
            if col < 24:
                start_x, start_y = TOP_TABLE_START_X, TOP_TABLE_START_Y
                current_col = col
            else:
                start_x, start_y = BOT_TABLE_START_X, BOT_TABLE_START_Y
                current_col = col - 24
            
            # кроки з корекці\ю
            x = int(start_x + (current_col * LOCAL_STEP_X))
            y = int(start_y + (row * LOCAL_STEP_Y))
            
            if y >= img.shape[0] or x >= img.shape[1]:
                row_data.append('unknown')
                continue

            pixel = img[y, x]
            b, g, r = pixel
            
            # блок під перевірку кольору
            brightness = (int(r) + int(g) + int(b)) / 3
            
            # визначення статусу
            if brightness > 160:
                status = 'on'
                color = (0, 255, 0)
            else:
                status = 'off'
                color = (0, 0, 255)

            row_data.append(status)
            
            if debug:
                cv2.circle(img, (x, y), 8, color, -1)
                
        schedule[group_name] = row_data
        
    if debug:
        cv2.imwrite("debug_grid.png", img)
        
    return schedule