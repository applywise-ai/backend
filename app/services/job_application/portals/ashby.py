"""Ashby job portal implementation."""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base import BasePortal
from app.schemas.application import QuestionType
from app.services.job_application.types import get_field_type
import time
import re


class Ashby(BasePortal):
    """Ashby job portal handler."""
    
    def __init__(self, driver, profile, url=None, job_description=None, overrided_answers=None):
        """Initialize Ashby portal with driver and user profile."""
        super().__init__(driver, profile, url, job_description, overrided_answers)
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
                    label, description, is_required = self._get_ashby_field_label(field)
                    self.logger.info(f"Field label: {label}")
                    
                    # Get field type
                    field_type = self._get_ashby_field_type(field)
                    
                    # Check if field has custom options
                    has_custom_options = bool(
                        field.tag_name == 'fieldset' or 
                        self._is_yesno_container(field) or 
                        self._is_ashby_dropdown(field)
                    )
                    
                    # Initialize form question
                    question_id = self.init_form_question(field, field_type, label, is_required, has_custom_options)

                    # Only include description for textarea fields
                    if description and field_type == QuestionType.TEXTAREA:
                        self.form_questions[question_id]['question'] = f"{label} - {description}"

                    # Match field to profile data
                    self.match_field_to_profile(question_id)
                    
                    # Check field type and fill accordingly
                    if self._is_communication_consent_radio(field):
                        self.logger.info(f"Processing communication consent radio: '{label}'")
                        success = self._fill_ashby_communication_consent_radio(field, question_id)
                    elif self._is_ashby_radio_group(field):
                        self.logger.info(f"Processing fieldset as radio group: '{label}'")
                        success = self._fill_ashby_radio_group(field, question_id)
                    elif self._is_yesno_container(field):
                        self.logger.info(f"Processing yes/no container: '{label}'")
                        success = self._fill_ashby_yesno_container(field, question_id)
                    elif self._is_ashby_dropdown(field):
                        self.logger.info(f"Processing dropdown field: '{label}'")
                        success = self._fill_ashby_dropdown(field, question_id)
                    elif self._is_datepicker_field(field):
                        self.logger.info(f"Processing datepicker field: '{label}'")
                        success = self._fill_ashby_datepicker(field, question_id)
                    else:
                        self.logger.info(f"Processing regular field: '{label}'")
                        success = self.fill_field(field, question_id)
                    
                    if success:
                        fields_filled += 1
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
        """Find all form fields on the page in DOM order."""
        try:
            # Select all relevant form fields at once
            fields = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input:not([type='radio']):not([type='checkbox']), textarea, select, fieldset, div[class*='_yesno'], div[class*='_phoneNumberConsent']"
            )

            self.logger.info(f"Found {len(fields)} form fields in DOM order")

            return fields

        except Exception as e:
            self.logger.warning(f"Error finding form fields: {str(e)}", exc_info=True)
            return []
    
    def _is_datepicker_field(self, field) -> bool:
        """Check if field is a datepicker by looking for react-datepicker class in parent div."""
        try:
            # Check if the field itself has datepicker-related attributes
            if field.get_attribute('type') == 'date':
                return True
            
            # Check if any parent element has react-datepicker class
            current = field
            max_attempts = 3  # Prevent infinite loop
            attempts = 0
            
            while current and attempts < max_attempts:
                try:
                    class_attr = current.get_attribute('class') or ''
                    if 'react-datepicker' in class_attr:
                        return True
                    
                    # Move up to parent
                    current = current.find_element(By.XPATH, "..")
                    attempts += 1
                except:
                    break
            
            return False
        except Exception as e:
            self.logger.warning(f"Error checking datepicker field: {str(e)}")
            return False

    def _get_ashby_field_type(self, field) -> QuestionType:
        """Get field type based on field attributes."""
        if self._is_datepicker_field(field):
            return QuestionType.DATE
        elif field.tag_name == 'fieldset':
            return QuestionType.SELECT
        elif self._is_yesno_container(field):
            return QuestionType.SELECT
        elif self._is_ashby_dropdown(field):
            return QuestionType.SELECT
        elif self._is_communication_consent_radio(field):
            return QuestionType.CHECKBOX
        else:
            return get_field_type(field.get_attribute('type'), field.tag_name)
    
    def _get_ashby_field_label(self, field) -> tuple[str, bool]:
        """Get field label using Ashby's specific label[for] pattern and include description if available."""
        try:
            # Handle fieldsets, listboxes, and datepickers differently
            if self._is_ashby_dropdown(field) or self._is_yesno_container(field) or self._is_ashby_radio_group(field) or self._is_datepicker_field(field):
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
                                label_description = None
                                
                                # Try to find description in the same parent
                                try:
                                    description = current.find_element(By.CSS_SELECTOR, ".ashby-application-form-question-description")
                                    if description:
                                        desc_text = description.text.strip()
                                        if desc_text:
                                            label_description = desc_text
                                except:
                                    pass
                                
                                is_required = 'required' in (label.get_attribute("class") or "")
                                return label_text, label_description, is_required
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
                            if label:
                                label_text = label.text.strip()
                                is_required = 'required' in (label.get_attribute("class") or "")
                                return label_text, None, is_required
                    except:
                        pass
                except:
                    pass
            
            if self._is_communication_consent_radio(field):
                return "Do you consent to receive text message updates from us regarding this application?", None, False

            # For other elements, use the for attribute approach
            field_id = field.get_attribute('id')
            if not field_id:
                fallback_label = self.analyze_field_context(field)
                return fallback_label, None, self.is_required_field(fallback_label)
            
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
                    
                    is_required = 'required' in (label.get_attribute("class") or "")
                    return label_text, None, is_required
            except:
                pass
            
            fallback_label = self.analyze_field_context(field)
            return fallback_label, None, self.is_required_field(fallback_label)
            
        except Exception as e:
            self.logger.warning(f"Error getting Ashby field label: {str(e)}")
            fallback_label = self.analyze_field_context(field)
            return fallback_label, None, self.is_required_field(fallback_label)
    
    def _fill_ashby_radio_group(self, fieldset, question_id: str):
        """Fill Ashby radio group (single select) or multiselect group by finding and clicking matching options."""
        try:
            value = self.form_questions[question_id].get('answer')
            label = self.form_questions[question_id].get('question')
            
            self.logger.info(f"Filling Ashby radio group with value: '{value}'")

            self.scroll_to_element(fieldset)
        
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
                    label_element = option_div.find_element(By.TAG_NAME, "label")
                    option_text = label_element.text.strip()
                    option_elements.append({
                        'element': input_element,
                        'label': label_element,
                        'text': option_text
                    })
                    self.logger.info(f"Option {i+1}: '{option_text}'")
                except Exception as e:
                    self.logger.info(f"Failed to get label for option {i+1}: {str(e)}")
                    continue
            
            if not option_elements:
                self.logger.warning("No valid option elements found in radio group")
                return False
            
            is_multiselect = option_elements[0]['element'].get_attribute('type') == 'checkbox'
            
            # Find matches for all target values
            option_texts = [opt['text'] for opt in option_elements]
            matched_indices = self.match_option_to_target(option_texts, question_id, multiple=is_multiselect)
                
            if not is_multiselect and matched_indices is not None:
                matched_indices = [matched_indices]

            self.logger.info(f"Matched indices: {matched_indices}")
            
            if not matched_indices:
                self.logger.warning(f"No match found for '{value}'")
                return False
            
            # Click all matched options
            for index in matched_indices:
                try:
                    option = option_elements[index]
                    selected_text = option['text']
                    self.logger.info(f"Selecting option: '{selected_text}' (index {index})")
                    
                    # Use the driver's wait_and_click_element method for the label
                    self.driver.wait_and_click_element(element=option['label'])
                    self.logger.info(f"Successfully clicked option: '{selected_text}'")
                    
                except Exception as e:
                    self.logger.error(f"Failed to click option {index}: {str(e)}")
                    continue
                
            self.logger.info(f"Successfully filled Ashby radio group with value: '{value}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling Ashby radio group: {str(e)}")
            return False

    def _is_communication_consent_radio(self, field) -> bool:
        """Check if field is a communication consent radio."""
        try:
            return 'phoneNumberConsent' in field.get_attribute('class')
        except:
            return False

    def _is_ashby_radio_group(self, field) -> bool:
        """Check if field is an Ashby radio group."""
        try:
            return field.tag_name == 'fieldset'
        except:
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

    def _fill_ashby_communication_consent_radio(self, field, question_id: str):
        """Fill Ashby communication consent radio by clicking the appropriate button."""
        try:
            value = self.form_questions[question_id].get('answer')
            self.logger.info(f"Filling Ashby communication consent radio with value: '{value}'")

            self.scroll_to_element(field)

            # Find radio buttons
            consent_labels = field.find_elements(By.CSS_SELECTOR, "label")
            consent_labels_texts = [label.text.strip() for label in consent_labels]

            # Match the value to the appropriate button
            best_index = self.match_option_to_target(consent_labels_texts, question_id)

            if best_index is not None:
                self.driver.wait_and_click_element(element=consent_labels[best_index])

            return True
        except:
            return False

    def _fill_ashby_yesno_container(self, yesno_container, question_id: str):
        """Fill Ashby yes/no container by clicking the appropriate button."""
        try:
            value = self.form_questions[question_id].get('answer')
            label = self.form_questions[question_id].get('question')
            
            self.logger.info(f"Filling Ashby yes/no container with value: '{value}'")
            
            self.scroll_to_element(yesno_container)

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
            best_index = self.match_option_to_target(button_texts, question_id)
            
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

    def _fill_ashby_dropdown(self, field, question_id: str) -> bool:
        """Fill Ashby dropdown input by typing and selecting first option."""
        try:
            value = self.form_questions[question_id].get('answer')
            question = self.form_questions[question_id].get('question')
            is_required = self.form_questions[question_id].get('is_required')
            if not value:
                # Use ai to get value
                if "location" in question.lower():
                    question = "What is your current location?"
                ai_result = self.ai_assistant.answer_question(
                    question=question, 
                    field_type=QuestionType.INPUT, 
                    is_required=is_required,
                    previous_question=self.last_question,
                    previous_answer=self.last_answer
                )
                if ai_result is not None:
                    value, is_open_ended = ai_result
                    self.form_questions[question_id]['pruned'] = True
                    self.form_questions[question_id]['answer'] = value
                    self.form_questions[question_id]['ai_custom'] = is_open_ended

            self.logger.info(f"Filling Ashby dropdown with value: {value}")
            
            # Scroll and click the input field
            self.driver.wait_and_click_element(element=field)

            # Type the value
            if value is not None:
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

    def _fill_ashby_datepicker(self, field, question_id: str) -> bool:
        """Fill Ashby datepicker field by entering the date value."""
        try:
            question = self.form_questions[question_id].get('question')
            value = self.form_questions[question_id].get('answer')
            if not value:
                return False

            self.logger.info(f"Filling Ashby datepicker with value: {value}")
            
            # Scroll to the field
            self.scroll_to_element(field)

            # Validate the date format otherwise use AI to answer the question
            if not self.validate_date_format(value):
                value = self.ai_assistant.answer_question(
                    question=question, 
                    field_type=QuestionType.DATE,
                    previous_question=self.last_question,
                    previous_answer=self.last_answer
                )
            
            # Clear and enter the date value
            field.clear()
            field.send_keys(str(value))
            
            # Press Tab or Enter to confirm the date
            field.send_keys("\t")
            
            self.logger.info(f"Successfully filled datepicker with: {value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling Ashby datepicker: {str(e)}")
            return False
    
    def validate_date_format(self, date_str: str) -> bool:
        """Validate date format using regex."""
        try:
            # Check if date matches MM/DD/YYYY format
            return re.match(r'^\d{2}/\d{2}/\d{4}$', date_str) is not None
        except:
            return False