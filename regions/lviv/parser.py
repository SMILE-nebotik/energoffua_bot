import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def parse_lviv_html(html_content):
    """
    Parses the Lvivoblenergo HTML content.
    Extracts schedule data from text descriptions using Regular Expressions.
    """
    soup = BeautifulSoup(html_content, 'lxml')
    schedule = {}
    
    # Find all text nodes containing "Група" followed by a number (e.g., "Група 1.1")
    # This targets the specific lines visible in your screenshot.
    lines = soup.find_all(string=re.compile(r"Група\s+\d+\.\d+"))
    
    if not lines:
        logger.warning("[Lviv Parser] No group text lines found in HTML.")
        return {}

    for line in lines:
        text = line.strip()
        
        # Extract group ID (e.g., '1.1', '2.1')
        group_match = re.search(r"Група\s+(\d+\.\d+)", text)
        if not group_match:
            continue
            
        group_id = group_match.group(1)
        
        # Initialize schedule: default to 'yes' (electricity is ON) for all 24 hours
        group_data = {f"{h:02d}-{(h+1):02d}": "yes" for h in range(24)}
        
        # Regex to find time ranges like "08:00 до 10:00" or "20:30 до 22:30"
        # Matches: HH:MM + " до " + HH:MM
        time_slots = re.findall(r"(\d{2}:\d{2})\s+до\s+(\d{2}:\d{2})", text)
        
        for start_str, end_str in time_slots:
            try:
                # Parse start time
                start_hour = int(start_str.split(':')[0])
                
                # Parse end time
                end_hour = int(end_str.split(':')[0])
                end_min = int(end_str.split(':')[1])

                # Determine the range of hours affected.
                # Logic: If the outage ends at XX:30 (minutes > 0), 
                # we count that full hour as an outage hour.
                range_end = end_hour + (1 if end_min > 0 else 0)

                for h in range(start_hour, range_end):
                    # Ensure hour is within valid 0-23 range
                    if 0 <= h < 24:
                        hour_key = f"{h:02d}-{(h+1):02d}"
                        group_data[hour_key] = "no"  # Set status to 'no' (outage)
                        
            except ValueError as e:
                logger.error(f"[Lviv Parser] Error parsing time slot in group {group_id}: {e}")
        
        # Note: If the text contains "Електроенергія є" (Electricity available),
        # the loop above won't find time slots, so the schedule remains all 'yes'.
        
        schedule[group_id] = group_data

    logger.info(f"[Lviv Parser] Successfully parsed {len(schedule)} groups from text.")
    return schedule