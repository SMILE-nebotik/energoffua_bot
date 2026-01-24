import os
import shutil
import logging
from datetime import datetime, timedelta
from core.config import config

logger = logging.getLogger(__name__)

BACKUP_DIR = os.path.join(config.BASE_DIR, "backups")

async def backup_database():
    # create backup directory if it doesn't exist
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    db_path = os.path.join(config.BASE_DIR, "database.db")
    if not os.path.exists(db_path):
        logger.warning("[Backup] Database file not found.")
        return

    # format backup filename with current date
    filename = f"backup_{datetime.now().strftime('%Y-%m-%d')}.db"
    backup_path = os.path.join(BACKUP_DIR, filename)

    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"[Backup] Success: {filename}")
        
        # delete old backups
        cleanup_old_backups()
    except Exception as e:
        logger.error(f"[Backup] Failed: {e}")

def cleanup_old_backups():
    #create beckup latest 7 days
    retention_days = 7
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    for filename in os.listdir(BACKUP_DIR):
        file_path = os.path.join(BACKUP_DIR, filename)
        if os.path.isfile(file_path):
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_time < cutoff_date:
                os.remove(file_path)
                logger.info(f"[Backup] Deleted old backup: {filename}")