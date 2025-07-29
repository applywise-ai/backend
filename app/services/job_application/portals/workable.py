"""Workable job portal implementation."""

from selenium.webdriver.common.by import By
from app.services.job_application.types import get_field_type
from app.schemas.application import QuestionType
from .base import BasePortal


class Workable(BasePortal):
    """Workable job portal handler."""
    
    def __init__(self, driver, profile, url=None, job_description=None, overrided_answers=None):
        """Initialize Workable portal with explicit parent initialization."""
        try:
            super().__init__(driver, profile, url, job_description, overrided_answers)
            self.logger.info("Workable portal initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing Workable portal: {str(e)}")
            raise

    def apply(self):
        """Apply to job on Workable portal using base class functionality."""
        try:
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
                    # Skip fields that shouldn't be filled
                    if self._should_skip_field(field):
                        continue
                    
                    # Use custom function to get enum type
                    question_type = self._get_workable_field_type(field)
                    
                    # Check if this is a Workable radio group
                    is_radio_group = field.tag_name == 'fieldset' and field.get_attribute('role') == 'radiogroup'
                    
                    # Get field label
                    question, is_required = self._get_workable_field_label(field)
                    
                    # Initialize form question
                    question_id = self.init_form_question(field, question_type, question, is_required, has_custom_options=is_radio_group)
                    
                    # Match field to profile data using base class method
                    answer = self.match_field_to_profile(question_id)
                    
                    # Fill the field using appropriate method
                    if is_radio_group:
                        success = self._fill_workable_radio_group(field, question_id)
                    else:
                        success = self.fill_field(field, question_id)
                        
                    if success:
                        fields_filled += 1
                        self.logger.info(f"Successfully filled field {i+1}: {answer}")
                    else:
                        self.logger.warning(f"Failed to fill field {i+1}: {answer}")
                    
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
    
    def _get_workable_field_type(self, field):
        """Get the type of field from Workable."""
        field_type = field.get_attribute('type')
        tag_name = field.tag_name
        if tag_name == 'fieldset' and field.get_attribute('role') == 'radiogroup':
            return QuestionType.SELECT
        return get_field_type(field_type, tag_name=tag_name)

    def _get_workable_field_label(self, field):
        """Get context from Workable field element using aria-labelledby, name-based labels, or base context."""
        try:
            label_element = None
            label_text = ""
            
            # Check aria-labelledby first
            aria_labelledby = field.get_attribute('aria-labelledby')
            # If there are two identifiers in labelled by use the first one
            if aria_labelledby:
                aria_labelledby = aria_labelledby.split(' ')[0] if len(aria_labelledby.split(' ')) > 1 else aria_labelledby
                
                try:
                    label_element = self.driver.find_element(By.ID, aria_labelledby)
                    label_text = label_element.text.strip()
                    if label_text:
                        self.logger.debug(f"Found label via aria-labelledby: {label_text}")
                except:
                    pass
            
            # Check for name-based label pattern: {name}_label
            if not label_text:
                name = field.get_attribute('name')
                if name:
                    label_id = f"{name}_label"
                    try:
                        label_element = self.driver.find_element(By.ID, label_id)
                        label_text = label_element.text.strip()
                        if label_text:
                            self.logger.debug(f"Found label via name pattern: {label_text}")
                    except:
                        pass
            
            # If we found a label element, check for required status in parent elements
            if label_element and label_text:
                try:
                    # Move two parents up from the label element
                    parent = label_element.find_element(By.XPATH, "../..")
                    parent_text = parent.text
                    is_required = self.is_required_field(parent_text)
                    return label_text, is_required
                except:
                    return label_text, False
            
            # Fallback to base context method
            self.logger.debug("Using base context method as fallback")
            base_context = self.analyze_field_context(field)
            return base_context, self.is_required_field(base_context)
            
        except Exception as e:
            self.logger.warning(f"Error getting field label: {str(e)}")
            base_context = self.analyze_field_context(field)
            return base_context, self.is_required_field(base_context)
    
    def _fill_workable_radio_group(self, radio_group, question_id) -> bool:
        """Fill Workable custom radio group by clicking the appropriate option wrapper."""
        try:
            value = self.form_questions[question_id].get('answer')
            self.logger.info(f"Filling Workable radio group with value: '{value}'")
            
            # Scroll to the radio group to ensure it's visible
            self.scroll_to_element(radio_group)
            
            # Find all inputs/labels
            option_elements = radio_group.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            option_labels = radio_group.find_elements(By.CSS_SELECTOR, "span[id*='radio_label_']")
            
            self.logger.info(f"Found {len(option_elements)} option elements and {len(option_labels)} option labels in radio group")
                    
            if not option_elements or not option_labels:
                self.logger.warning("No option elements found in radio group")
                return False
            
            # Match the value to the appropriate option
            option_texts = [opt.text for opt in option_labels]
            best_index = self.match_option_to_target(option_texts, question_id)
            
            if best_index is not None:
                selected_option = option_elements[best_index]
                selected_text = option_texts[best_index]
                self.logger.info(f"Selecting option: '{selected_text}' (index {best_index})")
                
                try:
                    selected_option.click()
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