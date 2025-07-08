"""Greenhouse job portal implementation."""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys  
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base import BasePortal


class Greenhouse(BasePortal):
    """Greenhouse job portal handler."""
    
    def __init__(self, driver, profile):
        """Initialize Greenhouse portal with driver and user profile."""
        super().__init__(driver, profile)
        self.logger.info("Greenhouse portal initialized successfully")
    
    def apply(self):
        """Apply to job on Greenhouse."""
        try:
            # Find and click the Apply button first
            try:
                apply_button = self.driver.wait_and_find_element(By.XPATH, "//button[contains(text(), 'Apply')]", 5)
                if apply_button:
                    self.logger.info("Found Apply button, clicking it")
                    self.driver.wait_and_click_element(element=apply_button)
                else:
                    self.logger.warning("Could not find Apply button")
            except Exception as e:
                self.logger.warning(f"Error clicking Apply button: {str(e)}")

            # Process all form fields
            self._process_all_form_fields()
            
            # Handle education section if present
            self._handle_greenhouse_education_section()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error applying to Greenhouse job: {str(e)}")
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
                    # Skip fields that shouldn't be filled
                    if self._should_skip_field(field):
                        continue
                    
                    # Check if this is a Greenhouse React Select
                    is_react_select = self._is_greenhouse_react_select(field)

                    # Check if this is a Greenhouse Select2 dropdown
                    is_select2 = self._is_greenhouse_select2_field(field)
                    
                    # Get field label by traversing parents
                    label = self._get_greenhouse_field_label(field)
                    self.logger.info(f"Field label: {label}")
                    if not label:
                        continue
                    
                    # Check if field is required
                    is_required = self.is_required_field(label)
                    if is_required:
                        self.logger.info(f"Field '{label}' is required")
                    
                    # Match field to profile data using base class method (don't skip repeated education fields)
                    match_result = self.match_field_to_profile(label, field)
                    self.logger.info(f"Match result: {match_result} for label: {label}")
                    if not match_result:
                        continue
                    
                    value, profile_key = match_result
                    
                    # Validate the match makes sense
                    if not self.validate_field_match(label, profile_key, value, field):
                        continue
                    
                    # Fill the field using appropriate method
                    if is_react_select:
                        success = self._fill_greenhouse_react_select(field, value)
                    elif is_select2:
                        success = self._fill_greenhouse_select2_field(field, value)
                    else:
                        success = self.fill_field(field, value)
                        
                    if success:
                        fields_filled += 1
                        self.mark_profile_key_filled(profile_key)
                        self.logger.info(f"Successfully filled field {i+1}")
                        
                        # If we just filled hispanic origin and selected No, fill race
                        if profile_key == 'hispanic' and str(value).lower() == 'no':
                            self._fill_race_field()
                    else:
                        self.remove_focus()
                        self.logger.warning(f"Failed to fill field {i+1}")
                    
                except Exception as e:
                    self.logger.warning(f"Error processing field {i+1}: {str(e)}", exc_info=True)
                    continue
            
            self.logger.info(f"Successfully filled {fields_filled} out of {len(all_fields)} fields")
                    
        except Exception:
            self.logger.error(f"Error processing form fields")
    
    def _find_all_form_fields(self):
        """Find all form fields on the page."""
        fields = []
        
        try:
            # Find all input fields
            input_fields = self.driver.find_elements(By.CSS_SELECTOR, "input")
            fields.extend(input_fields)
        
            # Find all textarea fields
            textarea_fields = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            fields.extend(textarea_fields)
            
            # Find all select fields
            select_fields = self.driver.find_elements(By.CSS_SELECTOR, "select")
            fields.extend(select_fields)
            
            # Find Greenhouse React Select input fields (they have specific classes and are within select containers)
            react_select_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input.select__input[role='combobox']")
            fields.extend(react_select_inputs)
            
        except Exception:
            self.logger.warning(f"Error finding form fields")
        
        return fields
    
    def _handle_greenhouse_education_section(self):
        """Handle Greenhouse custom education section with dynamic creation and filling."""
        try:
            # Check if education section exists
            education_section = self.driver.find_elements(By.ID, "education_section")
            if not education_section:
                return
            
            # Get education data from profile
            education_list = self.profile.get('education', [])
            if not education_list:
                return
            
            # Add all education entries so we can find and fill them later
            for i in range(len(education_list)):
                # Add new education entry if needed (skip first one as it already exists)
                if i > 0:
                    self._add_greenhouse_education_entry()
                
        except Exception:
            self.logger.error(f"Error handling Greenhouse education section")
    
    def _add_greenhouse_education_entry(self):
        """Add a new education entry by clicking the 'Add another education' button."""
        try:
            add_button = self.driver.find_element(By.ID, "add_education")
            if add_button and add_button.is_displayed():
                self.driver.wait_and_click_element(element=add_button)
        except Exception:
            self.logger.warning(f"Error adding education entry")

    def _is_greenhouse_react_select(self, field) -> bool:
        """Check if field is a Greenhouse React Select component."""
        try:
            # Check if the field is within a React Select container
            parent = field.find_element(By.XPATH, "./ancestor::div[contains(@class, 'select__control')]")
            return parent is not None
        except:
            return False
    
    def _is_react_select_autocomplete(self, select_control) -> bool:
        """Check if React Select field is an autocomplete field by checking if select__indicators is empty."""
        try:
            # Try to find select__indicators
            indicators = select_control.find_elements(By.CSS_SELECTOR, ".select__indicators *")
            return len(indicators) == 0
        except:
            return False
    
    def _fill_greenhouse_react_select(self, field, value) -> bool:
        """Fill Greenhouse React Select component."""
        try:
            if not value:
                return False
            
            # Find the select control container
            select_control = field.find_element(By.XPATH, "./ancestor::div[contains(@class, 'select__control')]")
            
            # Check if this is an autocomplete field
            is_autocomplete = self._is_react_select_autocomplete(select_control)
            self.logger.info(f"React Select field is autocomplete: {is_autocomplete}")
            
            # For both autocomplete and regular dropdowns, we need to:
            # 1. Click to open (or focus for autocomplete)
            # 2. Type the value if it's autocomplete
            # 3. Find and click the matching option
            
            # Click the field to open the dropdown
            self.driver.wait_and_click_element(element=field)

            if is_autocomplete:
                city = value.split(",")[0]
                field.send_keys(city)
            
            # Get field ID to find the listbox
            field_id = field.get_attribute('id')
            listbox_id = f"react-select-{field_id}-listbox" if field_id else None
            
            try:
                # Try to find options in the listbox if we have an ID
                if listbox_id:
                    self.logger.info(f"Looking for options in listbox: {listbox_id}")
                    option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{listbox_id} div[role='option']", 2)
                    if option_elements:
                        # If there are more than 5 options, type into the field and then fetch options again
                        if len(option_elements) >= 5:
                            field.send_keys(value)
                            option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{listbox_id} div[role='option']", 2)
                            if not option_elements:
                                self.logger.info(f"No options found, clearing field")
                                field.clear()
                                option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{listbox_id} div[role='option']", 2)
                        self.logger.info(f"Found {len(option_elements)} options in listbox")
                        option_texts = [elem.get_attribute('textContent') or '' for elem in option_elements]
                        best_index = self.match_option_to_target(option_texts, str(value))
                        if best_index is not None:
                            option_elements[best_index].click()
                            return True
                
                # If still no match found and it's autocomplete, just press enter
                if is_autocomplete:
                    self.logger.info("No matching option found for autocomplete, pressing enter")
                    field.send_keys(Keys.ENTER)
                    return True

                return False
                
            except Exception as e:
                self.logger.warning(f"Error finding/selecting options for {value}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error filling Greenhouse React Select for {value}")
            return False
    
    def _is_greenhouse_select2_field(self, field) -> bool:
        """Check if field is a Greenhouse Select2 dropdown by checking for 'select2' in classname."""
        try:
            class_name = field.get_attribute('class') or ''
            return 'select2' in class_name.lower()
        except:
            return False
    
    def _fill_greenhouse_select2_field(self, field, value) -> bool:
        """Fill Greenhouse Select2 field using label ID approach."""
        try:
            if not value:
                return False
            
            field_id = field.get_attribute('id')
            self.logger.info(f"Filling Select2 field with ID: {field_id}")
            if not field_id:
                return False
            
            # Find parent div and click that instead
            parent_div = field.find_element(By.XPATH, "./parent::div")
            self.driver.wait_and_click_element(element=parent_div)
            
            # Find the search input and options
            search_input = self.driver.wait_and_find_element(By.ID, f"{field_id}_search")
                    
            # Get the aria-controls attribute to find the listbox
            aria_controls = search_input.get_attribute('aria-controls')
                    
            if aria_controls:
                # Wait for listbox to be present
                listbox = self.driver.wait_and_find_element(By.XPATH, f"//*[@id='{aria_controls}']")
                        
                # Wait for at least one option to appear
                option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{aria_controls} li", 2)
                
                # Get the first 10 options
                option_elements = option_elements[:10]
                
                # Find the best matching option
                option_texts = [elem.get_attribute('textContent') or '' for elem in option_elements]
                
                best_index = self.match_option_to_target(option_texts, str(value))
                if best_index is not None:
                    option_elements[best_index].click()
                    return True
                    
            # If no match found, try typing the value directly
            search_input.send_keys(str(value))
            time.sleep(0.2)
            
            # Approach: Try Enter key
            self.logger.info(f"Trying Enter key for value: {value}")

            # If no match found or no options appeared, just press Enter
            self.logger.info(f"No matching option found, pressing Enter for value: {value}")
            search_input.send_keys(Keys.RETURN)
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling Select2 field: {str(e)}")
            return False 

    def _get_greenhouse_field_label(self, field) -> str:
        """Get field label by traversing up parent elements until we find a label."""
        # First try to find a label that's specifically for this field
        field_id = field.get_attribute('id')
        field_type = field.get_attribute('type')
        if field_id != "" and field_type != 'file':
            try:
                label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                if label:
                    label_text = label.text.strip()
                    if label_text:
                        return label_text
            except Exception as e:
                pass
            
        elif field_type == 'file':
            if field_id != "":
                return field_id
            else:
                # Get parent div and get data-presigned-form on the div
                try:
                    parent_div = field.find_element(By.XPATH, "./ancestor::div")
                    data_presigned_form = parent_div.get_attribute('data-presigned-form')
                    if data_presigned_form:
                        return data_presigned_form
                    else:
                        return None
                except Exception:
                    return None
        
        # Find parent label and get text
        try:
            parent_label = field.find_element(By.XPATH, "./ancestor::label")
            if parent_label:
                return parent_label.text.strip()
        except Exception:
            pass

        # Default to analyzing field context
        return self.analyze_field_context(field)

    def _fill_race_field(self):
        """Fill race field that appears after selecting No for Hispanic origin."""
        try:
            # Wait for race field to appear
            race_field = self.driver.wait_and_find_element(By.ID, "race", 2)
            if not race_field:
                self.logger.warning("Could not find race field")
                return False

            # Get race from profile
            race = self.profile.get('race')
            if not race:
                self.logger.warning("No race value found in profile")
                return False

            self.logger.info(f"Found race field, filling with value: {race}")
            return self._fill_greenhouse_react_select(race_field, race)

        except Exception as e:
            self.logger.warning(f"Error filling race field: {str(e)}")
            return False
