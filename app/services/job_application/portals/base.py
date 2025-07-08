"""Base portal class for job application portals."""

import logging
import os
import time
import requests
import tempfile
from urllib.parse import urlparse
from abc import ABC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from rapidfuzz import fuzz
from textdistance import jaccard, levenshtein
from app.services.browser import CustomWebDriver
from app.services.job_application.utils.helpers import clean_string
from app.schemas.application import Education

logger = logging.getLogger(__name__)


class BasePortal(ABC):
    """Base class for all job application portals."""
    
    def __init__(self, driver: CustomWebDriver, profile: dict):
        """Initialize portal with driver and user profile."""
        self.driver = driver
        self.profile = profile
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Track how many times each profile key has been used
        self.filled_profile_keys = {}
        
        # Define field mappings with keywords for profile matching
        self.field_mappings = {
            # Personal Information
            'fullName': ['full name', 'name', 'fname', 'full_name', 'applicant name'],
            'firstName': ['first name', 'fname', 'first_name', 'given name', 'firstname', 'preferred first name'],
            'lastName': ['last name', 'lname', 'last_name', 'surname', 'family name', 'lastname'],
            'email': ['email', 'email address', 'e-mail', 'mail'],
            'phoneNumber': ['phone', 'telephone', 'mobile', 'phone number', 'contact number'],
            'currentLocation': ['location', 'address', 'city', 'current location', 'where are you located'],
            'resumeUrl': ['resume', 'cv', 'resume url', 'curriculum vitae', 'upload resume', 'attach resume', 'resume file', 'cv file', 'upload cv', 'attach cv', 'upload a file', 'drag and drop', 'file upload', 'attach file', 'choose file', 'browse file', 'upload document', 'attach document'],
            'resumeFilename': ['resume name', 'cv name', 'file name'],
            
            # Social Links
            'linkedin': ['linkedin', 'linkedin url', 'linkedin profile', 'linkedin link'],
            'twitter': ['twitter', 'twitter url', 'twitter profile', 'twitter link', 'twitter handle'],
            'github': ['github', 'github url', 'github profile', 'github link'],
            'portfolio': ['portfolio', 'website', 'personal website', 'portfolio url', 'portfolio link'],
            
            # Demographics
            'gender': ['gender', 'sex'],
            'veteran': ['veteran', 'military', 'veteran status', 'military service'],
            'sexuality': ['sexuality', 'sexual orientation', 'lgbtq'],
            'race': ['race', 'ethnicity', 'racial background', 'ethnic background'],
            'hispanic': ['hispanic', 'latino', 'hispanic or latino', 'latino/hispanic'],
            'disability': ['disability', 'disabled', 'disability status', 'accommodations needed'],
            'trans': ['transgender', 'trans', 'trans status'],
            
            # Work Eligibility
            'eligibleCanada': ['eligible canada', 'canada eligible', 'eligible to work in canada', 'canadian work authorization'],
            'eligibleUS': ['eligible to work', 'work authorization', 'authorized to work', 'us eligible', 'work eligible', 'eligible to work in the us', 'eligible to work in the united states', 'us work authorization', 'authorized to work in the us', 'authorized to work in the united states'],
            'usSponsorship': ['sponsorship', 'visa sponsorship', 'require sponsorship', 'need sponsorship', 'h1b sponsorship'],
            'caSponsorship': ['canada sponsorship', 'canadian sponsorship', 'require canada sponsorship'],
            'over18': ['over 18', 'age verification', 'are you over 18', '18 years old'],
            
            # Job Preferences
            'noticePeriod': ['notice period'],
            'expectedSalary': ['salary', 'expected salary', 'salary expectation', 'compensation', 'salary range', 'desired salary'],
            'roleLevel': ['role level', 'experience level', 'seniority level', 'career level', 'job level'],
            'companySize': ['company size', 'organization size', 'team size preference'],
            
            # Skills (handled as comma-separated string)
            'skills': ['skills', 'technical skills', 'key skills', 'core skills'],
            
            # Source
            'source': ['source', 'how did you hear', 'where did you hear', 'referral source', 'where did you find', 'how you heard'],
        
            # Education fields
            'school': ['school', 'university', 'college', 'institution', 'alma mater'],
            'degree': ['degree', 'qualification', 'education level', 'diploma'],
            'fieldOfStudy': ['field of study', 'major', 'subject', 'area of study', 'discipline', 'concentration'],
            'educationGpa': ['education gpa', 'academic gpa', 'university gpa', 'college gpa'],
            'educationStartMonth': ['start month', 'education start month', 'enrollment month', 'begin month'],
            'educationStartYear': ['start year', 'education start year', 'enrollment year', 'begin year'],
            'educationEndMonth': ['graduation month', 'completion month', 'end month', 'education end month'],
            'educationEndYear': ['graduation year', 'completion year', 'end year', 'education end year'],
        }
        
        # Process profile to extract derived fields (firstName, lastName from fullName)
        self._process_profile()
    
    def _process_profile(self):
        """Process profile to extract derived fields and handle nested objects."""
        # Extract firstName and lastName from fullName if not provided
        if 'fullName' in self.profile and self.profile['fullName']:
            if 'firstName' not in self.profile or not self.profile['firstName']:
                parts = self.profile['fullName'].split()
                if parts:
                    self.profile['firstName'] = parts[0]
            
            if 'lastName' not in self.profile or not self.profile['lastName']:
                parts = self.profile['fullName'].split()
                if len(parts) > 1:
                    self.profile['lastName'] = ' '.join(parts[1:])

        # Process skills list to comma-separated string
        if 'skills' in self.profile and isinstance(self.profile['skills'], list):
            self.profile['skills'] = ', '.join(self.profile['skills'])
        
        # Process location preferences
        if 'locationPreferences' in self.profile and isinstance(self.profile['locationPreferences'], list):
            self.profile['locationPreferences'] = ', '.join(self.profile['locationPreferences'])
        
        # Process hispanic/latino status - add to race if true
        if 'hispanic' in self.profile and self.profile['hispanic']:
            if 'race' not in self.profile:
                self.profile['race'] = ['Hispanic or Latino']
            else:
                self.profile['race'].append('Hispanic or Latino')
                    
        # Process industry specializations
        if 'industrySpecializations' in self.profile and isinstance(self.profile['industrySpecializations'], list):
            self.profile['industrySpecializations'] = ', '.join(self.profile['industrySpecializations'])
        
        # Process education - extract date fields and add to each education entry
        if 'education' in self.profile and isinstance(self.profile['education'], list) and self.profile['education']:
            recent_education = self.profile['education'][0]  # Assuming sorted by recency
            self.profile['educationGpa'] = recent_education.get('educationGpa', '')
            
            # Process each education entry to add date fields
            for education in self.profile['education']:
                # Process start date (fromDate)
                from_date = education.get('educationFrom', '')
                if from_date and '/' in from_date:
                    parts = from_date.split('/')
                    if len(parts) == 2:
                        education['educationStartMonth'] = parts[0].zfill(2)
                        education['educationStartYear'] = parts[1]
                
                # Process end date (toDate)
                to_date = education.get('educationTo', '')
                if to_date and '/' in to_date:
                    parts = to_date.split('/')
                    if len(parts) == 2:
                        education['educationEndMonth'] = parts[0].zfill(2)
                        education['educationEndYear'] = parts[1]

        # Process employment - only get current company if employment is current (no end date)
        if 'employment' in self.profile and isinstance(self.profile['employment'], list) and self.profile['employment']:
            recent_employment = self.profile['employment'][0]  # Assuming sorted by recency
            
            # Only set current company if there's no end date (indicating current employment)
            to_date = recent_employment.get('toDate', '')
            if not to_date or to_date.strip() == '':
                # This is current employment
                self.profile['currentCompany'] = recent_employment.get('company', '')
            else:
                # This is past employment
                self.profile['currentCompany'] = 'N/A'
            
            # Process current title
            if 'title' in recent_employment:
                self.profile['currentTitle'] = recent_employment['title']

            # Add current company field mapping
            self.field_mappings.update({
                'currentCompany': ['current company', 'employer', 'company', 'current employer', 'organization'],
                'currentTitle': ['current title', 'current role', 'current position']
            })
        
        # Add additional field mappings for missing UserProfile fields
        additional_mappings = {
            # Job Types (convert list to string)
            'jobTypes': ['job type', 'employment type', 'position type', 'work type'],
            'locationPreferences': ['location preference', 'preferred location', 'preferred office location', 'work location preference'],
            'industrySpecializations': ['industry', 'industry preference', 'specialization', 'domain expertise'],
        }
        
        # Process job types list
        if 'jobTypes' in self.profile and isinstance(self.profile['jobTypes'], list):
            job_type_mapping = {
                'full_time': 'Full Time',
                'part_time': 'Part Time', 
                'contract': 'Contract',
                'internship': 'Internship'
            }
            job_types = [job_type_mapping.get(jt, jt) for jt in self.profile['jobTypes']]
            self.profile['jobTypes'] = ', '.join(job_types)
        
        # Add all additional mappings
        self.field_mappings.update(additional_mappings)
        
        # Add standard question mappings for common legal/compliance questions
        common_question_mappings = {
            # Criminal background questions - should be False
            'convictedFelon': ['convicted of a felony', 'felony conviction', 'criminal conviction', 'convicted of a crime', 'criminal background', 'have you ever been convicted'],
            'criminalRecord': ['criminal record', 'criminal history', 'been arrested', 'pending charges'],
            
            # Background check consent - should be True
            'backgroundCheckConsent': ['background check', 'consent to background check', 'authorize background check', 'criminal background check'],
            'drugTestConsent': ['drug test', 'consent to drug test', 'drug screening', 'substance abuse test'],
            
            # General yes/no questions - default to positive responses
            'generalYes': ['confirm', 'agree', 'acknowledge', 'consent'],
        }
        
        # Set default values for standard questions
        self.profile['convictedFelon'] = False
        self.profile['criminalRecord'] = False
        self.profile['backgroundCheckConsent'] = True
        self.profile['drugTestConsent'] = True
        self.profile['generalYes'] = True
        
        # Calculate earliest start date based on notice period
        if 'noticePeriod' in self.profile and self.profile['noticePeriod']:
            try:
                import datetime
                from dateutil.relativedelta import relativedelta
                import re
                
                notice_period = str(self.profile['noticePeriod']).lower().strip()
                today = datetime.date.today()
                
                # Parse notice period and calculate start date
                if 'immediate' in notice_period:
                    earliest_start = today
                else:
                    # Extract numbers from the notice period
                    numbers = re.findall(r'\d+', notice_period)
                    number = int(numbers[0]) if numbers else 2  # Default to 2 if no number found
                    
                    # Determine the time unit and calculate
                    if 'week' in notice_period:
                        earliest_start = today + relativedelta(weeks=number)
                    elif 'month' in notice_period:
                        earliest_start = today + relativedelta(months=number)
                    else:
                        # Default to weeks if no unit specified
                        earliest_start = today + relativedelta(weeks=number)
                
                # Format as MM/DD/YYYY for form compatibility
                self.profile['earliestStartDate'] = earliest_start.strftime('%m/%d/%Y')
                
            except Exception:
                # Fallback to "Immediate" if calculation fails
                self.profile['earliestStartDate'] = today.strftime('%m/%d/%Y')
        
        self.field_mappings.update(common_question_mappings)
        
        # Add earliest start date field mapping
        self.field_mappings.update({
            'earliestStartDate': ['earliest start date', 'when can you start', 'start date', 'available start date', 'earliest availability', 'when are you available', 'availability date', 'can start on'],
        })
    
    def apply(self):
        """Abstract method to be implemented by each portal."""
        raise NotImplementedError("Each portal must implement its own apply method")
    
    def _should_skip_field(self, field) -> bool:
        """Check if field should be skipped."""
        try:
            field_type = field.get_attribute('type')
            
            # For file inputs, only check if enabled (they're often hidden but still functional)
            if field_type == 'file':
                if not field.is_enabled():
                    return True
                # Don't skip file inputs even if not visible - they're often hidden by CSS
                return False
            
            # For radio inputs, only check if enabled (they're often hidden but still functional)
            if field_type == 'radio':
                if not field.is_enabled():
                    return True
                # Don't skip radio inputs even if not visible - they're often hidden by CSS
                return False
            
            # For other inputs, skip if not visible or not enabled
            if not field.is_displayed() or not field.is_enabled():
                return True
                
            # Skip certain input types
            skip_types = ['hidden', 'submit', 'button', 'reset', 'image']
            if field_type in skip_types:
                return True
                
            # Skip if already filled (has value) - but NOT for file or radio inputs
            if field_type not in ['file', 'radio'] and field.get_attribute('value') and field.get_attribute('value').strip():
                return True
                
            return False
            
        except Exception:
            return True
    
    def _get_skip_reason(self, field) -> str:
        """Get detailed reason why field is being skipped."""
        try:
            field_type = field.get_attribute('type')
            
            # For file inputs, only check if enabled (they're often hidden but still functional)
            if field_type == 'file':
                if not field.is_enabled():
                    return "File input is not enabled"
                return "File input should not be skipped"
            
            # For radio inputs, only check if enabled (they're often hidden but still functional)
            if field_type == 'radio':
                if not field.is_enabled():
                    return "Radio input is not enabled"
                return "Radio input should not be skipped"
            
            # For other inputs, check visibility and enabled status
            if not field.is_displayed():
                return "Field is not visible"
            if not field.is_enabled():
                return "Field is not enabled"
                
            skip_types = ['hidden', 'submit', 'button', 'reset', 'image']
            if field_type in skip_types:
                return f"Field type '{field_type}' is in skip list"
                
            # Check if already filled
            if field_type not in ['file', 'radio'] and field.get_attribute('value') and field.get_attribute('value').strip():
                return f"Field already has value: '{field.get_attribute('value')[:50]}...'"
                
            return "Unknown reason"
            
        except Exception as e:
            return f"Exception checking skip reason: {str(e)}"
    
    def analyze_field_context(self, field) -> str:
        """Analyze field context to understand what data it expects."""
        try:
            context_clues = []
            
            # Get field attributes (excluding CSS classes which are just noise)
            field_name = field.get_attribute('name') or ''
            field_id = field.get_attribute('id') or ''
            field_placeholder = field.get_attribute('placeholder') or ''
            field_aria_label = field.get_attribute('aria-label') or ''
            
            # Only add meaningful attributes (skip CSS classes)
            context_clues.extend([field_name, field_id, field_placeholder, field_aria_label])
            
            # Look for associated label
            try:
                # Try to find label by 'for' attribute
                if field_id:
                    label = self.driver.find_element(By.XPATH, f"//label[@for='{field_id}']")
                    context_clues.append(label.text)
            except:
                pass
                
            try:
                # Try to find parent label
                parent_label = field.find_element(By.XPATH, "./ancestor::label")
                context_clues.append(parent_label.text)
            except:
                pass
                
            try:
                # Look for preceding sibling text
                preceding_text = field.find_element(By.XPATH, "./preceding-sibling::*[1]")
                context_clues.append(preceding_text.text)
            except:
                pass
            
            # Combine and clean context clues
            context = ' '.join(context_clues).lower().strip()
            return context
            
        except Exception:
            return ''
    
    def match_field_to_profile(self, label: str, field) -> tuple:
        """Match field context to profile data using fuzzy matching."""
        if not label:
            return None
            
        best_match = None
        best_score = 0
        best_profile_key = None

        context = clean_string(label.lower().strip())
        
        # Special handling for file inputs - if it's a file input and we have generic upload text,
        # prioritize it for resume if no other specific matches
        field_type = field.get_attribute('type')
        is_file_input = field_type == 'file'
        is_select_input = field_type == 'select' or field_type == 'select-one'
        
        # Check each profile field mapping
        for profile_key, keywords in self.field_mappings.items():
            # Calculate match score
            score = 0
            current_matches = []
            for keyword in keywords:
                if keyword in context:
                    score += len(keyword)
                    current_matches.append(keyword)
                    
            # Boost score for resume fields on file inputs with generic upload terms
            if is_file_input and profile_key == 'resumeUrl' and score > 0:
                generic_upload_terms = ['upload a file', 'drag and drop', 'file upload', 'attach file', 'choose file']
                for term in generic_upload_terms:
                    if term in context:
                        score += 10  # Boost score for generic file upload on file inputs
                        break

            if score > best_score:
                best_score = score
                best_match = self.profile.get(profile_key)
                best_profile_key = profile_key
        
        # Fallback: if this is a file input and no specific matches, try resume anyway
        if is_file_input and best_match is None and 'resumeUrl' in self.profile and self.profile['resumeUrl']:
            generic_terms = ['upload', 'file', 'attach', 'drag', 'drop', 'browse', 'choose']
            if any(term in context for term in generic_terms):
                best_match = self.profile['resumeUrl']
                best_profile_key = 'resumeUrl'
                best_score = 5  # Low score but still a match
        
        # Special handling for boolean fields
        if best_match is not None and isinstance(best_match, bool):
            return ('Yes' if best_match else 'No', best_profile_key)
        
        # Removed for now: Skip if this profile key has already been used to fill a field
        # if skip and self.is_profile_key_filled(best_profile_key):
        #     return None
        
        # Handle education fields
        if self.is_education_field(best_profile_key):
            value = self.get_education_value(best_profile_key)
            return (value, best_profile_key)

        # Special handling for select inputs - if it's a select input and we have a list of matches,
        # prioritize the first match
        self.logger.info(f"Best match: {best_match} of type {field_type} for select input: {is_select_input}")
        if is_select_input and isinstance(best_match, list):
            return (best_match[0] if len(best_match) > 0 else None, best_profile_key)

        return (best_match if best_match is not None else None, best_profile_key)
    
    def validate_field_match(self, context: str, profile_key: str, profile_value: str, field = None) -> bool:
        """Validate if a field match makes logical sense."""
        if not profile_value:
            return False

        # If profile key is resume, field type should be file
        if profile_key == 'resumeUrl' and field.get_attribute('type') != 'file':
            self.logger.info(f"Rejecting {profile_key} match for resume question: {context}")
            return False

        # GPA questions should only match GPA values, not company names
        if 'gpa' in context.lower() or 'grade point' in context.lower():
            if profile_key in ['currentCompany']:
                self.logger.info(f"Rejecting {profile_key} match for GPA question: {context}")
                return False
            # Only allow numeric-like values for GPA
            if profile_key == 'educationGpa':
                try:
                    float(str(profile_value))
                    return True
                except:
                    return False
        
        # Remote work questions should get yes/no answers, not company names
        remote_indicators = ['comfortable working from home', 'productive working from home', 'remote work']
        if any(indicator in context.lower() for indicator in remote_indicators):
            if profile_value not in ['Yes', 'No']:
                self.logger.info(f"Rejecting {profile_key} match for remote work question: {context}")
                return False
        
        # Company name questions should not match boolean values or GPA
        company_indicators = ['company name', 'employer name', 'which company', 'name of company']
        if any(indicator in context.lower() for indicator in company_indicators):
            if isinstance(profile_value, bool) or profile_key in ['remoteWorkComfortable', 'relocateWilling', 'educationGpa']:
                self.logger.info(f"Rejecting {profile_key} match for company name question: {context}")
                return False
        
        return True
    
    def fill_field(self, field, value) -> bool:
        """Utility method to fill field with the given value based on field type."""
        try:
            if not value:
                return False
            
            # Scroll to the field to ensure it's visible
            self.scroll_to_element(field)
            
            field_type = field.get_attribute('type')
            tag_name = field.tag_name.lower()
            
            # Handle different field types
            if tag_name == 'select':
                return self.fill_select_field(field, value)
            elif field_type == 'checkbox':
                return self.fill_checkbox_field(field, value)
            elif field_type == 'radio':
                return self.fill_radio_field(field, value)
            elif field_type == 'file':
                return self.fill_file_field(field, value)
            else:
                return self.fill_text_field(field, value)
                
        except Exception as e:
            self.logger.warning(f"Error filling field: {str(e)}")
            return False
    
    def fill_text_field(self, field, value) -> bool:
        """Fill text input field."""
        try:
            field.clear()
            field.send_keys(str(value))
            return True
        except Exception:
            return False
    
    def fill_select_field(self, field, value) -> bool:
        """Fill select dropdown field."""
        try:
            select = Select(field)
            value_str = str(value).lower()
            
            # Match select option by our own method
            option_texts = [option.text for option in select.options]
            best_index = self.match_option_to_target(option_texts, value_str)
            if best_index is not None:
                select.select_by_visible_text(select.options[best_index].text)
                return True
                    
            return False
        except Exception:
            return False
    
    def fill_checkbox_field(self, field, value) -> bool:
        """Fill checkbox field."""
        try:
            should_check = value is True or str(value).lower() in ['true', 'yes', '1']
            is_checked = field.is_selected()
            
            if should_check != is_checked:
                field.click()
                
            return True
        except Exception:
            return False
    
    def fill_radio_field(self, field, value) -> bool:
        """Fill radio button field."""
        try:
            should_select = value is True or str(value).lower() in ['true', 'yes', '1']
            
            if should_select and not field.is_selected():
                field.click()
                
            return True
        except Exception:
            return False
    
    def fill_file_field(self, field, value) -> bool:
        """Handle file upload field with enhanced error detection and validation."""
        temp_file_path = None
        try:
            if not isinstance(value, str) or not value:
                return False
            
            # Handle URL downloads
            if value.startswith(('http://', 'https://')):
                try:
                    
                    # Download with timeout and proper headers to avoid bot detection
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    response = requests.get(value, stream=True, timeout=30, headers=headers)
                    
                    if response.status_code == 200:
                        # Get filename from profile
                        filename = self.profile.get('resumeFilename', 'resume.pdf')
                        if not filename or filename == '':
                            # Fallback to filename from URL
                            parsed_url = urlparse(value)
                            if parsed_url.path and '/' in parsed_url.path:
                                filename = parsed_url.path.split('/')[-1]
                            else:
                                filename = 'resume.pdf'
                        
                        # Ensure filename has proper extension
                        if '.' not in filename:
                            filename += '.pdf'
                        
                        # Validate file size (10MB limit for safety)
                        content_length = response.headers.get('content-length')
                        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
                            self.logger.warning(f"File too large ({content_length} bytes) for upload")
                            return False
                        
                        # Create temporary file
                        temp_dir = tempfile.gettempdir()
                        temp_file_path = os.path.join(temp_dir, filename)
                        
                        # Download file content
                        with open(temp_file_path, 'wb') as temp_file:
                            for chunk in response.iter_content(chunk_size=8192):
                                temp_file.write(chunk)
                        
                        # Verify file was downloaded and has content
                        if os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) > 0:
                            file_size = os.path.getsize(temp_file_path)
                            self.logger.info(f"Downloaded file ({file_size} bytes) for upload")
                            
                            # Upload to field with enhanced error detection
                            return self.safe_file_upload(field, temp_file_path, filename)
                        else:
                            self.logger.error(f"Downloaded file is empty: {temp_file_path}")
                            return False
                    else:
                        self.logger.warning(f"Failed to download file - HTTP {response.status_code}")
                        return False
                        
                except Exception as e:
                    self.logger.error(f"Error downloading file: {str(e)}")
                    return False
            
            # Handle local file path
            elif value.startswith(('/', 'C:', '\\')) and os.path.exists(value):
                filename = os.path.basename(value)
                file_size = os.path.getsize(value)
                return self.safe_file_upload(field, value, filename)
            
            else:
                return False
            
        except Exception as e:
            self.logger.error(f"Error filling file field: {str(e)}")
            return False
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    self.logger.warning(f"Failed to clean up temporary file: {str(e)}")
    
    def safe_file_upload(self, field, file_path, filename) -> bool:
        """Safely upload file with error detection and validation."""
        try:
            # Get current URL to detect redirects/errors
            current_url = self.driver.current_url
            
            # Upload the file
            field.send_keys(file_path)
            
            # Wait for upload to process
            time.sleep(1)
            
            # Check if we're still on the same page (no error redirect)
            new_url = self.driver.current_url
            if current_url != new_url:
                # Check for error indicators in the page
                error_indicators = [
                    "error", "sorry", "unavailable", "removed", "not found", 
                    "invalid file", "file too large", "unsupported format"
                ]
                page_text = self.driver.page_source.lower()
                
                for indicator in error_indicators:
                    if indicator in page_text:
                        self.logger.error(f"File upload error detected: '{indicator}' found in page")
                        return False
            
            self.logger.info(f"Successfully uploaded file: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in safe file upload: {str(e)}")
            return False
    
    def _normalize_option_value(self, value) -> str:
        """Normalize option value for matching in multi-option fields."""
        if isinstance(value, bool):
            return "YES" if value else "NO"
        
        value_str = str(value).upper().strip()
        
        # Common positive responses
        if value_str in ['TRUE', '1', 'YES', 'Y', 'AGREE', 'ACCEPT', 'WILLING', 'COMFORTABLE']:
            return "YES"
        
        # Common negative responses
        if value_str in ['FALSE', '0', 'NO', 'N', 'DISAGREE', 'DECLINE', 'NOT WILLING', 'NOT COMFORTABLE']:
            return "NO"
        
        return value_str
    
    def match_option_to_target(self, options: list, target_value: str):
        """Find the best matching option from a list of option strings.
        
        Args:
            options: List of option strings to match against
            target_value: The target value to match
            
        Returns:
            Index of the best matching option, or None if no good match found
        """
        if not options:
            return None
            
        # Normalize target value
        target_value = self._normalize_option_value(target_value)
        
        # Check if options exceed 10
        exceed_options = len(options) > 10

        best_index = None
        best_score = 0
        
        for i, option_text in enumerate(options):
            try:
                if not option_text or (exceed_options and option_text.lower()[0] != target_value.lower()[0]):
                    continue
                   
                # Normalize option text
                normalized_option = option_text.strip().upper()
                score = self._calculate_option_score(normalized_option, target_value)
                
                if score > best_score:
                    best_score = score
                    best_index = i
                    
            except Exception:
                continue
        
        # Only return if we have a reasonable match (score >= 0.45)
        if best_score >= 0.45:
            return best_index
        else:
            return None
    
    def average_score(self, input_str: str, choice: str) -> float:
        """Calculate a levenshtein and jaccard score."""

        # Base scores
        scores = [
            jaccard.normalized_similarity(input_str, choice),
            levenshtein.normalized_similarity(input_str, choice)
        ]
        return sum(scores) / len(scores)

    def _calculate_option_score(self, option_text: str, target_value: str) -> int:
        """Calculate similarity score between option text and target value."""
        # Perfect match
        if option_text == target_value:
            return 100
        
        # Special matching for common patterns
        if target_value == "YES":
            if option_text in ["YES", "Y", "TRUE", "AGREE", "ACCEPT", "WILLING", "COMFORTABLE"]:
                return 95
        
        if target_value == "NO":
            if option_text in ["NO", "N", "FALSE", "DISAGREE", "DECLINE", "NOT WILLING", "NOT COMFORTABLE"]:
                return 95
        
        # Direct substring match
        if target_value in option_text:
            return 90
        
        if option_text in target_value:
            return 85
        
        # Special handling for comma-separated values
        if ',' in target_value:
            target_parts = [part.strip() for part in target_value.split(',')]
            for part in target_parts:
                clean_part = part.replace('-', ' ').replace('_', ' ')
                if clean_part in option_text or option_text in clean_part:
                    return 80
                
                # Check if all words from the part appear in the option
                part_words = clean_part.split()
                if len(part_words) > 1 and all(word in option_text for word in part_words):
                    return 75
        
        # Clean up target value for better matching
        clean_target = target_value.replace('-', ' ').replace('_', ' ')
        if clean_target in option_text or option_text in clean_target:
            return 70
        
        # Word-based fuzzy matching
        return self.average_score(target_value, option_text)
    
    def fill_option_group_fallback(self, option_elements, target_value: str) -> bool:
        """Fallback method to fill multi-option group when no exact match is found."""
        try:
            # For boolean-like questions, default to first option if positive, second if negative
            if target_value in ["YES", "TRUE"]:
                if len(option_elements) >= 1:
                    # Scroll to the option before clicking
                    self.scroll_to_element(option_elements[0])
                    option_elements[0].click()
                    self.logger.info("Fallback: Selected first option for positive response")
                    return True
            
            elif target_value in ["NO", "FALSE"]:
                if len(option_elements) >= 2:
                    # Scroll to the option before clicking
                    self.scroll_to_element(option_elements[1])
                    option_elements[1].click()
                    self.logger.info("Fallback: Selected second option for negative response")
                    return True
                elif len(option_elements) >= 1:
                    # Scroll to the option before clicking
                    self.scroll_to_element(option_elements[0])
                    option_elements[0].click()
                    self.logger.info("Fallback: Selected first (only) option")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in option group fallback: {str(e)}")
            return False
    
    def get_education_value(self, profile_key):
        """Get education value based on how many times we've seen this profile key."""
        try:
            # Get the usage count directly from filled_profile_keys
            usage_count = self.filled_profile_keys.get(profile_key, 0)
            
            # Get education list from profile
            education_list = self.profile.get('education', [])
            
            # If we have education entries and our index is valid
            if education_list and usage_count < len(education_list):
                education_entry = education_list[usage_count]
                
                value = education_entry.get(profile_key, '')
                return value
            
            return None
            
        except Exception:
            self.logger.warning(f"Error getting education value for {profile_key}")
            return None

    def mark_profile_key_filled(self, profile_key: str):
        """Increment the usage count for a profile key."""
        if profile_key not in self.filled_profile_keys:
            self.filled_profile_keys[profile_key] = 0
        self.filled_profile_keys[profile_key] += 1
    
    def is_profile_key_filled(self, profile_key: str) -> bool:
        """Check if a profile key has already been used to fill a field."""
        return profile_key in self.filled_profile_keys
    
    def is_required_field(self, label: str) -> bool:
        """Check if a field is required."""
        return "*" in label

    def is_education_field(self, profile_key: str) -> bool:
        """Check if a field is in the education section."""
        return profile_key in Education.model_fields

    def remove_focus(self):
        """Remove focus from an element."""
        # Click on the body to dismiss any open dropdowns
        self.driver.find_element(By.TAG_NAME, "body").click()

    def scroll_to_element(self, element):
        """Scroll to an element to ensure it's visible before interacting with it."""
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", element)
        except Exception:
            self.logger.warning("Error scrolling to element")
    