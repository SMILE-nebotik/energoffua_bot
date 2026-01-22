import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(id_str) for id_str in os.getenv("ADMIN_IDS", "").split(",") if id_str.strip()]
    DB_NAME = "bot_database.db"
    
    # профілі для селеніума
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CHROME_PROFILE_PATH = os.path.join(BASE_DIR, "chrome_profile")
    TESSERACT_CMD = "/usr/bin/tesseract"

config = Config()