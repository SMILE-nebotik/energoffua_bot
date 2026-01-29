import psutil
import logging
import shutil
import os
import glob
import undetected_chromedriver as uc

logger = logging.getLogger(__name__)

def kill_zombie_processes():
    """Kills lingering Chrome/Chromedriver processes to free up RAM."""
    targets = ['chrome', 'chromedriver', 'Xvfb', 'xvfb']
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and any(t in proc.info['name'] for t in targets):
                proc.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    if killed_count > 0:
        logger.info(f"[Cleaner] Killed {killed_count} hanging processes.")

def clean_temp_files():
    """Cleans up temporary Chrome user data directories."""
    temp_patterns = ["/tmp/.com.google.Chrome*", "/tmp/.org.chromium.Chromium*"]
    deleted_count = 0
    
    for pattern in temp_patterns:
        for path in glob.glob(pattern):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"[Cleaner] Failed to delete {path}: {e}")
                
    if deleted_count > 0:
        logger.info(f"[Cleaner] Deleted {deleted_count} temp Chrome folders.")

def get_safe_driver(version_main=144, headless=False):
    """
    Creates and returns a configured Chrome driver instance.
    
    Args:
        version_main (int): The major version of Chrome installed on the OS.
                            Must match to avoid SessionNotCreatedException.
        headless (bool): Whether to run in headless mode (without UI).
    """
    options = uc.ChromeOptions()
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    if headless:
        options.add_argument("--headless")

    driver = uc.Chrome(
        options=options,
        version_main=version_main
    )
    
    return driver