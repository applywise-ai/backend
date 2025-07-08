"""Workable job portal implementation."""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .base import BasePortal


class Workable(BasePortal):
    """Workable job portal handler."""
    
    def __init__(self, driver, profile):
        """Initialize Workable portal with explicit parent initialization."""
        try:
            super().__init__(driver, profile)
            self.logger.info("Workable portal initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing Workable portal: {str(e)}")
            raise

    def apply(self):
        """Apply to job on Workable portal using base class functionality."""
        try:
            # Handle cookie consent first
            self._handle_cookie_consent()
            
            self.logger.info("Starting to fill out Workable application form")
            
            # Find all form fields and process them using base class methods
            self._process_all_form_fields()
            
            self.logger.info("Successfully completed Workable application form")
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling Workable form: {str(e)}")
            return False
    
    def _process_all_form_fields(self):
        """Process all form fields using base class functionality."""
        try:
            # Find all form fields (including custom radio groups, excluding regular radio inputs)
            all_fields = self._find_all_form_fields()
            
            self.logger.info(f"Found {len(all_fields)} form fields to process")
            fields_filled = 0
            
            for i, field in enumerate(all_fields):
                try:
                    field_type = field.tag_name
                    field_id = field.get_attribute('id') or 'no-id'
                    self.logger.info(f"Processing field {i+1}: {field_type} (id: {field_id})")
                    
                    # Skip fields that shouldn't be filled
                    if self._should_skip_field(field):
                        skip_reason = self._get_skip_reason(field) if hasattr(self, '_get_skip_reason') else "unknown reason"
                        self.logger.info(f"Skipping field {i+1}: {skip_reason}")
                        continue
                    
                    # Check if this is a Workable radio group
                    is_radio_group = field.tag_name.lower() == 'fieldset' and field.get_attribute('role') == 'radiogroup'
                    
                    # Analyze field context using base class method or specific method for fieldsets
                    if is_radio_group:
                        context = self._get_workable_fieldset_context(field)
                    else:
                        context = self.analyze_field_context(field)
                    
                    self.logger.info(f"Field {i+1} context: '{context[:100]}...' (type: {field_type})")
                    
                    if not context:
                        self.logger.info(f"No context found for field {i+1}, skipping")
                        continue
                    
                    # Match field to profile data using base class method
                    match_result = self.match_field_to_profile(context, field)
                    if not match_result:
                        self.logger.info(f"No profile match found for field {i+1} with context: '{context[:50]}...'")
                        continue
                    
                    value, profile_key = match_result
                    self.logger.info(f"Field {i+1} matched: '{context[:50]}...' -> {profile_key} = '{value}'")
                    
                    # Validate the match makes sense
                    if not self.validate_field_match(context, profile_key, value, field):
                        self.logger.info(f"Match validation failed for field {i+1}: {profile_key} = '{value}'")
                        continue
                    
                    # Fill the field using appropriate method
                    if is_radio_group:
                        self.logger.info(f"Processing fieldset {i+1} as radio group: '{context[:50]}...'")
                        success = self._fill_workable_radio_group(field, value)
                    else:
                        self.logger.info(f"Processing regular field {i+1} ({field_type}): '{context[:50]}...'")
                        success = self.fill_field(field, value)
                        
                    if success:
                        fields_filled += 1
                        self.mark_profile_key_filled(profile_key)
                        self.logger.info(f"Successfully filled field {i+1}: {profile_key}")
                    else:
                        self.logger.warning(f"Failed to fill field {i+1}: {profile_key}")
                    
                except Exception as e:
                    self.logger.warning(f"Error processing field {i+1}: {str(e)}")
                    continue
            
            self.logger.info(f"Successfully filled {fields_filled} fields")
                    
        except Exception as e:
            self.logger.error(f"Error processing form fields: {str(e)}")
    
    def _find_all_form_fields(self):
        """Find all form fields on the page, including Workable custom radio groups."""
        fields = []
        
        try:
            # Find all non-radio input fields (exclude radio to avoid conflicts with custom radio groups)
            input_fields = self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='radio'])")
            fields.extend(input_fields)
            
            # Find all textarea fields
            textarea_fields = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            fields.extend(textarea_fields)
            
            # Find all select fields
            select_fields = self.driver.find_elements(By.CSS_SELECTOR, "select")
            fields.extend(select_fields)
            
            # Find Workable custom radio groups (fieldset with role="radiogroup")
            radio_groups = self.driver.find_elements(By.CSS_SELECTOR, "fieldset[role='radiogroup']")
            fields.extend(radio_groups)
            
            self.logger.info(f"Found {len(input_fields)} input fields, {len(textarea_fields)} textarea fields, {len(select_fields)} select fields, {len(radio_groups)} radio groups")
            
        except Exception as e:
            self.logger.warning(f"Error finding form fields: {str(e)}")
        
        return fields
    
    def _get_workable_fieldset_context(self, fieldset):
        """Get context from Workable fieldset (question text)."""
        try:
            parent = fieldset.find_element(By.XPATH, "..")
            # Look for sibling span that contains the label
            sibling_spans = parent.find_elements(By.XPATH, "./span[contains(@class, 'styles--')]")
            for span in sibling_spans:
                # Look for nested span with ID ending in "_label"
                try:
                    label_span = span.find_element(By.CSS_SELECTOR, "span[id$='_label']")
                    label_text = label_span.text.strip()
                    if label_text:
                        return label_text
                except:
                    continue
            return ""
        except Exception as e:
            self.logger.warning(f"Error getting fieldset context: {str(e)}")
            return ""
    
    def _fill_workable_radio_group(self, radio_group, value) -> bool:
        """Fill Workable custom radio group by clicking the appropriate option wrapper."""
        try:
            self.logger.info(f"Filling Workable radio group with value: '{value}'")
            
            # Scroll to the radio group to ensure it's visible
            self.scroll_to_element(radio_group)
            
            # Find all option wrappers within the radio group - try multiple selectors
            option_wrappers = radio_group.find_elements(By.CSS_SELECTOR, "div[role='radio']")
            
            # If no div[role='radio'] found, try the data-ui="option" structure
            if not option_wrappers:
                option_wrappers = radio_group.find_elements(By.CSS_SELECTOR, "div[data-ui='option']")
            
            self.logger.info(f"Found {len(option_wrappers)} option wrappers in radio group")
            
            if not option_wrappers:
                self.logger.warning("No option wrappers found in radio group")
                return False
            
            # Create list of option elements for matching
            option_elements = []
            for i, option_wrapper in enumerate(option_wrappers):
                try:
                    # Try to get text from span with radio_label_ ID first
                    try:
                        label_span = option_wrapper.find_element(By.CSS_SELECTOR, "span[id*='radio_label_']")
                        option_text = label_span.text.strip()
                    except:
                        # Fallback to textContent of the wrapper
                        option_text = option_wrapper.get_attribute('textContent') or ''
                        option_text = option_text.strip()
                    
                    if option_text:
                        option_elements.append({
                            'element': option_wrapper,
                            'text': option_text
                        })
                        self.logger.info(f"Option {i+1}: '{option_text}'")
                except Exception as e:
                    self.logger.info(f"Failed to get text for option {i+1}: {str(e)}")
                    continue
            
            if not option_elements:
                self.logger.warning("No valid option elements found in radio group")
                return False
            
            # Match the value to the appropriate option
            option_texts = [opt['text'] for opt in option_elements]
            best_index = self.match_option_to_target(option_texts, str(value))
            
            if best_index is not None:
                selected_option = option_elements[best_index]
                selected_text = selected_option['text']
                self.logger.info(f"Selecting option: '{selected_text}' (index {best_index})")
                
                # Check if already selected
                aria_checked = selected_option['element'].get_attribute('aria-checked')
                if aria_checked == 'true':
                    self.logger.info(f"Option already selected: '{selected_text}'")
                    return True
                        
                # Click the wrapper to select it
                try:
                    self.driver.wait_and_click_element(element=selected_option['element'])
                    self.logger.info(f"Successfully clicked option: '{selected_text}'")
                    return True
                except Exception as e:
                    self.logger.warning(f"Failed to click option: {str(e)}")
                    return False
            else:
                self.logger.warning(f"No match found for value '{value}' against options: {option_texts}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error filling Workable radio group: {str(e)}")
            return False
    
    def _handle_cookie_consent(self):
        """Handle cookie consent banner on Workable."""
        try:
            self.logger.info("Checking for cookie consent banner")
            
            # Use known working selector for Workable
            selector = "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]"
            
            try:
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
                    
            except Exception as e:
                self.logger.info(f"No cookie consent banner found ({str(e)}) - proceeding with application")
                
        except Exception as e:
            self.logger.warning(f"Error handling cookie consent: {str(e)} - proceeding anyway")