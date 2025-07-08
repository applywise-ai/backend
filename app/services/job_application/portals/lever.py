"""Lever job portal implementation."""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.schemas.application import UserProfile
from .base import BasePortal


class Lever(BasePortal):
    """Lever job portal handler."""
    
    def __init__(self, driver, profile):
        """Initialize Lever portal with driver and user profile."""
        super().__init__(driver, profile)
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
                        return label_text
                except Exception as e:
                    self.logger.debug(f"Could not find label element: {str(e)}")
            
            # Fallback: Use base get context method(TODO: Use AI to extract the label)
            return self.analyze_field_context(field)
        except Exception as e:
            self.logger.warning(f"Error getting field label: {str(e)}")
            return ""
    
    def _find_all_form_fields(self):
        """Find all form fields on the page."""
        fields = []
        
        try:
            # Find all input fields except radio inputs (we'll handle radio groups separately)
            input_fields = self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='radio'])")
            fields.extend(input_fields)
            
            # Find all textarea fields
            textarea_fields = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            fields.extend(textarea_fields)
            
            # Find all select fields
            select_fields = self.driver.find_elements(By.CSS_SELECTOR, "select")
            fields.extend(select_fields)
            
            # Find Lever groups(checkboxes or multiple-choice)
            radio_groups = self.driver.find_elements(By.CSS_SELECTOR, "ul[data-qa]")
            fields.extend(radio_groups)
            
            self.logger.info(f"Found {len(input_fields)} input fields, {len(textarea_fields)} textarea fields, {len(select_fields)} select fields, {len(radio_groups)} radio groups")
            
        except Exception as e:
            self.logger.warning(f"Error finding form fields: {str(e)}", exc_info=True)
        
        return fields
    
    def _is_lever_group(self, field) -> bool:
        """Check if field is a Lever radio group."""
        try:
            return field.tag_name == 'ul' and field.get_attribute('data-qa')
        except:
            return False

    def _fill_lever_group(self, group, value) -> bool:
        """Fill Lever group by selecting the appropriate option(s)."""
        try:
            if not value:
                return False
            
            # Check if the group is a multiselect
            is_multiselect = group.get_attribute('data-qa') == 'checkboxes'

            self.logger.info(f"Filling Lever group with value: {value} (multiselect: {is_multiselect})")
            
            # Scroll to the group
            self.scroll_to_element(group)

            # Find all options
            options = group.find_elements(By.CSS_SELECTOR, "li label")
            if not options:
                self.logger.warning("No options found in group")
                return False
            
            # Get all option texts
            option_texts = [opt.find_element(By.CSS_SELECTOR, "span.application-answer-alternative").text.strip() for opt in options]
            
            # Handle multiple values
            if isinstance(value, list):
                values_to_process = value
            else:
                # Convert single value to list for uniform processing
                values_to_process = [value]
            
            # If not multiselect but multiple values provided, use only the first value
            if not is_multiselect and len(values_to_process) > 1:
                self.logger.info(f"Field is not multiselect but multiple values provided. Using first value: {values_to_process[0]}")
                values_to_process = [values_to_process[0]]
            
            # Track successful matches
            successful_matches = 0
            
            # Process each value
            for val in values_to_process:
                if not val:  # Skip empty values
                    continue
                
                # Use match_option_to_target to find best match
                best_index = self.match_option_to_target(option_texts, str(val))
                if best_index is not None:
                    options[best_index].click()
                    successful_matches += 1
                    self.logger.info(f"Successfully matched and clicked option for value: {val}")
                else:
                    self.logger.warning(f"No matching option found for value: {val}")
            
            # Return True if at least one match was successful
            if successful_matches > 0:
                return True
            
            self.logger.warning(f"No matching options found for any values: {values_to_process}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error filling Lever group: {str(e)}")
            return False
    
    def _process_all_form_fields(self):
        """Process all form fields using base class functionality."""
        try:
            # Find all form fields
            all_fields = self._find_all_form_fields()
            
            self.logger.info(f"Found {len(all_fields)} form fields to process")
            fields_filled = 0
            
            for i, field in enumerate(all_fields):
                try:
                    # Log field details
                    field_type = field.get_attribute('type') if not self._is_lever_group(field) else 'radio-group'
                    field_name = field.get_attribute('name') or 'no-name'
                    field_id = field.get_attribute('id') or 'no-id'
                    self.logger.info(f"Processing field {i+1}: {field_type} (name: {field_name}, id: {field_id})")
                    
                    # Skip fields that shouldn't be filled
                    if self._should_skip_field(field):
                        continue
                    
                    # Get field label
                    label = self._get_field_label(field)
                    if not label:
                        self.logger.info(f"No label found for field {i+1}, skipping")
                        continue
                    
                    if self.is_required_field(label):
                        self.logger.info(f"Field {i+1} with label '{label}' is required")
                    else:
                        self.logger.info(f"Field {i+1} label: '{label}' is not required")
                    
                    # Match field to profile data
                    match_result = self.match_field_to_profile(label, field)
                    if not match_result:
                        self.logger.info(f"No profile match found for field {i+1}")
                        continue
                    
                    value, profile_key = match_result
                    self.logger.info(f"Field {i+1} matched to profile key '{profile_key}' with value: {value}")
                    
                    # Validate the match makes sense
                    if not self.validate_field_match(label, profile_key, value, field):
                        self.logger.info(f"Field {i+1} match validation failed")
                        continue
                    
                    # Fill the field using appropriate method
                    if self._is_location_field(label, field):
                        self.logger.info(f"Field {i+1} identified as location field")
                        success = self._fill_location_field(field, value)
                    elif self._is_lever_group(field):
                        self.logger.info(f"Processing group: '{label}'")
                        success = self._fill_lever_group(field, value)
                    else:
                        self.logger.info(f"Processing regular field: '{label}'")
                        success = self.fill_field(field, value)
                    
                    if success:
                        fields_filled += 1
                        self.mark_profile_key_filled(profile_key)
                        self.logger.info(f"Successfully filled field {i+1}")
                        
                        # Fill disability section
                        if profile_key == 'disability':
                            self._fill_disability_signature_section()
                    else:
                        self.logger.warning(f"Failed to fill field {i+1}")
                    
                except Exception as e:
                    self.logger.warning(f"Error processing field {i+1}: {str(e)}", exc_info=True)
                    continue
            
            self.logger.info(f"Successfully filled {fields_filled} out of {len(all_fields)} fields")
                    
        except Exception as e:
            self.logger.error(f"Error processing form fields: {str(e)}", exc_info=True)
    
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