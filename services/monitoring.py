import psutil
import shutil
import logging
from aiogram import Bot
from core.config import config

logger = logging.getLogger(__name__)

async def system_health_check(bot: Bot):
    """Перевіряє стан системи (Диск, RAM)."""
    # check disk
    total, used, free = shutil.disk_usage("/")
    free_gb = free // (2**30)
    
    # check ram
    memory = psutil.virtual_memory()
    available_mb = memory.available // (2**20)

    logger.info(f"[Health] RAM: {available_mb}MB free | Disk: {free_gb}GB free")

    # if 1gb or 100 ram
    if free_gb < 1 or available_mb < 100:
        msg = (
            f"**CRITICAL WARNING**\n"
            f"Low system resources!\n"
            f"Disk Free: {free_gb}GB\n"
            f"RAM Free: {available_mb}MB"
        )
        logger.warning(f"[Health] {msg}")
        
        try:
            # await bot.send_message
            pass 
        except:
            pass