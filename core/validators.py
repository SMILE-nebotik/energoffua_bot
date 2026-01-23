# validation data from user inputs
import re

def is_valid_group(group: str) -> bool:
    pattern = r"^(\d+\.\d+|\d+)$"
    return bool(re.match(pattern, group))

def sanitize_input(text: str) -> str:
    if not text: 
        return ""
    return re.sub(r"[^a-zA-Z0-9\.\-\s]", "", text)