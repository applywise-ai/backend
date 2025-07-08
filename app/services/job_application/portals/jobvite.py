"""Jobvite job portal implementation."""

from selenium.webdriver.common.by import By
from .base import BasePortal


class Jobvite(BasePortal):
    """Jobvite job portal handler."""
    
    def __init__(self, driver, profile):
        """Initialize Jobvite portal with driver and user profile."""
        super().__init__(driver, profile)
        self.logger.info("Jobvite portal initialized successfully")
    
    def apply(self):
        """Apply to job on Jobvite portal using base class functionality."""
        try:
            self.logger.info("Starting to fill out Jobvite application form")
            
            # Process all form fields using base class methods
            self._process_all_form_fields()
            
            self.logger.info("Successfully completed Jobvite application form")
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling Jobvite form: {str(e)}")
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
                    field_type = field.tag_name
                    field_id = field.get_attribute('id') or 'no-id'
                    self.logger.info(f"Processing field {i+1}: {field_type} (id: {field_id})")
                    
                    # Skip fields that shouldn't be filled
                    if self._should_skip_field(field):
                        skip_reason = self._get_skip_reason(field) if hasattr(self, '_get_skip_reason') else "unknown reason"
                        self.logger.info(f"Skipping field {i+1}: {skip_reason}")
                        continue
                    
                    # Analyze field context using base class method
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
                    
                    # Fill the field using base class method
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
            
            self.logger.info(f"Found {len(input_fields)} input fields, {len(textarea_fields)} textarea fields, {len(select_fields)} select fields")
            
        except Exception as e:
            self.logger.warning(f"Error finding form fields: {str(e)}")
        
        return fields 