"""
Screenshot utilities for job applications.
"""

import os
import tempfile
import logging
from typing import Optional
from app.services.job_application.types import JobPortal
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


def take_screenshot(driver, application_id: str, portal_name: JobPortal, submit: bool = False) -> Optional[str]:
    """
    Take a screenshot of the current page using CDP.
    
    Args:
        driver: Selenium WebDriver instance
        application_id: Application identifier for filename
        portal_name: JobPortal enum to determine portal-specific processing
        submit: Boolean to determine if the screenshot is for a submitted application
        
    Returns:
        Filepath to the screenshot if successful, None otherwise
    """
    try:
        from Screenshot import Screenshot
        ss = Screenshot(driver)

        # Define temp filepath
        filename = f"screenshot_{application_id}.png"
        filepath = os.path.join(tempfile.gettempdir(), filename)

        # Take full page screenshot and save to temp dir
        ss.capture_full_page(
            output_path=filepath,
        )

        if submit:
            logger.info(f"Submitted screenshot taken successfully: {filepath}")
            return filepath

        # Portal-specific processing
        if portal_name == JobPortal.GREENHOUSE or portal_name == JobPortal.OLD_GREENHOUSE:
            filepath = _crop_greenhouse_screenshot(driver, filepath, portal_name)
        elif portal_name == JobPortal.ASHBY:
            filepath = _crop_ashby_screenshot(driver, filepath)
        elif portal_name == JobPortal.LEVER:
            filepath = _crop_lever_screenshot(driver, filepath)

        logger.info(f"Screenshot taken successfully: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        return None


def _crop_greenhouse_screenshot(driver, original_filepath: str, portal_name: JobPortal) -> str:
    """
    Crop Greenhouse screenshot to only include the application--container area.
    
    Args:
        driver: Selenium WebDriver instance
        original_filepath: Path to the original screenshot
        
    Returns:
        Filepath to the cropped screenshot
    """
    try:
        from PIL import Image
        
        # Find the application container element
        container_element = None
        try:
            if portal_name == JobPortal.GREENHOUSE:
                container_element = driver.find_element(By.CLASS_NAME, "application--container")
            elif portal_name == JobPortal.OLD_GREENHOUSE:
                container_element = driver.find_element(By.ID, "application")
        except Exception as e:
            logger.warning(f"Could not find application--container element: {e}")
            return original_filepath
        
        if not container_element:
            logger.warning("Container element not found, returning original screenshot")
            return original_filepath
        
        # Get the position and size of the container element
        container_x = container_element.location['x']
        container_y = container_element.location['y']
        container_width = container_element.size['width']
        container_height = container_element.size['height']
        
        # Open the screenshot with PIL
        with Image.open(original_filepath) as img:
            # Get image dimensions
            width, height = img.size
            
            # Crop the image to only include the container area
            # Crop box: (left, top, right, bottom)
            # We'll crop from container_x, container_y to container_x + container_width, container_y + container_height
            cropped_img = img.crop((container_x - 10, container_y - 10, container_x + container_width + 10, container_y + container_height + 10))
            
            # Save the cropped image back to the same file
            cropped_img.save(original_filepath)
            
            logger.info(f"{portal_name} screenshot cropped successfully: {original_filepath}")
            return original_filepath
            
    except Exception as e:
        logger.error(f"Failed to crop {portal_name} screenshot: {e}")
        return original_filepath


def _crop_ashby_screenshot(driver, original_filepath: str) -> str:
    """
    Crop Ashby screenshot to only include the width of the ashby-job-posting-right-pane.
    
    Args:
        driver: Selenium WebDriver instance
        original_filepath: Path to the original screenshot
        
    Returns:
        Filepath to the cropped screenshot
    """
    try:
        from PIL import Image
        
        # Find the ashby-job-posting-right-pane element
        pane_element = None
        try:
            pane_element = driver.find_element(By.CLASS_NAME, "ashby-job-posting-right-pane")
        except Exception as e:
            logger.warning(f"Could not find ashby-job-posting-right-pane element: {e}")
            return original_filepath
        
        if not pane_element:
            logger.warning("Pane element not found, returning original screenshot")
            return original_filepath
        
        # Get the position and size of the pane element
        pane_x = pane_element.location['x']
        pane_y = pane_element.location['y']
        pane_width = pane_element.size['width']
        pane_height = pane_element.size['height']
        
        # Open the screenshot with PIL
        with Image.open(original_filepath) as img:
            # Get image dimensions
            width, height = img.size
            
            # Crop the image to only include the pane area
            # Crop box: (left, top, right, bottom)
            # We'll crop from pane_x, pane_y to pane_x + pane_width, pane_y + pane_height
            cropped_img = img.crop((pane_x - 10, pane_y - 10, pane_x + pane_width + 10, pane_y + pane_height + 10))
            
            # Save the cropped image back to the same file
            cropped_img.save(original_filepath)
            
            logger.info(f"Ashby screenshot cropped successfully: {original_filepath}")
            return original_filepath
            
    except Exception as e:
        logger.error(f"Failed to crop Ashby screenshot: {e}")
        return original_filepath


def _crop_lever_screenshot(driver, original_filepath: str) -> str:
    """
    Crop Lever screenshot to only include the section page-centered application-form area.
    
    Args:
        driver: Selenium WebDriver instance
        original_filepath: Path to the original screenshot
        
    Returns:
        Filepath to the cropped screenshot
    """
    try:
        from PIL import Image
        
        # Find the application form element
        form_element = None
        try:
            form_element = driver.find_element(By.CLASS_NAME, "section.page-centered.application-form")
        except Exception as e:
            logger.warning(f"Could not find section.page-centered.application-form element: {e}")
            return original_filepath
        
        if not form_element:
            logger.warning("Form element not found, returning original screenshot")
            return original_filepath
        
        # Get the position and size of the form element
        form_x = form_element.location['x']
        form_y = form_element.location['y']
        form_width = form_element.size['width']
        form_height = form_element.size['height']
        
        # Open the screenshot with PIL
        with Image.open(original_filepath) as img:
            # Get image dimensions
            width, height = img.size
            
            # Crop the image to only include the form area with padding
            # Crop box: (left, top, right, bottom)
            # We'll crop from form_x - 10, form_y - 10 to form_x + form_width + 10, form_y + form_height + 10
            cropped_img = img.crop((form_x - 10, form_y - 10, form_x + form_width + 10, height))
            
            # Save the cropped image back to the same file
            cropped_img.save(original_filepath)
            
            logger.info(f"Lever screenshot cropped successfully: {original_filepath}")
            return original_filepath
            
    except Exception as e:
        logger.error(f"Failed to crop Lever screenshot: {e}")
        return original_filepath


def cleanup_screenshot(filepath: str) -> bool:
    """
    Clean up screenshot file from temporary directory.
    
    Args:
        filepath: Path to the screenshot file to delete
        
    Returns:
        True if cleanup was successful, False otherwise
    """
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Screenshot cleaned up: {filepath}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to cleanup screenshot {filepath}: {e}")
        return False 