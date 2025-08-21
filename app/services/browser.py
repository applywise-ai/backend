import threading
import time
import os
import shutil
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


def get_chrome_binary_path():
    """
    Detect the Chrome binary path based on the environment
    """
    # Common Chrome binary paths for different environments
    chrome_paths = [
        "/usr/bin/google-chrome",  # Docker/Linux (installed via apt)
        "/usr/bin/google-chrome-stable",  # Alternative Linux path
        "/usr/bin/chromium-browser",  # Chromium fallback
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",  # Windows
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",  # Windows 32-bit
    ]
    
    # Check if we can find chrome in PATH
    chrome_in_path = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium-browser")
    if chrome_in_path:
        logger.info(f"Found Chrome in PATH: {chrome_in_path}")
        return chrome_in_path
    
    # Check common installation paths
    for path in chrome_paths:
        if os.path.exists(path):
            logger.info(f"Found Chrome at: {path}")
            return path
    
    # If production environment (Docker), expect Chrome to be installed
    if settings.is_production or os.path.exists("/.dockerenv"):
        logger.warning("Running in production/Docker but Chrome not found at expected paths")
        # Return None to let undetected-chromedriver handle it
        return None
    
    logger.warning("Chrome binary not found, letting undetected-chromedriver auto-detect")
    return None


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

            # Get Chrome binary path based on environment
            chrome_binary = get_chrome_binary_path()
            
            # Initialize with detected Chrome path
            if chrome_binary:
                logger.info(f"Initializing Chrome with binary: {chrome_binary}")
                super().__init__(options=options, headless=headless, version_main=None, browser_executable_path=chrome_binary)
            else:
                logger.info("Initializing Chrome with auto-detection")
                super().__init__(options=options, headless=headless, version_main=None)
            
            self.apply_stealth()
            
        except Exception as e:
            logger.error(f"Failed to initialize undetected-chromedriver: {e}")
            raise

    def _get_custom_chrome_options(self, headless=None):
        """Set up Chrome options for undetected Chrome"""
        chrome_options = uc.ChromeOptions()
        
        # Basic options (undetected-chromedriver handles most stealth automatically)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Additional options for Docker/production environments
        if settings.is_production or os.path.exists("/.dockerenv"):
            logger.info("Adding Docker-specific Chrome options")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-features=TranslateUI")
            chrome_options.add_argument("--disable-ipc-flooding-protection")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--remote-debugging-port=9222")

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

    def wait_for_options_to_change(self, selector: str, initial_count: int, timeout: int = 5):
        """Wait for options to change after typing in a search field."""
        try:
            wait = WebDriverWait(self, timeout)
            wait.until(lambda driver: len(driver.find_elements(By.CSS_SELECTOR, selector)) != initial_count)
            return self.find_elements(By.CSS_SELECTOR, selector)
        except:
            return self.find_elements(By.CSS_SELECTOR, selector)

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
        self._shutdown_event = threading.Event()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_inactive_drivers, daemon=True)
        self.cleanup_thread.start()

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
        while not self._shutdown_event.is_set():
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
                
                # Wait for 60 seconds or until shutdown is signaled
                self._shutdown_event.wait(60)
                
            except Exception as e:
                logger.error(f"Error in driver cleanup: {e}")
                if not self._shutdown_event.is_set():
                    self._shutdown_event.wait(60)
        
        logger.info("Cleanup thread shutting down")
    
    def close_all(self):
        """Close all drivers and shutdown cleanup thread"""
        logger.info("Shutting down browser pool...")
        
        # Signal shutdown to cleanup thread
        self._shutdown_event.set()
        
        # Wait for cleanup thread to finish (with timeout)
        if self.cleanup_thread.is_alive():
            logger.info("Waiting for cleanup thread to finish...")
            self.cleanup_thread.join(timeout=5)
            if self.cleanup_thread.is_alive():
                logger.warning("Cleanup thread did not finish within timeout")
        
        # Close all drivers
        with self.driver_lock:
            driver_count = len(self.drivers)
            if driver_count > 0:
                logger.info(f"Closing {driver_count} remaining drivers...")
                
                for worker_id in list(self.drivers.keys()):
                    try:
                        self.close_driver(worker_id)
                    except Exception as e:
                        logger.error(f"Error closing driver for worker {worker_id}: {e}")
                        # Force remove from dict even if close failed
                        if worker_id in self.drivers:
                            del self.drivers[worker_id]
                        if worker_id in self.last_used:
                            del self.last_used[worker_id]
            else:
                logger.info("No active drivers to close")
        
        logger.info("Browser pool shutdown complete")


# Global browser pool instance
browser_pool = BrowserPool() 