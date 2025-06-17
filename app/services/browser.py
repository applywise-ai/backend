import threading
import time
import os
import glob
from typing import Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class BrowserPool:
    """Singleton browser pool to manage persistent Chrome drivers"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.drivers: Dict[str, webdriver.Chrome] = {}
        self.driver_lock = threading.Lock()
        self.last_used: Dict[str, float] = {}
        self._initialized = True
        
        # Start cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_inactive_drivers, daemon=True)
        cleanup_thread.start()
    
    def get_chrome_options(self) -> Options:
        """Configure Chrome options for automation"""
        options = Options()
        
        if settings.HEADLESS_BROWSER:
            options.add_argument("--headless")
        
        # Performance and stability options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--window-size=1920,1080")
        
        # Disable images and CSS for faster loading
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        options.add_experimental_option("prefs", prefs)
        
        return options
    
    def _get_chromedriver_path(self) -> str:
        """Get the correct ChromeDriver path, handling macOS permission issues"""
        try:
            driver_path = ChromeDriverManager().install()
            
            # Check if webdriver-manager returned a valid executable
            if self._is_valid_executable(driver_path):
                return driver_path
            
            # Find the actual chromedriver in the same directory
            driver_dir = os.path.dirname(driver_path)
            chromedriver_path = os.path.join(driver_dir, "chromedriver")
            
            if os.path.isfile(chromedriver_path) and self._is_valid_executable(chromedriver_path):
                return chromedriver_path
            
            # If not executable, try to fix permissions
            if os.path.isfile(chromedriver_path):
                try:
                    os.chmod(chromedriver_path, 0o755)
                    if self._is_valid_executable(chromedriver_path):
                        logger.info(f"Fixed permissions for chromedriver: {chromedriver_path}")
                        return chromedriver_path
                except Exception as e:
                    logger.error(f"Failed to fix permissions: {e}")
            
            # Fallback to original path
            return driver_path
            
        except Exception as e:
            logger.error(f"Error getting chromedriver path: {e}")
            raise
    
    def _is_valid_executable(self, path: str) -> bool:
        """Check if file is a valid executable binary"""
        if not (os.path.isfile(path) and os.access(path, os.X_OK)):
            return False
        
        try:
            with open(path, 'rb') as f:
                header = f.read(4)
                # Check for Mach-O executable headers (macOS)
                return header.startswith((b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', 
                                        b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf'))
        except Exception:
            return False

    def get_driver(self, worker_id: str) -> webdriver.Chrome:
        """Get or create a Chrome driver for the worker"""
        with self.driver_lock:
            if worker_id not in self.drivers:
                logger.info(f"Creating new Chrome driver for worker {worker_id}")
                
                # Get the correct ChromeDriver path
                chromedriver_path = self._get_chromedriver_path()
                service = Service(chromedriver_path)
                
                # Create driver with options
                options = self.get_chrome_options()
                driver = webdriver.Chrome(service=service, options=options)
                driver.set_page_load_timeout(settings.BROWSER_TIMEOUT)
                
                self.drivers[worker_id] = driver
            
            # Update last used time
            self.last_used[worker_id] = time.time()
            return self.drivers[worker_id]
    
    def release_driver(self, worker_id: str):
        """Mark driver as available (but keep it warm)"""
        self.last_used[worker_id] = time.time()
    
    def close_driver(self, worker_id: str):
        """Close and remove a specific driver"""
        with self.driver_lock:
            if worker_id in self.drivers:
                try:
                    self.drivers[worker_id].quit()
                except Exception as e:
                    logger.error(f"Error closing driver for worker {worker_id}: {e}")
                
                del self.drivers[worker_id]
                if worker_id in self.last_used:
                    del self.last_used[worker_id]
                
                logger.info(f"Closed driver for worker {worker_id}")
    
    def _cleanup_inactive_drivers(self):
        """Background thread to cleanup inactive drivers"""
        while True:
            try:
                current_time = time.time()
                inactive_threshold = 30 * 60  # 30 minutes
                
                with self.driver_lock:
                    inactive_workers = [
                        worker_id for worker_id, last_used in self.last_used.items()
                        if current_time - last_used > inactive_threshold
                    ]
                
                for worker_id in inactive_workers:
                    logger.info(f"Cleaning up inactive driver for worker {worker_id}")
                    self.close_driver(worker_id)
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in driver cleanup: {e}")
                time.sleep(60)
    
    def close_all(self):
        """Close all drivers"""
        with self.driver_lock:
            for worker_id in list(self.drivers.keys()):
                self.close_driver(worker_id)


# Global browser pool instance
browser_pool = BrowserPool() 