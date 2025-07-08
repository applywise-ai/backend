"""Module to populate job form."""

import os
import logging
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException, ElementClickInterceptedException
from app.services.browser import CustomWebDriver
from app.services.job_application.portals import Lever, Greenhouse, Ashby, Jobvite, Workable

logger = logging.getLogger(__name__)
load_dotenv()


class JobApplicationService:
    """Service class for handling job applications across different portals."""
    
    def __init__(self, driver: CustomWebDriver, profile: dict = None):
        """Initialize the job application service with a driver and user profile."""
        self.driver = driver
        self.profile = profile or {}
        
        # Validate required environment variables
        self._validate_environment()
        
        # Portal configuration - easily extensible
        self.portal_config = {
            'lever.co': {
                'name': 'Lever',
                'portal_class': Lever,
                'transform': lambda url: url if "/apply" in url else f"{url.rstrip('/')}/apply"
            },
            'greenhouse.io': {
                'name': 'Greenhouse',
                'portal_class': Greenhouse,
                'transform': lambda url: url if '#app' in url else f"{url}#app"
            },
            'ashbyhq.com': {
                'name': 'Ashby',
                'portal_class': Ashby,
                'transform': lambda url: url if "/application" in url else f"{url.rstrip('/')}/application"
            },
            'jobvite.com': {
                'name': 'Jobvite',
                'portal_class': Jobvite,
                'transform': lambda url: url if '/apply' in url else f"{url.rstrip('/')}/apply"
            },
            'workable.com': {
                'name': 'Workable',
                'portal_class': Workable,
                'transform': lambda url: f"{url.rstrip('/')}/apply"
            }
        }
    
    def _validate_environment(self):
        """Validate that required environment variables are set."""
        required_env_vars = {
            'OPENAI_API_KEY': 'OpenAI API key is required for AI-powered form filling'
        }
        
        missing_vars = []
        for var_name, description in required_env_vars.items():
            if not os.getenv(var_name):
                missing_vars.append(f"{var_name}: {description}")
        
        if missing_vars:
            error_msg = "Missing required environment variables:\n" + "\n".join(f"  - {var}" for var in missing_vars)
            logger.error(error_msg)
            raise EnvironmentError(error_msg)
        
        # Set OpenAI API key
        os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
        logger.info("Environment variables validated successfully")
    
    def _wait_for_page_load(self):
        """Wait for the page to load completely."""
        logger.info("Waiting for page to load...")
            
        success = self.driver.wait_and_find_element(By.TAG_NAME, "input", timeout=2)
        if success:
            logger.info("Page loaded successfully")
        else:
            logger.warning("Page loaded but no body element found")
    
    def get_portal_info(self, url: str):
        """
        Get portal information including type and direct application URL.
        
        Args:
            url (str): The job URL
            
        Returns:
            dict: Contains 'portal_class', 'application_url', and 'portal_name'
        """
        # Find matching portal configuration
        for domain, config in self.portal_config.items():
            if domain in url:
                return {
                    'portal_class': config['portal_class'],
                    'application_url': config['transform'](url),
                    'portal_name': config['name']
                }
        
        # Unknown portal
        return {
            'portal_class': None,
            'application_url': url,
            'portal_name': 'Unknown'
        }
    
    def apply(self, job_url: str, submit: bool = False) -> bool:
        """
        Apply for a job at the given URL.
        
        Args:
            job_url (str): The URL of the job to apply for
            submit (bool): Whether to submit the application
            
        Returns:
            bool: True if application was successful, False otherwise
        """
        try:
            logger.info(f"Starting job application for URL: {job_url}")
            
            # Get portal information and direct application URL
            portal_info = self.get_portal_info(job_url)
            application_url = portal_info['application_url']
            portal_class = portal_info['portal_class']
            portal_name = portal_info['portal_name']
            
            logger.info(f"Portal detected: {portal_name}")
            if application_url != job_url:
                logger.info(f"Direct application URL: {application_url}")
            
            # Navigate directly to the application URL
            self.driver.get(application_url)
            
            # Initialize the portal with profile and apply
            if portal_class:
                portal = portal_class(self.driver, self.profile)

                # Wait for page to load completely
                self._wait_for_page_load()

                portal.apply()

            if submit:
                submit_success = self._submit_application()
                if submit_success:
                    logger.info(f"Successfully submitted application for job: {job_url}")
                else:
                    logger.warning(f"Application prepared but submission failed for job: {job_url}")
                    return False
            else:
                logger.info(f"Successfully prepared application for job: {job_url}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying to job {job_url}: {str(e)}")
            return False
    
    def _submit_application(self):
        """Dynamically find and click submit button."""
        try:
            # Common submit button selectors and text patterns
            submit_selectors = [
                # By text content (most common)
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit application')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send application')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'complete application')]",
                
                # By input/button attributes
                "//input[@type='submit' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
                "//button[@type='submit']",
                "//input[@type='submit']",
                
                # By common class names
                "//*[contains(@class, 'submit') and (self::button or self::input)]",
                "//*[contains(@class, 'apply') and (self::button or self::input)]",
                
                # By id attributes
                "//*[contains(@id, 'submit') and (self::button or self::input)]",
                "//*[contains(@id, 'apply') and (self::button or self::input)]"
            ]
            
            submit_button = None
            
            # Try each selector until we find a clickable button
            for selector in submit_selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, selector)
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            submit_button = button
                            break
                    if submit_button:
                        break
                except Exception:
                    continue
            
            if submit_button:
                # Scroll to button and click
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
                
                # Try to click using different methods
                try:
                    self.driver.wait_and_click_element(element=submit_button)
                    logger.info("Application submitted successfully")
                except ElementClickInterceptedException:
                    # Try JavaScript click if regular click fails
                    self.driver.execute_script("arguments[0].click();", submit_button)
                    logger.info("Application submitted successfully using JavaScript click")
                
                return True
            else:
                logger.warning("No submit button found on the page")
                return False
                
        except TimeoutException:
            logger.error("Timeout waiting for page to load when looking for submit button")
            return False
        except Exception as e:
            logger.error(f"Error clicking submit button: {str(e)}")
            return False

# Example usage and test URLs (for development/testing)
if __name__ == "__main__":
    # Test URLs for different portals
    test_urls = {
        'lever': "https://jobs.lever.co/Eudia/7bc53322-dd7b-417e-a05e-ba543662e14c",
        'lever_2': "https://jobs.lever.co/palantir/f362d7aa-360d-4059-ab38-f482742693b3/apply?lever-source=LinkedIn",
        'greenhouse_new': "https://job-boards.greenhouse.io/clockworksystems/jobs/4066040004?gh_src=8e2949a04us",
        'greenhouse': "https://boards.greenhouse.io/embed/job_app?token=4054592006&utm_source=jobright",
        'ashby': "https://jobs.ashbyhq.com/comulate/4d5a3632-2812-4ab0-b3ad-ca6cf6083348/application?utm_source=PyDKyZpboQ",
        'ashby_2': "https://jobs.ashbyhq.com/baseten/ae64d1d4-7b0a-4be4-8d77-7f5ce63849a7/application?utm_source=worNde4l4L",
        'workable': "https://apply.workable.com/performyard/j/8147038392",
        'jobvite': "https://jobs.jobvite.com/example-company/job/example123"
    }
    
    # Example of how to use with browser pool
    from app.services.browser import browser_pool

    # Get driver from browser pool
    worker_id = "test_worker"
    driver = browser_pool.get_driver(worker_id)
    
    try:
        # Create job application service
        from app.db.firestore import firestore_manager

        profile = firestore_manager.get_profile('fYDy4dNReTN6ng8qWnD5iLJTSrH2')
        job_service = JobApplicationService(driver, profile)

        # Apply to a job
        success = job_service.apply(test_urls['greenhouse_new'])

        
    finally:
        # Release driver back to pool
        browser_pool.release_driver(worker_id)
