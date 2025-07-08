"""Ashby job portal implementation."""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base import BasePortal
import time


class Ashby(BasePortal):
    """Ashby job portal handler."""
    
    def __init__(self, driver, profile):
        """Initialize Ashby portal with driver and user profile."""
        super().__init__(driver, profile)
        self.logger.info("Ashby portal initialized successfully")
    
    def apply(self):
        """Apply to job on Ashby portal using base class functionality."""
        try:
            self.logger.info("Starting to fill out Ashby application form")
            
            # Process all form fields using base class methods
            self._process_all_form_fields()
            
            self.logger.info("Successfully completed Ashby application form")
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling Ashby form: {str(e)}")
            return False
    
    def _process_all_form_fields(self):
        """Process all form fields on the page, excluding radio inputs but including fieldsets."""
        try:
            # Find all form fields
            all_fields = self._find_all_form_fields()
            
            self.logger.info(f"Found {len(all_fields)} form fields to process")
            fields_filled = 0
            
            for i, field in enumerate(all_fields):
                try:
                    # Skip fields that shouldn't be filled
                    if self._should_skip_field(field):
                        continue
                    
                    # Get field label using Ashby's specific method
                    label = self._get_ashby_field_label(field)
                    self.logger.info(f"Field label: {label}")
                    if not label:
                        continue
                    
                    # Check if field is required
                    is_required = self.is_required_field(label)
                    if is_required:
                        self.logger.info(f"Field '{label}' is required")
                    
                    # Match field to profile data
                    match_result = self.match_field_to_profile(label, field)
                    if not match_result:
                        continue
                    
                    value, profile_key = match_result
                    
                    # Validate the match makes sense
                    if not self.validate_field_match(label, profile_key, value, field):
                        continue
                    
                    # Check field type and fill accordingly
                    if field.tag_name == 'fieldset':
                        self.logger.info(f"Processing fieldset as radio group: '{label}'")
                        success = self._fill_ashby_radio_group(field, value)
                    elif self._is_yesno_container(field):
                        self.logger.info(f"Processing yes/no container: '{label}'")
                        success = self._fill_ashby_yesno_container(field, value)
                    elif self._is_ashby_dropdown(field):
                        self.logger.info(f"Processing dropdown field: '{label}'")
                        success = self._fill_ashby_dropdown(field, value)
                    else:
                        self.logger.info(f"Processing regular field: '{label}'")
                    success = self.fill_field(field, value)
                    
                    if success:
                        fields_filled += 1
                        self.mark_profile_key_filled(profile_key)
                        self.logger.info(f"Successfully filled field: {label}")
                    else:
                        self.logger.warning(f"Failed to fill field: {label}")
                    
                except Exception as e:
                    self.logger.warning(f"Error processing field {i+1}: {str(e)}")
                    continue
            
            self.logger.info(f"Successfully filled {fields_filled} fields")
                    
        except Exception as e:
            self.logger.error(f"Error processing form fields: {str(e)}")
    
    def _find_all_form_fields(self):
        """Find all form fields on the page, excluding radio inputs but including fieldsets."""
        fields = []
        
        try:
            # Find all input fields except radio inputs
            input_fields = self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='radio'])")
            fields.extend(input_fields)
            
            # Find all textarea fields
            textarea_fields = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            fields.extend(textarea_fields)
            
            # Find all select fields
            select_fields = self.driver.find_elements(By.CSS_SELECTOR, "select")
            fields.extend(select_fields)
            
            # Find all fieldsets (for radio groups)
            fieldsets = self.driver.find_elements(By.CSS_SELECTOR, "fieldset")
            fields.extend(fieldsets)
            
            # Find all yes/no containers
            yesno_containers = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='_yesno']")
            fields.extend(yesno_containers)
            
            self.logger.info(f"Found {len(input_fields)} input fields, {len(textarea_fields)} textarea fields, {len(select_fields)} select fields, {len(fieldsets)} fieldsets, {len(yesno_containers)} yes/no containers")
            
        except Exception:
            self.logger.warning(f"Error finding form fields")
        
        return fields 
    
    def _get_ashby_field_label(self, field) -> str:
        """Get field label using Ashby's specific label[for] pattern and include description if available."""
        try:
            # Handle fieldsets and listboxes differently
            if field.tag_name == 'fieldset' or field.get_attribute('aria-haspopup') == 'listbox':
                try:
                    # Start with the field and traverse up to find the label
                    current = field
                    max_attempts = 5  # Prevent infinite loop
                    attempts = 0
                    
                    while current and attempts < max_attempts:
                        try:
                            # Look for the label with the question title class
                            label = current.find_element(By.CSS_SELECTOR, "label.ashby-application-form-question-title")
                            if label:
                                label_text = label.text.strip()
                                
                                # Try to find description in the same parent
                                try:
                                    description = current.find_element(By.CSS_SELECTOR, ".ashby-application-form-question-description")
                                    if description:
                                        desc_text = description.text.strip()
                                        if desc_text:
                                            label_text = f"{label_text} - {desc_text}"
                                except:
                                    pass
                                
                                return label_text
                        except:
                            pass
                        
                        # Move up to parent
                        try:
                            current = current.find_element(By.XPATH, "..")
                        except:
                            break
                        attempts += 1
                    
                    # Fallback to any label if no specific one found
                    try:
                        if field.tag_name == 'fieldset':
                            label = field.find_element(By.CSS_SELECTOR, "label")
                            return label.text.strip()
                    except:
                        pass
                except:
                    pass
            
            # For other elements, use the for attribute approach
            field_id = field.get_attribute('id')
            if not field_id:
                return self.analyze_field_context(field)
            
            # Find label using for attribute
            try:
                label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                if label:
                    label_text = label.text.strip()
                    
                    # Try to find description in siblings
                    try:
                        parent = label.find_element(By.XPATH, "..")
                        description = parent.find_element(By.CSS_SELECTOR, ".ashby-application-form-question-description")
                        if description:
                            desc_text = description.text.strip()
                            if desc_text:
                                label_text = f"{label_text} - {desc_text}"
                    except:
                        pass
                    
                    return label_text
            except:
                pass
            
            return self.analyze_field_context(field)
            
        except Exception as e:
            self.logger.warning(f"Error getting Ashby field label: {str(e)}")
            return self.analyze_field_context(field)
    
    def _fill_ashby_radio_group(self, fieldset, value):
        """Fill Ashby radio group (single select) or multiselect group by finding and clicking matching options."""
        try:
            self.logger.info(f"Filling Ashby radio group with value: '{value}'")
            
            # Check if this is a multiselect (list type)
            is_multiselect = isinstance(value, list)
            target_values = value if is_multiselect else [str(value)]
            
            self.logger.info(f"Target values: {target_values}, Multiselect: {is_multiselect}")
            
            # Find all option containers with class names starting with _option
            option_divs = fieldset.find_elements(By.XPATH, ".//div[starts-with(@class, '_option')]")
            self.logger.info(f"Found {len(option_divs)} option divs in radio group")
            
            if not option_divs:
                self.logger.warning("No option divs found in radio group")
                return False
            
            # Create a list of option elements with their text for matching
            option_elements = []
            for i, option_div in enumerate(option_divs):
                try:
                    # Get the input element and label
                    input_element = option_div.find_element(By.TAG_NAME, "input")
                    label = option_div.find_element(By.TAG_NAME, "label")
                    option_text = label.text.strip()
                    option_elements.append({
                        'element': input_element,
                        'label': label,
                        'text': option_text
                    })
                    self.logger.info(f"Option {i+1}: '{option_text}'")
                except Exception as e:
                    self.logger.info(f"Failed to get label for option {i+1}: {str(e)}")
                    continue
            
            if not option_elements:
                self.logger.warning("No valid option elements found in radio group")
                return False
            
            # Find matches for all target values
            option_texts = [opt['text'] for opt in option_elements]
            matched_indices = []
            
            for target_value in target_values:
                self.logger.info(f"Matching target '{target_value}' against options: {option_texts}")
                best_index = self.match_option_to_target(option_texts, target_value)
                
                if best_index is not None:
                    matched_indices.append(best_index)
                    self.logger.info(f"Found match for '{target_value}': index {best_index}")
                else:
                    self.logger.warning(f"No match found for '{target_value}'")
            
            if matched_indices:
                # Click all matched options
                success_count = 0
                for index in matched_indices:
                    try:
                        option = option_elements[index]
                        selected_text = option['text']
                        self.logger.info(f"Selecting option: '{selected_text}' (index {index})")
                        
                        # Use the driver's wait_and_click_element method for the label
                        self.driver.wait_and_click_element(element=option['label'])
                        self.logger.info(f"Successfully clicked option: '{selected_text}'")
                        success_count += 1
                        
                    except Exception as e:
                        self.logger.error(f"Failed to click option {index}: {str(e)}")
                        continue
                
                if success_count > 0:
                    self.logger.info(f"Successfully selected {success_count} out of {len(matched_indices)} options")
                    return True
                else:
                    self.logger.warning("Failed to click any matched options")
            else:
                self.logger.warning(f"No good matches found for any target values: {target_values}")
            
            # Fallback: use base class fallback method for single select only
            if not is_multiselect:
                self.logger.info("Attempting fallback option selection")
                fallback_elements = [opt['element'] for opt in option_elements]
                result = self.fill_option_group_fallback(fallback_elements, str(value))
                self.logger.info(f"Fallback result: {result}")
                return result
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error filling Ashby radio group: {str(e)}")
            return False

    def _is_yesno_container(self, element):
        """Check if the element is a yes/no container."""
        try:
            class_attr = element.get_attribute('class') or ''
            return '_yesno' in class_attr
        except:
            return False

    def _get_ashby_yesno_context(self, yesno_container):
        """Get context from Ashby yes/no container (question text)."""
        try:
            # Look for the label with the question title class in the parent container
            parent = yesno_container.find_element(By.XPATH, "..")
            label = parent.find_element(By.CSS_SELECTOR, "label.ashby-application-form-question-title")
            return label.text.strip()
        except:
            # Fallback to any label in the parent
            try:
                parent = yesno_container.find_element(By.XPATH, "..")
                label = parent.find_element(By.CSS_SELECTOR, "label")
                return label.text.strip()
            except:
                return ""

    def _fill_ashby_yesno_container(self, yesno_container, value):
        """Fill Ashby yes/no container by clicking the appropriate button."""
        try:
            self.logger.info(f"Filling Ashby yes/no container with value: '{value}'")
            
            # Find Yes and No buttons
            buttons = yesno_container.find_elements(By.CSS_SELECTOR, "button")
            self.logger.info(f"Found {len(buttons)} buttons in yes/no container")
            
            if len(buttons) < 2:
                self.logger.warning("Expected at least 2 buttons (Yes/No) in yes/no container")
                return False
            
            # Create list of button options for matching
            button_options = []
            for i, button in enumerate(buttons):
                button_text = button.text.strip()
                button_options.append({
                    'element': button,
                    'text': button_text
                })
                self.logger.info(f"Button {i+1}: '{button_text}'")
            
            # Match the value to the appropriate button
            button_texts = [btn['text'] for btn in button_options]
            best_index = self.match_option_to_target(button_texts, str(value))
            
            if best_index is not None:
                selected_button = button_options[best_index]
                selected_text = selected_button['text']
                self.logger.info(f"Selecting button: '{selected_text}' (index {best_index})")
                
                # Click the matched button
                self.driver.wait_and_click_element(element=selected_button['element'])
                self.logger.info(f"Successfully clicked button: '{selected_text}'")
                return True
            else:
                self.logger.warning(f"No match found for value '{value}' against buttons: {button_texts}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error filling Ashby yes/no container: {str(e)}")
            return False

    def _is_ashby_dropdown(self, field) -> bool:
        """Check if field is an Ashby dropdown input."""
        try:
            return field.get_attribute('aria-haspopup') == 'listbox'
        except:
            return False

    def _wait_for_aria_controls(self, field, timeout=5):
        """Wait for aria-controls attribute to be populated."""
        def has_aria_controls(field):
            return field.get_attribute('aria-controls') is not None
        
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(lambda _: has_aria_controls(field))
            return field.get_attribute('aria-controls')
        except:
            return None

    def _fill_ashby_dropdown(self, field, value) -> bool:
        """Fill Ashby dropdown input by typing and selecting first option."""
        try:
            if not value:
                return False

            self.logger.info(f"Filling Ashby dropdown with value: {value}")
            
            # Scroll and click the input field
            self.driver.wait_and_click_element(element=field)
            
            # Type the value
            field.clear()
            field.send_keys(str(value))
            
            # Wait for aria-controls to be populated
            listbox_id = self._wait_for_aria_controls(field)
            if not listbox_id:
                self.logger.warning("No aria-controls found for dropdown after waiting")
                return False
            
            self.logger.info(f"Found listbox ID: {listbox_id}")
            
            # Wait for listbox and options to appear
            try:
                # Wait for listbox
                listbox = self.driver.wait_and_find_element(By.ID, listbox_id, 2)
                if not listbox:
                    self.logger.warning("Could not find listbox element")
                    return False
                
                # Wait for at least one option to appear
                options = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{listbox_id} div[role='option']", 2)
                if not options:
                    self.logger.warning("No options found in listbox")
                    return False
                
                # Click the first option
                first_option = options[0]
                first_option.click()
                return True
                
            except Exception as e:
                self.logger.warning(f"Error selecting dropdown option: {str(e)}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error filling Ashby dropdown: {str(e)}")
            return False