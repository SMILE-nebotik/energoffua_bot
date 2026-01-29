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
        daily_schedule = ["on"] * 24 # По замовчуванню світло є
        
        if "немає" in line.lower():
            # Шукаємо всі проміжки часу
            intervals = re.findall(r"(\d{2}:\d{2})\s+до\s+(\d{2}:\d{2})", line)
            for start_str, end_str in intervals:
                try:
                    s_h = int(start_str.split(':')[0])
                    e_h = int(end_str.split(':')[0])
                    e_m = int(end_str.split(':')[1])
                    
                    # Якщо кінець 22:30, то 22-га година теж "off"
                    end_hour = e_h + (1 if e_m > 0 else 0)
                    
                    for h in range(s_h, min(end_hour, 24)):
                        daily_schedule[h] = "off"
                except: continue
        
        schedule[group_id] = daily_schedule

    return target_date, update_time, schedule