"""Greenhouse job portal implementation."""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .base import BasePortal
from app.services.job_application.types import get_field_type
from app.schemas.application import QuestionType

class Greenhouse(BasePortal):
    """Greenhouse job portal handler."""
    
    def __init__(self, driver, profile, url=None, job_description=None, overrided_answers=None):
        """Initialize Greenhouse portal with driver and user profile."""
        super().__init__(driver, profile, url, job_description, overrided_answers)
        self.is_new_portal = self.url and 'job-boards.greenhouse.io' in self.url
        self.logger.info("Greenhouse portal initialized successfully")
    
    def apply(self):
        """Apply to job on Greenhouse."""
        try:
            # Only click Apply button for new Greenhouse portal
            if self.is_new_portal:
                try:
                    apply_button = self.driver.wait_and_find_element(By.XPATH, "//button[contains(text(), 'Apply')]", 5)
                    if apply_button:
                        self.logger.info("Found Apply button, clicking it")
                        self.driver.wait_and_click_element(element=apply_button)
                    else:
                        self.logger.warning("Could not find Apply button")
                except Exception as e:
                    self.logger.warning(f"Error clicking Apply button: {str(e)}")
            else:
                self.logger.info("Old Greenhouse portal detected, skipping Apply button click")

            # Handle education section if present
            self._handle_greenhouse_education_section()

            # Process all form fields
            self._process_all_form_fields()
            
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

                    has_options = is_react_select or is_select2
                    
                    # Get field type
                    field_type = self._get_greenhouse_field_type(field, has_options)
                    
                    # Get field label by traversing parents
                    label = self._get_greenhouse_field_label(field)
                    
                    # Check if field is required
                    is_required = self.is_required_field(label)
                    
                    # Initialize form question
                    question_id = self.init_form_question(field, field_type, label, is_required, has_options)
                    
                    # Match field to profile data using base class method
                    self.match_field_to_profile(question_id)
                    
                    # Fill the field using appropriate method
                    if is_react_select:
                        success = self._fill_greenhouse_react_select(field, question_id)
                    elif is_select2:
                        success = self._fill_greenhouse_select2_field(field, question_id)
                    else:
                        success = self.fill_field(field, question_id)

                    if success:
                        fields_filled += 1
                        self.logger.info(f"Successfully filled field {i+1}")
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
    
    def _get_greenhouse_field_type(self, field, has_options: bool) -> QuestionType:
        """Get field type based on field attributes."""
        if has_options:
            return QuestionType.SELECT
        return get_field_type(field.get_attribute('type'), field.tag_name)
    
    def _handle_greenhouse_education_section(self):
        """Handle Greenhouse custom education section with dynamic creation and filling."""
        try:
            # Check if education section exists
            if self.is_new_portal:
                education_section = self.driver.find_elements(By.CSS_SELECTOR, ".education--container")
            else:
                education_section = self.driver.find_elements(By.ID, "education_section")
            self.logger.info(f"Found {len(education_section)} education section(s)")
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
                    self._add_greenhouse_education_entry(education_section[0])
                
        except Exception:
            self.logger.error(f"Error handling Greenhouse education section")
    
    def _add_greenhouse_education_entry(self, education_container):
        """Add a new education entry by clicking the 'Add another education' button."""
        try:
            if self.is_new_portal:
                # For new portal, find add-another-button within education container
                add_button = education_container.find_element(By.CSS_SELECTOR, ".add-another-button")
            else:
                # For old portal, use the existing logic
                add_button = self.driver.find_element(By.ID, "add_education")
            
            if add_button and add_button.is_displayed():
                self.driver.wait_and_click_element(element=add_button)
                self.logger.info(f"Added education entry")
            else:
                self.logger.warning(f"Could not find add button")
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
    
    def _fill_greenhouse_react_select(self, field, question_id: str) -> bool:
        """Fill Greenhouse React Select component."""
        try:
            value = self.form_questions[question_id].get('answer')
            
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

            if is_autocomplete and value is not None:
                field.send_keys(value[:7])
            
            # Get field ID to find the listbox
            field_id = field.get_attribute('id')
            listbox_id = f"react-select-{field_id}-listbox" if field_id else None
            
            try:
                # Try to find options in the listbox if we have an ID
                if listbox_id:
                    self.logger.info(f"Looking for options in listbox: {listbox_id}")
                    try:
                        option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{listbox_id} div[role='option']", 2)
                    except Exception:
                        self.remove_focus()
                        self.driver.wait_and_click_element(element=field)
                        option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{listbox_id} div[role='option']", 4)
                        self.logger.info(f"Found {len(option_elements)} options in listbox after clicking outside") 

                    if option_elements:
                        # If there are more than 10 options, type into the field and wait for options to change
                        if len(option_elements) >= 20 and value is not None:
                            self.form_questions[question_id]['pruned'] = True
                            field.send_keys(value)
                            option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{listbox_id} div[role='option']", 2)
                            if not option_elements:
                                self.logger.info(f"No options found after typing, clearing field")
                                field.clear()
                                option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{listbox_id} div[role='option']", 2)
                        
                        self.logger.info(f"Found {len(option_elements)} options in listbox")
                        option_texts = [elem.get_attribute('textContent') or '' for elem in option_elements]
                        best_index = self.match_option_to_target(option_texts, question_id)
                        if best_index is not None:
                            option_elements[best_index].click()
                            return True
                
                # If still no match found and it's autocomplete, just press enter
                if is_autocomplete:
                    self.logger.info("No matching option found for autocomplete, pressing enter")
                    field.send_keys(Keys.ENTER)
                    return True

                return False
                
            except Exception:
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
    
    def _fill_greenhouse_select2_field(self, field, question_id: str) -> bool:
        """Fill Greenhouse Select2 field using label ID approach."""
        try:
            value = self.form_questions[question_id].get('answer')
            question = self.form_questions[question_id].get('question')
            
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
                try:
                    option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{aria_controls} li", 2)
                    self.logger.info(f"Found {len(option_elements)} options in listbox")
                except Exception:
                    self.remove_focus()
                    self.driver.wait_and_click_element(element=parent_div)
                    option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{aria_controls} li", 4)

                if len(option_elements) >= 20 and value is not None:
                    self.form_questions[question_id]['pruned'] = True
                    initial_count = len(option_elements)
                    search_input.send_keys(value)
                    
                    # Wait for options to change after typing
                    option_elements = self.driver.wait_for_options_to_change(
                        f"#{aria_controls} li", 
                        initial_count,
                    )
                    
                    self.logger.info(f"Found {len(option_elements)} options in listbox after typing")
                    if not option_elements:
                        self.logger.info(f"No options found, clearing field")
                        search_input.clear()
                        option_elements = self.driver.wait_and_find_elements(By.CSS_SELECTOR, f"#{aria_controls} li", 2)

                # Find the best matching option
                option_texts = [elem.get_attribute('textContent') or '' for elem in option_elements]
                
                best_index = self.match_option_to_target(option_texts, question_id)
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
                # Check upload label
                upload_label = self.driver.find_element(By.ID, f"upload-label-{field_id}")
                if upload_label:
                    return upload_label.text.strip()
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
        
        # Check if aria-label is present
        aria_label = field.get_attribute('aria-label')
        if aria_label != "" and aria_label is not None:
            return aria_label
        
        # Find parent label and get text
        try:
            parent_label = field.find_element(By.XPATH, "./ancestor::label")
            if parent_label:
                return parent_label.text.strip()
        except Exception:
            pass

        # Default to analyzing field context
        return self.analyze_field_context(field)
