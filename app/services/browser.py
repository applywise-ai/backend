import threading
import time
from typing import Dict
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from selenium_stealth import stealth
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class CustomWebDriver(uc.Chrome):
    """Custom WebDriver class that extends the Undetected Chrome WebDriver with additional functionality."""
    
    def __init__(self, headless=None, options=None, service=None):
        """Initialize the Custom Undetected Chrome WebDriver with fallback"""
        try:
            if options is None:
                options = self._get_custom_chrome_options(headless)
                
            # Determine headless mode
            if headless is None:
                headless = settings.HEADLESS_BROWSER

            super().__init__(options=options, headless=headless, version_main=137, browser_executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            self.apply_stealth()
            
        except Exception as e:
            logger.warning(f"Failed to initialize undetected-chromedriver: {e}")

    def _get_custom_chrome_options(self, headless=None):
        """Set up Chrome options for undetected Chrome"""
        chrome_options = uc.ChromeOptions()
        
        # Basic options (undetected-chromedriver handles most stealth automatically)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Disable images and CSS for faster loading
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        return chrome_options

    def apply_stealth(self):
        """Apply stealth using Selenium Stealth"""
        stealth(self,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)

    def wait_and_find_element(self, by=By.ID, value=None, timeout=2):
        """Wait until the element is visible, then return it."""
        wait = WebDriverWait(self, timeout, ignored_exceptions=[StaleElementReferenceException])
        element = wait.until(EC.presence_of_element_located((by, value)))
        return element

    def wait_and_find_elements(self, by=By.ID, value=None, timeout=2):
        """Wait until at least one element is visible, then return all."""
        wait = WebDriverWait(self, timeout, ignored_exceptions=[StaleElementReferenceException])
        wait.until(EC.presence_of_element_located((by, value)))
        elements = super().find_elements(by, value)
        return elements
    
    def wait_and_click_element(self, element=None, by=By.ID, timeout=2):
        """Wait until the element is clickable, then click it."""
        if element is not None:
            # If element is provided, scroll to it and click
            super().execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", element)
            wait = WebDriverWait(self, timeout)
            wait.until(EC.element_to_be_clickable(element))
            element.click()

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
        
        self._initialized = True
        
        self.drivers: Dict[str, CustomWebDriver] = {}
        self.driver_lock = threading.Lock()
        self.last_used: Dict[str, float] = {}
        
        # Start cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_inactive_drivers, daemon=True)
        cleanup_thread.start()
    
    def get_chrome_options(self) -> uc.ChromeOptions:
        """Configure Chrome options for undetected automation"""
        options = uc.ChromeOptions()
        
        # Basic options (undetected-chromedriver handles most stealth automatically)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        # Disable images and CSS for faster loading
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        options.add_experimental_option("prefs", prefs)
        
        return options

    def get_driver(self, worker_id: str) -> CustomWebDriver:
        """Get or create a Custom Chrome driver for the worker"""
        with self.driver_lock:
            if worker_id not in self.drivers:
                logger.info(f"Creating new Custom Chrome driver for worker {worker_id}")
                
                # Create CustomWebDriver with stealth capabilities
                driver = CustomWebDriver()
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