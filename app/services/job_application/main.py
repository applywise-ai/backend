"""Module to populate job form."""

import os
import logging
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from app.services.browser import CustomWebDriver
from app.services.job_application.portals import Lever, Greenhouse, Ashby, Jobvite, Workable
from app.db.supabase import supabase_manager
from app.schemas.application import FormSectionType, QuestionType
from app.services.job_application.types import JobPortal

load_dotenv()


class JobApplicationService:
    """Service class for handling job applications across different portals."""
    
    def __init__(self, driver: CustomWebDriver, profile: dict = None, job_description: str = None):
        """Initialize the job application service with a driver and user profile."""
        self.driver = driver
        self.profile = profile or {}
        self.job_description = job_description
        self.logger = logging.getLogger(__name__)

        self.temp_file_paths = []
        
        # Portal configuration - easily extensible
        self.portal_config = {
            'lever.co': {
                'name': JobPortal.LEVER,
                'portal_class': Lever,
                'transform': lambda url, query_params: url if "/apply" in url else f"{url.rstrip('/')}/apply{query_params}"
            },
            'job-boards.greenhouse.io': {
                'name': JobPortal.GREENHOUSE,
                'portal_class': Greenhouse,
                'transform': lambda url, query_params: url if '#app' in url else f"{url}{query_params}#app"
            },
            'greenhouse.io': {
                'name': JobPortal.OLD_GREENHOUSE,
                'portal_class': Greenhouse,
                'transform': lambda url, query_params: url if '#app' in url else f"{url}{query_params}#app"
            },
            'ashbyhq.com': {
                'name': JobPortal.ASHBY,
                'portal_class': Ashby,
                'transform': lambda url, query_params: url if "/application" in url else f"{url.rstrip('/')}/application{query_params}"
            },
            # 'jobvite.com': {
            #     'name': 'Jobvite',
            #     'portal_class': Jobvite,
            #     'transform': lambda url: url if '/apply' in url else f"{url.rstrip('/')}/apply"
            # },
            'workable.com': {
                'name': JobPortal.WORKABLE,
                'portal_class': Workable,
                'transform': lambda url, query_params: f"{url.rstrip('/')}/apply{query_params}"
            }
        }
    

    
    def _wait_for_page_load(self):
        """Wait for the page to load completely."""
        self.logger.info("Waiting for page to load...")
        try:  
            
            self.driver.wait_and_find_elements(By.TAG_NAME, "input", timeout=10)
        except TimeoutException:
            self.logger.warning("Page loaded but no body element found")
            return False
        
        return True
    
    def get_portal_info(self, url: str):
        """
        Get portal information including type and direct application URL.
        
        Args:
            url (str): The job URL
            
        Returns:
            dict: Contains 'portal_class', 'application_url', and 'portal_name'
        """
        # Clean URL by removing query parameters
        if '?' in url:
            clean_url, query_params = url.split('?', 1)
        elif '&' in url:
            clean_url, query_params = url.split('&', 1)
        else:
            clean_url, query_params = url, None
        
        query_params = f"?{query_params}" if query_params else "" # Add back the query params
        
        # Find matching portal configuration
        for domain, config in self.portal_config.items():
            if domain in clean_url:
                return {
                    'portal_class': config['portal_class'],
                    'application_url': config['transform'](clean_url, query_params),
                    'portal_name': config['name']
                }
        
        # Unknown portal
        return {
            'portal_class': None,
            'application_url': clean_url,
            'portal_name': 'Unknown'
        }
    
    def apply(self, job_url: str, overrided_answers: dict = None) -> list:
        """
        Apply for a job at the given URL.
        
        Args:
            job_url (str): The URL of the job to apply for
            overrided_answers (dict): A dictionary of question IDs and FormQuestion objects to override the answers
        Returns:
            list: List of form questions if application was successful, None otherwise
            str: Portal name if application was successful, None otherwise
        """
        try:
            self.logger.info(f"Starting job application for URL: {job_url}")
            
            # Get portal information and direct application URL
            portal_info = self.get_portal_info(job_url)
            application_url = portal_info['application_url']
            portal_class = portal_info['portal_class']
            portal_name = portal_info['portal_name']
            
            self.logger.info(f"Portal detected: {portal_name}")
            if application_url != job_url:
                self.logger.info(f"Direct application URL: {application_url}")
            
            # Navigate directly to the application URL
            self.driver.get(application_url)
            
            # Initialize the portal with profile and apply
            if not portal_class:
                self.logger.warning(f"No portal class found for job URL: {job_url}")
                return None
            
            portal = portal_class(self.driver, self.profile, application_url, self.job_description, overrided_answers)

            # Wait for page to load completely
            if not self._wait_for_page_load():
                self.logger.warning("Page unable to load")
                return None

            self._handle_cookie_consent()

            portal.apply()

            if not portal.form_questions:
                self.logger.warning("No form questions found")
                return None

            # Sort form questions by count
            sorted_form_questions = sorted(portal.form_questions.values(), key=lambda x: x['count'])

            for q in sorted_form_questions:
                if 'type' in q and isinstance(q["type"], QuestionType):
                    q["type"] = q["type"].value
                if 'section' in q and isinstance(q["section"], FormSectionType):
                    q["section"] = q["section"].value
                q.pop("element", None)
                q.pop("count", None)

            self.logger.info(f"Successfully prepared application for job: {job_url}")
            
            self.temp_file_paths = portal.temp_file_paths

            # Return the form questions
            return sorted_form_questions, portal_name
            
        except Exception as e:
            self.logger.error(f"Error applying to job {job_url}: {str(e)}")
            return None
    
    def submit(self):
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
                    self.logger.info("Application submitted successfully")
                except ElementClickInterceptedException:
                    # Try JavaScript click if regular click fails
                    self.driver.execute_script("arguments[0].click();", submit_button)
                    self.logger.info("Application submitted successfully using JavaScript click")
                
                # See if we re-routed to a new url
                if self.driver.current_url != self.driver.page_source:
                    self.logger.info("We re-routed to a new url")
                    return True
                else:
                    self.logger.warning("We did not re-routed to a new url")
                    return False

                return True
            else:
                self.logger.warning("No submit button found on the page")
                return False
                
        except TimeoutException:
            self.logger.error("Timeout waiting for page to load when looking for submit button")
            return False
        except Exception as e:
            self.logger.error(f"Error clicking submit button: {str(e)}")
            return False

    def _handle_cookie_consent(self):
        """Handle cookie consent banner on all portals."""
        try:
            self.logger.info("Checking for cookie consent banner on all portals")
            
            # Use known working selector
            selector = "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]"
            
            elements = self.driver.wait_and_find_elements(By.XPATH, selector)
            cookie_button = None
            
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    cookie_button = element
                    break
            
            if cookie_button:
                self.logger.info("Found cookie consent button")
                self.driver.wait_and_click_element(element=cookie_button)
                self.logger.info("Successfully clicked cookie consent button")
            else:
                self.logger.info("No cookie consent banner found - proceeding with application")
        except Exception:
            self.logger.warning("No cookie consent banner found - proceeding anyway")

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
        'workable': "https://apply.workable.com/performyard/j/8147038392"
    }
    
    # Example of how to use with browser pool
    from app.services.browser import browser_pool

    # Get driver from browser pool
    worker_id = "test_worker"
    driver = browser_pool.get_driver(worker_id)
    
    try:
        # Create job application service
        from app.db.firestore import firestore_manager
        from Screenshot import Screenshot
        import time

        profile = firestore_manager.get_profile('fYDy4dNReTN6ng8qWnD5iLJTSrH2')
        job = supabase_manager.get_job_by_id("li-4260290879")
        print(job.get('description'))

        job_service = JobApplicationService(driver, profile, job.get('description'))
        
        # # test screenshot
        # driver.get(job.get('job_url'))
        # time.sleep(5)
        # ss = Screenshot(driver)

   
        # ss.capture_full_page(
        #     output_path="fullpage.png",
        # )

        # # Apply to a job
        # answers = {
        #     'School2': 'University of Toronto',
        #     'Your website URL1': "https://mynamejeff.com"
        # }

        test = "https://boards.greenhouse.io/embed/job_app?token=6709289&gh_src=8c01b2f01&source=LinkedIn&urlHash=sxPx"
        # print(job_service.get_portal_info(test))
        old_greenhouse = "https://boards.greenhouse.io/embed/job_app?token=6709289&gh_src=Simplify&source=LinkedIn&urlHash=sxPx&utm_source=Simplify"
        questions, portal_name = job_service.apply('https://jobs.ashbyhq.com/airapps/b1b7acf5-af91-46d9-9db5-8dddc9facf95?src=LinkedIn&urlHash=RH3W')
        import json

        formatted = json.dumps(questions, indent=2, default=str)
        print(formatted)
    finally:
        # Release driver back to pool
        browser_pool.release_driver(worker_id)
