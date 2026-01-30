import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def parse_lviv_text_data(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    text = soup.get_text(separator=' ')
    
    target_date = None
    date_match = re.search(r"відключень\s+на\s+(\d{2}\.\d{2}\.\d{4})", text)
    if date_match:
        try:
            d, m, y = date_match.group(1).split('.')
            target_date = f"{y}-{m}-{d}"
        except ValueError:
            logger.error(f"[LvivParser] Date parsing error: {date_match.group(1)}")

    update_time = None
    time_match = re.search(r"станом\s+на\s+(\d{2}[:.]\d{2})", text)
    if time_match:
        update_time = time_match.group(1).replace('.', ':')

    schedule = {}

    chunks = re.split(r'(?=Група\s+\d\.\d)', text)
    
    for chunk in chunks:
        group_match = re.search(r"Група\s+(\d\.\d)", chunk)
        if not group_match:
            continue
            
        group_id = group_match.group(1)
        daily_schedule = ["on"] * 48 
        
        if "немає" in chunk.lower() or "вимкнен" in chunk.lower() or "відключ" in chunk.lower():
            intervals = re.findall(r"(\d{1,2}[:.]\d{2})\s*(?:до|-|–)\s*(\d{1,2}[:.]\d{2})", chunk)
            
            for start_str, end_str in intervals:
                try:
                    s_h, s_m = map(int, start_str.replace('.', ':').split(':'))
                    e_h, e_m = map(int, end_str.replace('.', ':').split(':'))

                    start_idx = s_h * 2 + (1 if s_m >= 30 else 0)
                    end_idx = e_h * 2 + (1 if e_m >= 30 else 0)
                    
                    for i in range(start_idx, min(end_idx, 48)):
                        daily_schedule[i] = "off"
                except Exception as e:
                    logger.warning(f"[LvivParser] Error parsing interval {start_str}-{end_str}: {e}")
                    continue
        
        schedule[group_id] = daily_schedule

    return target_date, update_time, schedule