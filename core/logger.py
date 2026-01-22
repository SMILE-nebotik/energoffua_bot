import logging
from logging.handlers import RotatingFileHandler
import os
from core.config import config

def setup_logger():
    log_file = os.path.join(config.BASE_DIR, "bot.log")
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    # хенжлер до 5 мб, зберігає 2 бекапи
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # для консолі
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Налаштовуємо кореневий логер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Очищаємо старі хендлери (щоб не дублювалося при перезапуску)
    root_logger.handlers = []
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    logging.info("Логування налаштовано (RotatingFileHandler)")