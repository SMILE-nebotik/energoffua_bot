import psutil
import logging
import shutil
import os
import glob

logger = logging.getLogger(__name__)

def kill_zombie_processes():
    """Вбиває старі процеси Chrome, Chromedriver та Xvfb"""
    targets = ['chrome', 'chromedriver', 'Xvfb', 'xvfb']
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Перевіряємо, чи процес містить цільове ім'я
            if any(t in proc.info['name'] for t in targets):
                proc.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    if killed_count > 0:
        logger.info(f"🧹 [Cleaner] Знищено {killed_count} завислих процесів.")

def clean_temp_files():
    """Видаляє тимчасові папки, які створює Undetected Chromedriver"""
    # Зазвичай вони в /tmp/ і починаються на .com.google.Chrome
    temp_patterns = ["/tmp/.com.google.Chrome*", "/tmp/.org.chromium.Chromium*"]
    deleted_count = 0
    
    for pattern in temp_patterns:
        for path in glob.glob(pattern):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"⚠️ Не вдалося видалити {path}: {e}")
                
    if deleted_count > 0:
        logger.info(f"🗑 [Cleaner] Видалено {deleted_count} тимчасових папок Chrome.")