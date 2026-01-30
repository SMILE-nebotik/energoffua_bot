import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def parse_lviv_text_data(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    text = soup.get_text(separator=' ')
    
    # 1. Шукаємо дату (наприклад: "на 30.01.2026")
    target_date = None
    # Покращена регулярка для дати
    date_match = re.search(r"відключень\s+на\s+(\d{2}\.\d{2}\.\d{4})", text)
    if date_match:
        d, m, y = date_match.group(1).split('.')
        target_date = f"{y}-{m}-{d}"
        logger.info(f"[LvivParser] Found date in text: {target_date}")

    # 2. Час оновлення
    update_time = None
    time_match = re.search(r"станом\s+на\s+(\d{2}:\d{2})", text)
    if time_match:
        update_time = time_match.group(1)

    schedule = {}
    # 3. Парсимо групи 1.1 - 6.2
    # Шукаємо рядки: "Група X.X. Електроенергії немає з ... до ..."
    lines = re.findall(r"(Група\s+\d\.\d\.[^.]+)", text)
    
    for line in lines:
        group_match = re.search(r"Група\s+(\d\.\d)", line)
        if not group_match: continue
            
        group_id = group_match.group(1)
        daily_schedule = ["on"] * 48 
        
        if "немає" in line.lower():
            intervals = re.findall(r"(\d{2}:\d{2})\s+до\s+(\d{2}:\d{2})", line)
            for start_str, end_str in intervals:
                try:
                    # Перетворюємо час у індекси (0-47)
                    s_h, s_m = map(int, start_str.split(':'))
                    e_h, e_m = map(int, end_str.split(':'))
                    
                    start_idx = s_h * 2 + (1 if s_m >= 30 else 0)
                    end_idx = e_h * 2 + (1 if e_m >= 30 else 0)
                    
                    # Заповнюємо проміжок "відсутністю світла"
                    for i in range(start_idx, min(end_idx, 48)):
                        daily_schedule[i] = "off"
                except: continue
        
        schedule[group_id] = daily_schedule

    return target_date, update_time, schedule