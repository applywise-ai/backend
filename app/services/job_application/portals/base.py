"""Base portal class for job application portals."""

import logging
import os
import uuid
import time
import requests
import tempfile
from typing import Any
from urllib.parse import urlparse
from abc import ABC
from collections import defaultdict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from textdistance import jaccard, levenshtein
from app.services.browser import CustomWebDriver
from app.services.job_application.utils.helpers import clean_string
from app.schemas.application import Education, FormQuestion, FormSectionType
from app.services.ai_assistant import AIAssistant
from app.services.job_application.types import map_profile_value
from app.schemas.application import QuestionType
from app.services.job_application.types import DEMOGRAPHIC_FIELDS
from app.services.storage import storage_manager

logger = logging.getLogger(__name__)


class BasePortal(ABC):
    """Base class for all job application portals."""
    
    def __init__(self, driver: CustomWebDriver, profile: dict, url: str = None, job_description: str = None, overrided_answers: dict = None):
        """Initialize portal with driver and user profile."""
        self.driver = driver
        self.profile = profile
        self.url = url
        self.job_description = job_description
        self.overrided_answers = overrided_answers
        self.logger = logging.getLogger(self.__class__.__name__)

        self.temp_file_paths = []

        # Track the form questions that have been asked
        self.form_questions: dict[str, FormQuestion] = {}
        
        # Count occurrences of clean labels
        self.counted_labels = defaultdict(int)

        # Track count for order of form questions
        self.form_question_count = 0

        # Track last question and answer for context
        self.last_question = None
        self.last_answer = None
        self.last_question_id = None

        self.confident_mapping_keys = ['linkedin', 'twitter', 'github', 'portfolio', 'other']

        # Define field mappings with keywords for profile matching
        self.field_mappings = {
            # Personal Information
            'fullName': ['full name', 'name', 'fname', 'full_name', 'applicant name'],
            'firstName': ['first name', 'fname', 'first_name', 'given name', 'firstname', 'preferred first name'],
            'lastName': ['last name', 'lname', 'last_name', 'surname', 'family name', 'lastname'],
            'email': ['email', 'email address', 'e-mail', 'mail'],
            'phoneNumber': ['phone', 'telephone', 'mobile', 'phone number', 'contact number'],
            'currentLocation': ['address', 'city', 'current location', 'where are you located', 'location city'],
            'resume': ['resume', 'cv', 'resumecv', 'resume url', 'curriculum vitae', 'upload resume', 'attach resume', 'resume file', 'cv file', 'upload cv', 'attach cv', 'upload a file', 'drag and drop', 'file upload', 'attach file', 'choose file', 'browse file', 'upload document', 'attach document'],
            'resumeFilename': ['resume name', 'cv name', 'file name'],
            'coverLetterPath': ['cover letter', 'cover letter url', 'cover letter file', 'upload cover letter', 'attach cover letter'],
            
            # Social Links
            'linkedin': ['linkedin', 'linkedin url', 'linkedin profile', 'linkedin link'],
            'twitter': ['twitter', 'twitter url', 'twitter profile', 'twitter link', 'twitter handle'],
            'github': ['github', 'github url', 'github profile', 'github link'],
            'portfolio': ['portfolio', 'website', 'personal website', 'portfolio url', 'portfolio link'],
            'other': ['other website'],
            
            # Demographics
            'gender': ['gender', 'sex'],
            'veteran': ['veteran', 'military', 'veteran status', 'military service'],
            'sexuality': ['sexuality', 'sexual orientation', 'lgbtq'],
            'race': ['race', 'ethnicity', 'racial background', 'ethnic background'],
            'hispanic': ['hispanic', 'latino', 'hispanic or latino', 'latino/hispanic'],
            'disability': ['disability', 'disabled', 'disability status', 'accommodations needed'],
            'trans': ['transgender', 'trans status'],
            
            # Work Eligibility
            'eligibleCanada': ['eligible canada', 'canada eligible', 'eligible to work in canada', 'canadian work authorization'],
            'eligibleUS': ['eligible to work', 'work authorization', 'authorized to work', 'us eligible', 'work eligible', 'eligible to work in the us', 'eligible to work in the united states', 'us work authorization', 'authorized to work in the us', 'authorized to work in the united states'],
            'usSponsorship': ['visa sponsorship', 'require sponsorship', 'need sponsorship', 'h1b sponsorship', 'future sponsorship', 'future work authorization'],
            'caSponsorship': ['canada sponsorship', 'canadian sponsorship', 'require canada sponsorship'],
            'over18': ['over 18', 'age verification', 'are you over 18', '18 years old'],
            
            # Job Preferences
            'noticePeriod': ['notice period'],
            'expectedSalary': ['salary', 'expected salary', 'salary expectation', 'compensation', 'salary range', 'desired salary'],
            'roleLevel': ['role level', 'experience level', 'seniority level', 'career level', 'job level'],
            'companySize': ['company size', 'organization size', 'team size preference'],
            'jobTypes': ['job type', 'employment type', 'position type', 'work type'],
            'locationPreferences': ['location preference', 'preferred location', 'preferred office location', 'work location preference'],
            'industrySpecializations': ['industry preference', 'specialization', 'domain expertise'],

            # Skills (handled as comma-separated string)
            'skills': ['skills', 'technical skills', 'key skills', 'core skills'],
            
            # Source
            'source': ['source', 'how did you hear', 'where did you hear', 'referral source', 'where did you find', 'how you heard'],
        
            # Education fields
            'school': ['school', 'university', 'college', 'alma mater'],
            'degree': ['degree', 'qualification', 'education level', 'diploma'],
            'fieldOfStudy': ['field of study', 'major', 'subject', 'area of study', 'discipline', 'concentration'],
            'educationGpa': ['education gpa', 'academic gpa', 'university gpa', 'college gpa', 'gpa'],
            'educationStartMonth': ['start month', 'education start month', 'enrollment month', 'begin month', 'start date month'],
            'educationStartYear': ['start year', 'education start year', 'enrollment year', 'begin year', 'start date year'],
            'educationEndMonth': ['graduation month', 'completion month', 'end month', 'education end month', 'end date month', 'graduation date month'],
            'educationEndYear': ['graduation year', 'completion year', 'end year', 'education end year', 'end date year', 'graduation date year'],
        }

        # Process profile to extract derived fields for manual matching (firstName, lastName from fullName)
        self._process_profile()

        # Initialize ai assistant
        self.ai_assistant = AIAssistant(self.profile, job_description=job_description)
    
    def init_form_question(self, question_element, question_type: QuestionType, label: str, required: bool = False, has_custom_options: bool = False) -> str:
        """
        Initialize a new form question and return its unique ID.
        
        Args:
            question_element: The element of the question
            question_type: The type of question (from QuestionType enum)
            label: The label/question text
            required: Whether the question is required
            has_custom_options: Whether the question has custom options
        
        Returns:
            str: The unique ID of the created form question
        """
        # Generate unique ID
        question_id = str(uuid.uuid4())

        # Cleaned label - remove * for required fields
        cleaned_label = label.replace('*', '').replace('✱', '').strip()

        # Count the occurrence of this label
        self.counted_labels[cleaned_label] += 1

        # Increment the form question count
        self.form_question_count += 1

        # Create the form question entry
        form_question = {
            'element': question_element,
            'type': question_type,
            'question': cleaned_label,
            'required': required,
            'placeholder': question_element.get_attribute('placeholder'),
            'has_custom_options': has_custom_options,
            'unique_label_id': cleaned_label + str(self.counted_labels[cleaned_label]),
            'count': self.form_question_count,
            'ai_custom': False,  # Default to False, will be updated when AI is used
        }
        
        # Store in the form_questions map
        self.form_questions[question_id] = form_question

        return question_id

    def delete_form_question(self, question_id: str) -> bool:
        """
        Delete a form question by its ID.
        
        Args:
            question_id: The unique ID of the question to delete
        
        Returns:
            bool: True if the question was found and deleted, False otherwise
        """
        if question_id in self.form_questions:
            deleted_question = self.form_questions.pop(question_id)
            if deleted_question.get('question', 'Unknown') in self.counted_labels:
                del self.counted_labels[deleted_question.get('question', 'Unknown')]
            self.logger.info(f"Deleted form question with ID {question_id}: {deleted_question.get('question', 'Unknown')}")
            return True
        else:
            self.logger.warning(f"Attempted to delete non-existent form question with ID {question_id}")
            return False

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
        
        # Process hispanic/latino status - add to race if true
        if 'hispanic' in self.profile and self.profile['hispanic']:
            if 'race' not in self.profile:
                self.profile['race'] = ['Hispanic or Latino']
            else:
                self.profile['race'].append('Hispanic or Latino')
        
        # Process education - extract date fields and add to each education entry
        if 'education' in self.profile and isinstance(self.profile['education'], list) and self.profile['education']:
            recent_education = self.profile['education'][0]  # Assuming sorted by recency
            self.profile['educationGpa'] = recent_education.get('educationGpa', '')
            
            # Process each education entry to add date fields
            for education in self.profile['education']:
                # Map degree to degree field
                if 'degree' in education:
                    education['degree'] = map_profile_value('degree', education['degree'])

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
                'currentTitle': ['current title', 'current role', 'current position', 'job title']
            })
        
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

        # Add earliest start date field mapping
        self.field_mappings.update({
            'earliestStartDate': ['earliest start date', 'when can you start', 'start working', 'start date', 'available start date', 'earliest availability', 'when are you available', 'availability date', 'can start on'],
        })
        
        # Process profile values using the type mappings
        profile_fields_to_map = ['jobTypes', 'locationPreferences', 'industrySpecializations', 'roleLevel', 'companySize']
        for field_key in profile_fields_to_map:
            if field_key in self.profile and self.profile[field_key]:
                self.profile[field_key] = map_profile_value(field_key, self.profile[field_key])
        
        # Process social media links - add prefixes if only usernames are provided
        if 'linkedin' in self.profile and self.profile['linkedin']:
            linkedin_value = self.profile['linkedin']
            if not linkedin_value.startswith('http'):
                # Add LinkedIn prefix if it's just a username
                self.profile['linkedin'] = f"https://linkedin.com/in/{linkedin_value}"
        
        if 'github' in self.profile and self.profile['github']:
            github_value = self.profile['github']
            if not github_value.startswith('http'):
                # Add GitHub prefix if it's just a username
                self.profile['github'] = f"https://github.com/{github_value}"
        
        if 'twitter' in self.profile and self.profile['twitter']:
            twitter_value = self.profile['twitter']
            if not twitter_value.startswith('http'):
                # Add Twitter prefix if it's just a username
                self.profile['twitter'] = f"https://twitter.com/{twitter_value}"
        
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

        self.field_mappings.update(common_question_mappings)
    
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
            
            if field_type == 'checkbox':
                if not field.is_enabled():
                    return True
                # Don't skip checkbox inputs even if not visible - they're often hidden by CSS
                return False
            
            # For other inputs, skip if not visible or not enabled
            if not field.is_displayed() or not field.is_enabled():
                return True
                
            # Skip certain input types
            skip_types = ['hidden', 'submit', 'button', 'reset', 'image']
            if field_type in skip_types:
                return True
                
            # Skip if already filled (has value) - but NOT for file or radio inputs
            if field_type not in ['file', 'radio', 'checkbox'] and field.get_attribute('value') and field.get_attribute('value').strip():
                return True
                
            return False
            
        except Exception:
            return True

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
    
    def _set_form_section(self, question_id: str, profile_key: str, field_type: QuestionType) -> None:
        """Set the form section based on the profile key."""
        if profile_key is None or field_type == QuestionType.TEXTAREA:
            self.form_questions[question_id]['section'] = FormSectionType.ADDITIONAL
        elif profile_key in DEMOGRAPHIC_FIELDS:
            self.form_questions[question_id]['section'] = FormSectionType.DEMOGRAPHIC
        elif self.is_education_field(profile_key):
            self.form_questions[question_id]['section'] = FormSectionType.EDUCATION
        elif profile_key == 'coverLetterPath':
            self.form_questions[question_id]['section'] = FormSectionType.COVER_LETTER
        elif profile_key == 'resume':
            self.form_questions[question_id]['section'] = FormSectionType.RESUME
        else:
            self.form_questions[question_id]['section'] = FormSectionType.PERSONAL
    
    def _handle_custom_match(self, question_id: str, profile_key: str, best_match: Any, field_type: QuestionType) -> Any:
        """Handle custom matching for special cases like boolean, select, resume, cover letter."""
        # Handle boolean fields
        if best_match is not None and isinstance(best_match, bool):
            best_match = 'Yes' if best_match else 'No'
        
        # Handle education fields
        if self.is_education_field(profile_key):
            best_match = self.get_education_value(profile_key, self.form_questions[question_id]['question'])
            
        # Handle cover letter fields
        if profile_key == 'coverLetterPath' and best_match is not None:
            self.form_questions[question_id]['file_path'] = best_match
            self.form_questions[question_id]['file_name'] = self.profile.get('coverLetterFilename', 'cover_letter.pdf')

        # Handle resume fields - set file_path and file_name
        if profile_key == 'resume' and best_match is not None:
            self.form_questions[question_id]['file_path'] = best_match
            self.form_questions[question_id]['file_name'] = self.profile.get('resumeFilename', 'resume.pdf')

        return best_match
    
    def match_field_to_profile(self, question_id: str) -> tuple:
        """Match field context to profile data using fuzzy matching."""
        field = self.form_questions[question_id]['element']
        has_custom_options = self.form_questions[question_id]['has_custom_options']
        field_type = self.form_questions[question_id]['type']
        label = self.form_questions[question_id]['question']
        is_required = self.form_questions[question_id]['required']
        unique_label_id = self.form_questions[question_id]['unique_label_id']

        if not label:
            placeholder = field.get_attribute('placeholder')
            if placeholder:
                label = placeholder
            else:
                self.delete_form_question(question_id)
                self.logger.info(f"No label found for question {question_id}, deleting question")
                return None
            
        best_match = None
        best_score = 0
        best_profile_key = None
        
        context = clean_string(label.lower().strip())

        is_file_input = field_type == QuestionType.FILE
        is_select_input = field_type == QuestionType.SELECT
        
        # Check each profile field mapping
        for profile_key, keywords in self.field_mappings.items():
            # Calculate match score
            score = 0
            for keyword in keywords:
                if f"{keyword} " in context or f" {keyword}" in context or keyword == context:
                    score += len(keyword)
                    
            # Boost score for resume fields on file inputs with generic upload terms
            if is_file_input and profile_key == 'resume' and score > 0:
                generic_upload_terms = ['upload a file', 'drag and drop', 'file upload', 'attach file']
                for term in generic_upload_terms:
                    if term in context:
                        score += 10  # Boost score for generic file upload on file inputs
                        break
                        
            # Boost score for gpa fields
            if profile_key == 'educationGpa' and " gpa" in label.lower():
                score += 10

            if score > best_score:
                best_score = score
                best_match = self.profile.get(profile_key)
                best_profile_key = profile_key
        
        # Set form section based on profile key
        self._set_form_section(question_id, best_profile_key, field_type)
        
        # Handle custom matching for special cases
        best_match = self._handle_custom_match(question_id, best_profile_key, best_match, field_type)

        # Override answer if overrided_answers is provided
        if self.overrided_answers and unique_label_id in self.overrided_answers:
            best_match = self.overrided_answers[unique_label_id].get("answer")
            self.form_questions[question_id]['answer'] = best_match
            return best_match

        # If our manual matching is not valid, set to None so we can use AI
        if best_match is not None and not self.validate_field_match(label, best_profile_key, best_match, field):
            best_match = None

        if best_profile_key in self.confident_mapping_keys:
            self._update_context(question_id, label, best_match)
            self.form_questions[question_id]['answer'] = best_match
            return best_match

        # Always use AI for textarea type questions, or if we don't have a match and there are no options
        self.logger.info(f"Best match: {best_match} for field: {label} with type: {field_type} with profile key: {best_profile_key}")
        if field_type == QuestionType.TEXTAREA or (best_match is None and not is_select_input and not has_custom_options and not is_file_input):
            # Pass context from previous question/answer
            ai_result = self.ai_assistant.answer_question(
                label,
                field_type, 
                is_required=is_required, 
                profile_value=best_match,
                previous_question=self.last_question,
                previous_answer=self.last_answer
            )
            
            if ai_result is not None:
                best_match, is_open_ended = ai_result
                # Set ai_custom parameter based on whether question is open-ended
                self.form_questions[question_id]['ai_custom'] = is_open_ended

        if best_match is not None:
            self.form_questions[question_id]['answer'] = best_match
        
        self._update_context(question_id, label, best_match)

        return best_match
    
    def validate_field_match(self, context: str, profile_key: str, profile_value: str, field = None) -> bool:
        """Validate if a field match makes logical sense."""
        if not profile_value:
            return False

        # If profile key is resume, field type should be file
        if profile_key == 'resume' and field and field.get_attribute('type') != 'file':
            self.logger.info(f"Rejecting {profile_key} match for resume question: {context}")
            return False

        # If profile key is coverLetterPath, field type should be file
        if profile_key == 'coverLetterPath' and field and field.get_attribute('type') != 'file':
            self.logger.info(f"Rejecting {profile_key} match for cover letter question: {context}")
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
        
        # Company name questions should not match boolean values or GPA
        company_indicators = ['company name', 'employer name', 'which company', 'name of company']
        if any(indicator in context.lower() for indicator in company_indicators):
            if isinstance(profile_value, bool) or profile_key in ['remoteWorkComfortable', 'relocateWilling', 'educationGpa']:
                self.logger.info(f"Rejecting {profile_key} match for company name question: {context}")
                return False
        
        return True
    
    def _update_context(self, question_id: str, question: str, answer: Any) -> None:
        """
        Update the context with the last question and answer for AI assistant reference.
        
        Args:
            question_id: The ID of the question
            question: The question text
            answer: The answer provided
        """
        self.last_question_id = question_id
        self.last_question = question
        self.last_answer = answer
        self.logger.info(f"Updated context - Question: {question}, Answer: {answer}")
    
    def fill_field(self, field, question_id: str) -> bool:
        """Utility method to fill field based on field type."""
        try:
            # Get the answer from form_questions
            value = self.form_questions[question_id].get('answer')
            
            # Scroll to the field to ensure it's visible
            self.scroll_to_element(field)
            
            field_type = field.get_attribute('type')
            tag_name = field.tag_name.lower()
            
            # Handle different field types
            if tag_name == 'select':
                return self.fill_select_field(field, question_id)
            elif field_type == 'file':
                if 'file_path' not in self.form_questions[question_id] or 'file_name' not in self.form_questions[question_id]:
                    self.logger.warning(f"No file path or name found for question: {question_id}")
                    return False
                
                file_path = self.form_questions[question_id]['file_path']
                file_name = self.form_questions[question_id]['file_name']
                return self.fill_file_field(field, file_path, filename=file_name)
            elif field_type == 'checkbox':
                return self.fill_checkbox(field, value)
            else:
                return self.fill_text_field(field, value)
                
        except Exception as e:
            self.logger.warning(f"Error filling field: {str(e)}")
            return False
    
    def fill_checkbox(self, field, value) -> bool:
        """Fill checkbox field - click if value is 'Yes', don't click otherwise."""
        try:
            if not value:
                return True  # No value means don't click, which is fine
            
            # Convert to string and normalize
            value_str = str(value).strip().lower()
            
            # Only click if the value is "yes"
            if value_str == "yes":
                self.logger.info(f"Clicking checkbox - value is 'yes'")
                if not field.is_selected():
                    field.click()
                return True
            else:
                self.logger.info(f"Not clicking checkbox - value is '{value_str}' (not 'yes')")
                # If it's already selected and we don't want it selected, uncheck it
                if field.is_selected():
                    field.click()
                return True
                
        except Exception as e:
            self.logger.warning(f"Error filling checkbox: {str(e)}")
            return False
    
    def fill_text_field(self, field, value) -> bool:
        """Fill text input field."""
        if not value:
            return False
        self.logger.info(f"Filling text field: {value}")
        try:
            field.clear()
            field.send_keys(str(value))
            return True
        except Exception:
            return False
    
    def fill_select_field(self, field, question_id: str) -> bool:
        """Fill select dropdown field."""
        try:
            select = Select(field)
            
            # Match select option by our own method
            option_texts = [option.text for option in select.options]
            best_index = self.match_option_to_target(option_texts, question_id)
            if best_index is not None:
                question = self.form_questions[question_id].get('question', '')
                self.logger.info(f"Best match for select field: {select.options[best_index].text} for question: {question}")
                select.select_by_visible_text(select.options[best_index].text)
                return True
                    
            return False
        except Exception:
            return False
    
    def fill_file_field(self, field, value, filename=None) -> bool:
        """Handle file upload field with enhanced error detection and validation."""
        try:
            if not isinstance(value, str) or not value:
                return False
            
            # Handle file paths (from storage manager)
            if not value.startswith(('http://', 'https://', '/', 'C:', '\\')):
                # This is likely a file path from storage manager
                download_url = storage_manager.get_download_url_from_path(value)
                if download_url:
                    # Treat it as a URL download
                    value = download_url
                else:
                    self.logger.error(f"Could not get download URL for file path: {value}")
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
            self.temp_file_paths.append(file_path)
            return True
            
        except Exception as e:
            self.logger.error(f"Error in safe file upload: {str(e)}")
            return False
    
    def _normalize_target_value(self, value) -> str:
        """Normalize target value for matching in field."""
        if isinstance(value, bool):
            return "YES" if value else "NO"

        # If value is a list, return the first value
        if isinstance(value, list) and len(value) > 0:
            value = value[0]

        value_str = str(value).upper().strip()
        
        # Common positive responses
        if value_str in ['TRUE', '1', 'YES', 'Y', 'AGREE', 'ACCEPT', 'WILLING', 'COMFORTABLE']:
            return "YES"
        
        # Common negative responses
        if value_str in ['FALSE', '0', 'NO', 'N', 'DISAGREE', 'DECLINE', 'NOT WILLING', 'NOT COMFORTABLE']:
            return "NO"
        
        return value_str
    
    def match_option_to_target(self, options: list, question_id: str, multiple=False, retry=False):
        """Find the best matching option from a list of option strings to target(s).
        
        Args:
            options: List of option strings to match against
            target: The target value(s) to match
            question: The question that the target value is for
            multiple: Whether the field is a multiple select field
            retry: Whether to retry the match with AI if no good match is found
        Returns:
            multiple=False -> Index of the best matching option, or None if no good match found
            multiple=True -> List of indices of the best matching options, or [] if no good match found
        """
        target = self.form_questions[question_id].get('answer')
        question = self.form_questions[question_id].get('question')
        is_required = self.form_questions[question_id].get('required')
        unique_label_id = self.form_questions[question_id]['unique_label_id']
        override = self.overrided_answers and unique_label_id in self.overrided_answers
        override_pruned = override and self.overrided_answers[unique_label_id].get("pruned")

        # Override target with overrided_answers if provided
        if override:
            target = self.overrided_answers[unique_label_id].get("answer")
            if target is None:
                return None

        if not options:
            return None

        # Clean each option text
        options = [option.strip(".") for option in options]

        # Normalize options
        normalized_options = [self._normalize_target_value(option) for option in options]
        
        # If we don't have a target value, use AI to get value from question
        field_type = QuestionType.SELECT if not multiple else QuestionType.MULTISELECT
        self.form_questions[question_id]['type'] = field_type
        if target is None:
            # Pass context from previous question/answer
            ai_result = self.ai_assistant.answer_question(
                question, 
                field_type, 
                options, 
                is_required,
                previous_question=self.last_question,
                previous_answer=self.last_answer
            )
            if ai_result is not None:
                target, is_open_ended = ai_result
                # Set ai_custom parameter based on whether question is open-ended
                self.form_questions[question_id]['ai_custom'] = is_open_ended
            if not target:
                return None

        self._update_context(question_id, question, target)

        # Normalize target(s) if not overrided or overrided is pruned
        if not override or override_pruned:
            if multiple and isinstance(target, list):
                target = [self._normalize_target_value(value) for value in target]
            elif multiple and not isinstance(target, list):
                target = [self._normalize_target_value(target)]
            else:
                target = self._normalize_target_value(target)

        # Get best match indices for each target value
        best_indices = []
        best_index = None

        if multiple:
            for value in target:
                # If we have an override and it's not pruned, use the override value
                if override and not override_pruned:
                    best_indices.append(value)
                else:
                    best_indices.append(self._get_best_match_index(normalized_options, value))
            
            # Remove duplicates and None values
            best_indices = list(set([index for index in best_indices if index is not None]))
        else:
            # If we have an override and it's not pruned, use the override value
            if override and not override_pruned:
                best_index = target
            else:
                best_index = self._get_best_match_index(normalized_options, target)
        self.logger.info(f"Override: {override}, override_pruned: {override_pruned}, best_indices: {best_indices}, best_index: {best_index}")
        if best_indices or best_index is not None:
            # Prune options if there are more than 20(for frontend performance)
            if len(options) > 20 or self.form_questions[question_id].get('pruned'):
                self.form_questions[question_id]['answer'] = [options[index] for index in best_indices] if multiple else options[best_index]
                self.form_questions[question_id]['pruned'] = True
            else:
                self.form_questions[question_id]['answer'] = best_indices if multiple else best_index
                self.form_questions[question_id]['options'] = options

        # If we have nothing and haven't retried, retry with AI
        if not best_indices and best_index is None and not retry:
            # Set target to None and retry
            self.form_questions[question_id]['answer'] = None
            return self.match_option_to_target(options, question_id, multiple, retry=True)

        return best_indices if multiple else best_index
        
    def _get_best_match_index(self, options: list, target_value: str) -> int:
        # Check if options exceed 10
        exceed_options = len(options) > 10

        best_index = None
        best_score = 0

        for i, option_text in enumerate(options):
            try:
                # Skip if option text is empty or if options exceed 10 and first letter of option text doesn't match first letter of target value
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
    
    def get_education_value(self, profile_key, label):
        """Get education value from the most recent education entry."""
        try:
            # Get education list from profile
            education_list = self.profile.get('education', [])
            
            # Get the education entry based on label counts
            if education_list:
                count = self.counted_labels.get(label, 0)
                if count - 1 < len(education_list):
                    return education_list[count - 1].get(profile_key, '')
            return None
            
        except Exception:
            self.logger.warning(f"Error getting education value for {profile_key}")
            return None
    
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
    