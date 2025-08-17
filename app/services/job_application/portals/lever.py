"""Lever job portal implementation."""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base import BasePortal
from app.services.job_application.types import get_field_type
from app.schemas.application import QuestionType


class Lever(BasePortal):
    """Lever job portal handler."""
    
    def __init__(self, driver, profile, url=None, job_description=None, overrided_answers=None):
        """Initialize Lever portal with driver and user profile."""
        super().__init__(driver, profile, url, job_description, overrided_answers)
        self.logger.info("Lever portal initialized successfully")
    
    def apply(self):
        """Apply to job on Lever portal using base class functionality."""
        try:
            self.logger.info("Starting to fill out Lever application form")
            
            # Process all form fields using base class methods
            self._process_all_form_fields()
            
            self.logger.info("Successfully completed Lever application form")
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling Lever form: {str(e)}", exc_info=True)
            return False
    
    def _get_field_label(self, field) -> str:
        """Get the field label from the Lever application form structure."""
        try:
            # First try to find the parent question div
            parent = field
            max_attempts = 5  # Prevent infinite loop
            attempts = 0
            
            while parent and attempts < max_attempts:
                if parent.get_attribute('class') and 'application-question' in parent.get_attribute('class'):
                    break
                parent = parent.find_element(By.XPATH, '..')
                attempts += 1
            
            if parent and 'application-question' in parent.get_attribute('class'):
                # Find the label element within the question div
                try:
                    label_elem = parent.find_element(By.CSS_SELECTOR, '.application-label')
                    if label_elem:
                        label_text = label_elem.text.strip()
                        self.logger.debug(f"Found label text: {label_text}")
                        is_required = len(label_elem.find_elements(By.CSS_SELECTOR, '.required')) > 0
                        return label_text, is_required
                except Exception as e:
                    self.logger.debug(f"Could not find label element: {str(e)}")
            
            # If an id exists try to find label by id
            field_id = field.get_attribute('id')
            if field_id:
                label_elem = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                if label_elem:
                    label_text = label_elem.text.strip()
                    self.logger.debug(f"Found label text: {label_text}")
                    is_required = len(label_elem.find_elements(By.CSS_SELECTOR, '.required')) > 0
                    return label_text, is_required

            # Fallback: Use base get context method
            fallback_label = self.analyze_field_context(field)
            return fallback_label, self.is_required_field(fallback_label)
        except Exception as e:
            self.logger.warning(f"Error getting field label: {str(e)}")
            return ""
    
    def _find_all_form_fields(self):
        """Find all form fields on the page in DOM order."""
        try:
            # Select all relevant form fields at once
            fields = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input:not([type='radio']):not([type='checkbox']), textarea, select, ul[data-qa]"
            )

            self.logger.info(f"Found {len(fields)} form fields in DOM order")

            return fields

        except Exception as e:
            self.logger.warning(f"Error finding form fields: {str(e)}", exc_info=True)
            return []
    
    def _process_all_form_fields(self):
        """Process all form fields using base class functionality."""
        try:
            # Find all form fields
            all_fields = self._find_all_form_fields()

            # Queued location field to process at end(prevents issues with resume autofill)
            location_field = {}
            
            self.logger.info(f"Found {len(all_fields)} form fields to process")
            fields_filled = 0
            
            for i, field in enumerate(all_fields):
                try:
                    # Skip fields that shouldn't be filled
                    if self._should_skip_field(field):
                        continue
                    
                    # Get field label
                    label, is_required = self._get_field_label(field)
                    
                    # Get field type
                    field_type = self._get_lever_field_type(field)
                    
                    # Check if field has custom options
                    is_lever_group = self._is_lever_group(field)
                    
                    # Initialize form question
                    question_id = self.init_form_question(field, field_type, label, is_required, is_lever_group)
                    
                    # Match field to profile data
                    value = self.match_field_to_profile(question_id)
                    self.logger.info(f"Field {i+1} matched to value: {value}")
                    
                    # Fill the field using appropriate method
                    if self._is_location_field(label, field):
                        self.logger.info(f"Field {i+1} identified as location field")
                        location_field = { 'field': field, 'value': value, 'question': label }
                        continue
                    elif is_lever_group:
                        self.logger.info(f"Processing group: '{label}'")
                        success = self._fill_lever_group(field, question_id)
                    else:
                        self.logger.info(f"Processing regular field: '{label}'")
                        success = self.fill_field(field, question_id)
                    
                    if success:
                        fields_filled += 1
                        self.logger.info(f"Successfully filled field {i+1}")
                        
                        # Fill disability section - check if 'disability' is in the question text
                        if 'disability' in label.lower():
                            self._fill_disability_signature_section()
                    else:
                        self.logger.warning(f"Failed to fill field {i+1}")
                    
                except Exception as e:
                    self.logger.warning(f"Error processing field {i+1}: {str(e)}", exc_info=True)
                    continue
            
            # Fill location field at end
            if location_field:
                success = self._fill_location_field(location_field['field'], location_field['value'])
                if success:
                    fields_filled += 1
                    self.logger.info(f"Successfully filled location field")
            
            self.logger.info(f"Successfully filled {fields_filled} out of {len(all_fields)} fields")
                    
        except Exception as e:
            self.logger.error(f"Error processing form fields: {str(e)}", exc_info=True)

    def _get_lever_field_type(self, field) -> QuestionType:
        """Get field type based on field attributes."""
        if self._is_lever_group(field):
            return QuestionType.SELECT
        else:
            return get_field_type(field.get_attribute('type'), field.tag_name)

    def _is_lever_group(self, field) -> bool:
        """Check if field is a Lever radio group."""
        try:
            return field.tag_name == 'ul' and field.get_attribute('data-qa') is not None
        except:
            return False

    def _fill_lever_group(self, group, question_id: str) -> bool:
        """Fill Lever group by selecting the appropriate option(s)."""
        try:
            value = self.form_questions[question_id].get('answer')
            question = self.form_questions[question_id].get('question')
            
            # Check if the group is a multiselect
            is_multiselect = 'checkboxes' in group.get_attribute('data-qa').lower()

            self.logger.info(f"Filling Lever group with value: {value} (multiselect: {is_multiselect}) for question: {question}")
            
            # Scroll to the group
            self.scroll_to_element(group)

            # Find all options
            options = group.find_elements(By.CSS_SELECTOR, "li label")
            if not options:
                self.logger.warning("No options found in group")
                return False
            
            # Get all option texts
            option_texts = [opt.find_element(By.CSS_SELECTOR, "span.application-answer-alternative").text.strip() for opt in options]
            
            best_indices = []
            if is_multiselect:
                best_indices = self.match_option_to_target(option_texts, question_id, multiple=True)
            else:
                best_indices = [self.match_option_to_target(option_texts, question_id)]
            
            # Click the options
            for index in best_indices:
                self.driver.wait_and_click_element(options[index])
                self.logger.info(f"Successfully clicked option {index} for value: {value}")
            
            # Return True if at least one match was successful
            if len(best_indices) > 0:
                return True
            
            self.logger.warning(f"No matching options found for any values: {value}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error filling Lever group: {str(e)}")
            return False
    
    def _is_location_field(self, label: str, field) -> bool:
        """Check if this is Lever's specific current location field."""
        try:
            # Check for Lever's specific current location field
            field_name = field.get_attribute('name') or ''
            field_id = field.get_attribute('id') or ''
            
            # Log field attributes
            self.logger.debug(f"Checking location field - name: {field_name}, id: {field_id}, label: {label}")
            
            # Lever's current location field has specific attributes
            if 'current' in label.lower() and 'location' in label.lower():
                self.logger.debug("Identified as location field by label")
                return True
            
            # Check for specific field names/IDs that Lever uses for location
            if field_name in ['location', 'currentLocation', 'current_location']:
                self.logger.debug(f"Identified as location field by name: {field_name}")
                return True
                
            if field_id in ['location', 'currentLocation', 'current_location']:
                self.logger.debug(f"Identified as location field by id: {field_id}")
                return True
                
            return False
            
        except Exception as e:
            self.logger.warning(f"Error checking location field: {str(e)}")
            return False
    
    def _fill_location_field(self, field, value) -> bool:
        """Fill location field with autocomplete/typeahead functionality."""
        try:
            self.logger.info(f"Filling location field with value: {value}")
            
            # Scroll to the field
            self.scroll_to_element(field)
            self.logger.debug("Scrolled to location field")

            field.send_keys(value)
            self.logger.debug(f"Entered value: {value}")
            
            # Wait for autocomplete options to appear (reduced time)
            time.sleep(2)
            self.logger.debug("Waited for autocomplete options")
            
            # Look for Lever's specific location dropdown structure
            dropdown_selectors = [
                # Lever's specific location dropdown structure
                '.dropdown-results .dropdown-location',
                '.dropdown-location',
                # Fallback patterns
                '.dropdown-results div',
                '[id^="location-"]'
            ]
            
            for selector in dropdown_selectors:
                try:
                    self.logger.debug(f"Trying selector: {selector}")
                    # Wait for options to appear
                    wait = WebDriverWait(self.driver, 2)
                    options = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                    
                    if options:
                        self.logger.info(f"Found {len(options)} autocomplete options with selector: {selector}")
                        
                        # Click the first option
                        first_option = options[0]
                        self.scroll_to_element(first_option)
                        first_option.click()
                        
                        self.logger.info("Successfully clicked first autocomplete option")
                        return True
                        
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {str(e)}")
                    continue
            
            # If no dropdown found, just leave the typed value
            self.logger.info("No autocomplete dropdown found, leaving typed value")
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling location field: {str(e)}", exc_info=True)
            return False

    def _fill_disability_signature_section(self) -> bool:
        """Fill the disability signature section if disability status was filled."""
        try:
            # Check if the section exists
            signature_section = self.driver.wait_and_find_element(By.ID, "disabilitySignatureSection", 2)
            if not signature_section.is_displayed():
                self.logger.debug("Disability signature section not displayed")
                return False

            self.logger.info("Found disability signature section, filling required fields")
            
            # Get the current date in MM/DD/YYYY format
            from datetime import datetime
            current_date = datetime.now().strftime("%m/%d/%Y")
            
            # Fill name field
            try:
                # Wait for name field to be present and interactable
                wait = WebDriverWait(self.driver, 10)
                name_field = wait.until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, 'input[name="eeo[disabilitySignature]"]')
                    )
                )
                full_name = self.profile.get('fullName', '')
                self.logger.info(f"Filling disability signature name with: {full_name}")
                name_field.send_keys(full_name)
            except Exception as e:
                self.logger.warning(f"Error filling disability signature name: {str(e)}")
                return False

            # Fill date field
            try:
                date_field = signature_section.find_element(By.CSS_SELECTOR, 'input[name="eeo[disabilitySignatureDate]"]')
                self.logger.info(f"Filling disability signature date with: {current_date}")
                date_field.send_keys(current_date)
            except Exception as e:
                self.logger.warning(f"Error filling disability signature date: {str(e)}")
                return False

            self.logger.info("Successfully filled disability signature section")
            return True

        except Exception as e:
            self.logger.warning(f"Error handling disability signature section: {str(e)}")
            return False