# конфіг фулл бота не комітити добавити в гіт ігнор (неактуал перенесено для безпеки)
import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = "bot_users.db"

admins_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(id_str) for id_str in admins_str.split(",") if id_str.strip()]



