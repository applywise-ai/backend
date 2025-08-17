"""
AI Assistant service using OpenAI GPT-4.1 for Pro users (textarea fields only) and Google Gemini Flash for non-pro users.
This provides efficient AI form filling capabilities with profile context in each request.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
import google.generativeai as genai
from openai import OpenAI
import pandas as pd
from app.core.config import settings
from app.schemas.application import QuestionType
from datetime import datetime


class AIAssistant:
    """AI Assistant using OpenAI for Pro users (textarea only) and Gemini for non-pro users."""
    
    def __init__(self, user_profile: Dict[str, Any], job_description: Optional[str] = None, override_gemini_model: Optional[str] = None):
        """
        Initialize the AI assistant with user profile.
        
        Args:
            user_profile: Dictionary containing user profile information
            job_description: Optional job description to provide context for answers
            override_gemini_model: Optional Gemini model to use instead of the default
        """
        self.user_profile = self._format_profile_context(user_profile)
        self.is_pro_member = user_profile.get('isProMember', False)
        self.job_description = job_description
        self.logger = logging.getLogger(self.__class__.__name__)
        self.current_date = datetime.now()
        
        # Initialize both AI clients
        self._init_openai()
        self._init_gemini(override_gemini_model)
    
    def _init_openai(self):
        """Initialize OpenAI client."""
        openai_api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not openai_api_key:
            self.logger.warning("OpenAI API key not found - OpenAI features will be disabled")
            self.openai_client = None
        else:
            self.openai_client = OpenAI(api_key=openai_api_key)
            self.logger.info("Initialized OpenAI GPT-4.1")
    
    def _init_gemini(self, override_gemini_model: Optional[str] = None):
        """Initialize Gemini client."""
        gemini_api_key = getattr(settings, 'GOOGLE_API_KEY', None)
        if not gemini_api_key:
            raise ValueError("Google API key is required")
        
        genai.configure(api_key=gemini_api_key)
        
        # Default generation config for Gemini
        self.generation_config = genai.GenerationConfig(
            temperature=0.1,
            max_output_tokens=150,
            response_mime_type="text/plain"
        )

        # Initialize Gemini model
        self.model = genai.GenerativeModel(
            model_name=override_gemini_model if override_gemini_model else "gemini-2.0-flash",
            generation_config=self.generation_config
        )
        self.logger.info("Initialized Gemini 1.5/2.0 Flash")
    
    def _should_use_openai(self, field_type: QuestionType, is_cover_letter: bool = False, is_open_ended: bool = False) -> bool:
        """
        Determine whether to use OpenAI based on field type and user status.
        
        Args:
            field_type: Type of input field
            is_cover_letter: Whether this is for cover letter generation
            is_open_ended: Whether the question is open-ended
        Returns:
            True if OpenAI should be used, False for Gemini
        """
        # Always use OpenAI for cover letter generation if available
        if is_cover_letter and self.openai_client:
            return True
        
        # Use OpenAI for open ended questions only if user is pro and OpenAI is available
        if self.is_pro_member and self.openai_client and is_open_ended:
            return True
        
        # Use Gemini for all other cases
        return False
    
    def _call_ai(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        temperature: float = 0.1, 
        max_tokens: int = None, 
        field_type: QuestionType = QuestionType.INPUT, 
        is_cover_letter: bool = False,
        is_open_ended: bool = False) -> Optional[str]:
        """
        Unified method to call the appropriate AI provider.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt (for OpenAI)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            field_type: Type of input field
            is_cover_letter: Whether this is for cover letter generation
                        
        Returns:
            Generated response text or None if failed
        """
        try:
            if self._should_use_openai(field_type, is_cover_letter, is_open_ended):
                return self._call_openai(prompt, system_prompt, temperature, max_tokens)
            else:
                return self._call_gemini(prompt, system_prompt, temperature, max_tokens)
        except Exception as e:
            provider = "OpenAI" if self._should_use_openai(field_type, is_cover_letter, is_open_ended) else "Gemini"
            self.logger.error(f"Error calling {provider}: {str(e)}")
            return None
    
    def _call_openai(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1, max_tokens: int = None) -> Optional[str]:
        """Call OpenAI API."""
        if not self.openai_client:
            self.logger.error("OpenAI client not initialized")
            return None
            
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 500,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            print("Messages:", messages)
            print("Response:", response)
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content.strip()
            
            return None
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {str(e)}")
            return None
    
    def _call_gemini(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1, max_tokens: int = None) -> Optional[str]:
        """Call Gemini API."""
        try:
            # For Gemini, include system prompt in the user prompt if provided
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            
            # Update generation config with provided parameters
            config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens or 150,
                response_mime_type="text/plain"
            )
            
            response = self.model.generate_content(full_prompt, generation_config=config)
            
            # Check if response is valid and has text
            if not response or not hasattr(response, 'text'):
                self.logger.error("Invalid response from Gemini API - no text available")
                return None
            
            # Check if response has candidates and proper finish reason
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason != 1:
                    self.logger.error(f"Gemini response blocked or failed - finish_reason: {candidate.finish_reason}")
                    return None
            
            return response.text.strip()
            
        except Exception as e:
            self.logger.error(f"Gemini API error: {str(e)}")
            return None
    
    def _format_profile_context(self, user_profile: Dict[str, Any]) -> str:
        """Format user profile into a concise context for the AI."""
        try:
            parts = []
            
            # Personal
            if user_profile.get('fullName'):
                parts.append(f"Name: {user_profile['fullName']}")
            if user_profile.get('currentLocation'):
                parts.append(f"Location: {user_profile['currentLocation']}")
            
            # Current Job
            if user_profile.get('employment'):
                job = user_profile['employment'][0]
                if job.get('company') and job.get('position'):
                    parts.append(f"Current: {job['position']} at {job['company']}")
                if job.get('employmentLocation'):
                    parts.append(f"Work Location: {job['employmentLocation']}")
                if job.get('employmentDescription'):
                    parts.append(f"Role: {job['employmentDescription'][:100]}")
                
                # Employment dates
                emp_dates = []
                if job.get('employmentFrom'):
                    emp_dates.append(f"from {job['employmentFrom']}")
                if job.get('employmentTo'):
                    emp_dates.append(f"to {job['employmentTo']}")
                elif not job.get('employmentTo'):
                    emp_dates.append("to present")
                if emp_dates:
                    parts.append(f"Employment: {' '.join(emp_dates)}")
            
            # Education
            if user_profile.get('education'):
                edu = user_profile['education'][0]
                if edu.get('degree') and edu.get('school'):
                    parts.append(f"Education: {edu['degree']} from {edu['school']}")
                if edu.get('fieldOfStudy'):
                    parts.append(f"Major: {edu['fieldOfStudy']}")
                if edu.get('educationGpa'):
                    parts.append(f"GPA: {edu['educationGpa']}")
                
                # Education dates
                edu_dates = []
                if edu.get('educationFrom'):
                    edu_dates.append(f"from {edu['educationFrom']}")
                if edu.get('educationTo'):
                    edu_dates.append(f"to {edu['educationTo']}")
                if edu_dates:
                    parts.append(f"Education Period: {' '.join(edu_dates)}")
                
            # Skills
            if user_profile.get('skills'):
                skills = user_profile['skills']
                if isinstance(skills, list):
                    parts.append(f"Skills: {', '.join(skills[:8])}")
                else:
                    parts.append(f"Skills: {str(skills)[:100]}")
            
            # Projects
            if user_profile.get('projects'):
                projects = user_profile['projects']
                if isinstance(projects, list) and projects:
                    project_names = [proj.get('name', proj.get('title', '')) for proj in projects[:3] if isinstance(proj, dict)]
                    project_names = [name for name in project_names if name]
                    if project_names:
                        parts.append(f"Projects: {', '.join(project_names)}")
            
            # Job Preferences
            if user_profile.get('expectedSalary'):
                parts.append(f"Salary: {user_profile['expectedSalary']}")
            if user_profile.get('roleLevel'):
                parts.append(f"Level: {user_profile['roleLevel']}")
            if user_profile.get('noticePeriod'):
                parts.append(f"Notice: {user_profile['noticePeriod']}")
            
            # Job Types
            if user_profile.get('jobTypes'):
                job_types = user_profile['jobTypes']
                if isinstance(job_types, list):
                    parts.append(f"Job Types: {', '.join(job_types)}")
                else:
                    parts.append(f"Job Types: {job_types}")
            
            # Location Preferences
            if user_profile.get('locationPreferences'):
                location_prefs = user_profile['locationPreferences']
                if isinstance(location_prefs, list):
                    parts.append(f"Location Prefs: {', '.join(location_prefs[:3])}")
                else:
                    parts.append(f"Location Prefs: {location_prefs}")
            
            # Industry Specializations
            if user_profile.get('industrySpecializations'):
                industry_specs = user_profile['industrySpecializations']
                if isinstance(industry_specs, list):
                    parts.append(f"Industries: {', '.join(industry_specs[:3])}")
                else:
                    parts.append(f"Industries: {industry_specs}")
            
            # Source
            if user_profile.get('source'):
                parts.append(f"Source: {user_profile['source']}")
            
            # Work Auth
            auth_parts = []
            if user_profile.get('eligibleUS'):
                auth_parts.append("US-eligible")
            if user_profile.get('usSponsorship'):
                auth_parts.append("needs-US-sponsorship")
            if user_profile.get('eligibleCanada'):
                auth_parts.append("Canada-eligible")
            if user_profile.get('over18'):
                auth_parts.append("18+")
            if auth_parts:
                parts.append(f"Auth: {', '.join(auth_parts)}")
            
            # Demographics
            demo_parts = []
            for field in ['race', 'gender', 'veteran', 'disability', 'trans', 'sexuality']:
                if user_profile.get(field):
                    demo_parts.append(f"{field}:{user_profile[field]}")
            if demo_parts:
                parts.append(f"Demo: {', '.join(demo_parts)}")
            
            return '\n'.join(parts)
            
        except Exception as e:
            self.logger.error(f"Error formatting profile context: {str(e)}")
            return f"{json.dumps(user_profile, default=str)[:300]}"
    
    def answer_question(
        self, 
        question: str,
        field_type: QuestionType = QuestionType.INPUT,
        options: Optional[List[str]] = None,
        is_required: bool = False,
        custom_prompt: Optional[str] = None,
        profile_value: Optional[str] = None,
        previous_question: Optional[str] = None,
        previous_answer: Optional[str] = None
    ) -> Optional[Union[str, List[str], tuple]]:
        """
        Answer a form question using AI based on user profile context.
        
        Args:
            question: The question to answer
            field_type: Type of input field (input, select, multiselect, date)
            options: List of options for select/multiselect fields
            is_required: Whether the field is required
            custom_prompt: Optional custom prompt to guide the AI response
            profile_value: The value of the profile field that is being answered
            previous_question: The previous question that was asked (for context)
            previous_answer: The answer provided to the previous question (for context)
        Returns:
            - For INPUT/TEXTAREA: Tuple of (answer, is_open_ended) or None
            - For SELECT: One of the options or None
            - For MULTISELECT: List of selected options or None
            - For DATE: Date string in MM/DD/YYYY format or None
        """
        try:
            # Check if question is related to previous question
            is_related_to_previous_question = self._is_related_to_previous_question(question, previous_question)
            
            # Check if question is open-ended
            is_open_ended = self._is_open_ended_question(question)

            # If we already have a value and it's not open-ended, skip AI
            if profile_value and not is_open_ended:
                return None

            # Build prompt with profile context
            prompt_text = self._build_prompt(field_type, options, question, previous_answer, is_required, is_open_ended, is_related_to_previous_question)
            
            # Skip non required additional information questions for non-pro members
            if field_type == QuestionType.TEXTAREA and not self.is_pro_member and not is_required:
                if self._is_additional_information_question(question):
                    self.logger.info(f"Skipping additional information question for non-pro member: {question}")
                    return None
            
            # Prepare system prompt for form filling
            system_prompt = f"""You are a helpful assistant that fills out job application forms based on user profile information. 

IMPORTANT INSTRUCTIONS:
1. Do not include any explanation or additional text - only the value"""        
            # Prepare user prompt with profile context
            user_prompt = f"""User Profile:
{self.user_profile}
"""

            # Add previous question/answer context if available
            if is_related_to_previous_question:
                user_prompt += f"""

PREVIOUS CONTEXT:
Previous Question: {previous_question}
Previous Answer: {previous_answer}

This question is a follow-up use the previous context to answer the question accurately. """

            # Add custom prompt if provided
            if custom_prompt:
                user_prompt += f"""

CUSTOM INSTRUCTIONS:
{custom_prompt}

IMPORTANT CONTEXT:
- If the custom instructions ask for specific details or focus areas, prioritize those in your response"""
            
            user_prompt += f"""

Question: {question}

{prompt_text}
"""

            # Set temperature based on question type
            temperature = 0.8 if is_open_ended else 0.1
            
            # Set max tokens based on user type and question type
            max_tokens = 250
            if field_type == QuestionType.TEXTAREA and self.is_pro_member:
                max_tokens = 650
            
            # Generate response using unified AI call
            answer = self._call_ai(user_prompt, system_prompt, temperature, max_tokens, field_type, is_open_ended=is_open_ended)
            
            self.logger.info(f"""
            Prompt: {prompt_text}
            AI response: {answer}
            Is open-ended: {is_open_ended}
            Is required: {is_required}
            Is related to previous question: {is_related_to_previous_question}
            Previous answer: {previous_answer}
            """)

            if answer is None:
                self.logger.error(f"Failed to get AI response for question: {question}")
                return None
            
            # Process the answer based on input type
            processed_answer = self._process_answer(answer, field_type, options)
            
            return (processed_answer, is_open_ended)
            
        except Exception as e:
            self.logger.error(f"Error getting AI response for question '{question}': {str(e)}")
            return None
    
    def _is_additional_information_question(self, question: str) -> bool:
        """Check if a question is asking for additional information that can be skipped."""
        for keyword in ["additional", "optional", "comments", "anything else"]:
            if keyword in question.lower().strip():
                return True
        return False
    
    def _is_open_ended_question(self, question: str) -> bool:
        """Check if a question is open-ended, reflective, or personal."""
        try:
            # Edge case for lever additional information question
            if question and question.lower().strip() == "additional information":
                return True
            
            # Build classification prompt with context
            classification_prompt = f"""Question: {question}

Based on the criteria below, determine whether the following question is open-ended (requires a descriptive, multi-sentence answer) or not (can be answered with yes/no or a single word).
Open-ended questions typically:
- Ask "why", "how", "what", "describe", "explain", "tell me about"
- Require personal reflection, motivation, or reasoning
- Ask about feelings, excitement, passion, goals, or experiences
- Need multiple sentences to answer properly

Answer "true" if open-ended, "false" if not.
"""

            # Use unified AI call for classification
            result = self._call_ai(classification_prompt, temperature=0.1, max_tokens=10, field_type=QuestionType.INPUT)
            
            if result is None:
                self.logger.error(f"Failed to classify question as open-ended: {question}")
                return False
            self.logger.info(f"Is open ended: Question: {question} - {result}")
            return result.lower().strip() == "true"
            
        except Exception as e:
            self.logger.error(f"Error classifying question as open-ended '{question}': {str(e)}")
            return False
    
    def _is_related_to_previous_question(self, question: str, previous_question: Optional[str] = None) -> bool:
        """Check if a question is related to the previous question."""
        try:
            # Build classification prompt with context
            classification_prompt = f"""Question: {question}
Previous Question: {previous_question}

Is the current question a follow-up to the previous question and contains an if at the start or explicitly mention above?

Answer only "true" or "false"."""
            
            # Use unified AI call for classification
            result = self._call_ai(classification_prompt, temperature=0.1, max_tokens=10)
            return result.lower().strip() == "true"
        except Exception as e:
            self.logger.error(f"Error classifying question as related to previous question '{question}': {str(e)}")
            return False

    def _build_prompt(
        self, 
        field_type: QuestionType,
        options: Optional[List[str]] = None,
        question: Optional[str] = None,
        previous_answer: Optional[str] = None,
        is_required: bool = False,
        is_open_ended: bool = False,
        is_related_to_previous_question: bool = False
    ) -> str:
        """Build the prompt for the AI based on question and input type."""
        prompt = None
        
        if field_type == QuestionType.SELECT:
            if options:
                prompt = f"\nAvailable Options: {', '.join(options)}"
                prompt += "\nSelect the BEST matching option from the list above. Return only the exact option text."
            else:
                prompt = "\nProvide the most appropriate answer."
        
        elif field_type == QuestionType.MULTISELECT:
            if options:
                prompt = f"\nAvailable Options: {', '.join(options)}"
                prompt += "\nSelect ALL appropriate options from the list above. Return as JSON array like [\"option1\", \"option2\"] or \"null\" if no options match."
            else:
                prompt = "\nProvide all appropriate answers as JSON array."
        
        elif field_type == QuestionType.DATE:
            prompt = f"\nProvide a date in MM/DD/YYYY format. Consider the current date ({self.current_date.strftime('%B %d, %Y')}) when answering questions about graduation status, employment dates, or time-based information."
        
        elif field_type == QuestionType.CHECKBOX:
            prompt = f"\nBased on the user profile information above, should this checkbox be checked? Answer only 'Yes' or 'No'."
        
        elif field_type == QuestionType.NUMBER:
            prompt = f"\nProvide a numeric value (integer or decimal). Return only the number without any text or formatting."
        
        else:
            # Default prompt same as INPUT
            date_prompt = f"Consider the current date ({self.current_date.strftime('%B %d, %Y')}) when answering questions about graduation status, employment dates, or time-based information."
            # prompt = f"\nProvide a concise text answer. {date_prompt}"
            
            # # Check if question is open-ended and add detailed prompt if so
            # if question and is_open_ended:
            #     prompt = f"\nBased on the user profile information above, provide a detailed and descriptive answer that best addresses the question. Use relevant details from the profile (experience, skills, education, etc.) to craft a thoughtful response. {date_prompt}"
            descriptive_prompt = "Provide a detailed and descriptive answer using full sentence format. Use relevant details from the profile(education, experience, skills, etc.) to craft a thoughtful response."
            prompt = f"Answer the question formally. {descriptive_prompt if is_open_ended else ''} {date_prompt}" 
            if self.job_description and is_open_ended:
                prompt += f"\n\nJob Description:\n{self.job_description[:500]}\n\nTailor your response to show how you would be a good fit for this specific role."

        # Add null instruction only for non-required questions
        if not is_required:
            if not is_related_to_previous_question or not previous_answer:
                prompt += "\nProvide \"null\" if you cannot determine an appropriate answer."
            else:
                prompt += "\nTry to answer the question as best as possible."
        else:
            prompt += "\nYou MUST answer this question as it is required."
        
        return prompt + "\nAlways answer yes to any question related to eligibility, interest, or willingness to proceed unless doing so would be illegal or dishonest."
    
    def _process_answer(
        self, 
        answer: str, 
        field_type: QuestionType, 
        options: Optional[List[str]] = None
    ) -> Optional[Union[str, List[str]]]:
        """Process the AI's answer based on input type."""
        
        if answer.lower().strip() == 'null':
            return None
        
        if field_type == QuestionType.SELECT:
            # Verify the answer is in the options if options were provided
            if options and answer not in options:
                # Try to find a case-insensitive match
                answer_lower = answer.lower()
                for option in options:
                    if option.lower() == answer_lower:
                        return option
                # If no match found, return None
                self.logger.warning(f"AI selected '{answer}' but it's not in options: {options}")
                return None
            return answer
        
        elif field_type == QuestionType.MULTISELECT:
            try:
                # Try to parse as JSON array
                if answer.startswith('[') and answer.endswith(']'):
                    selected_options = json.loads(answer)
                    if isinstance(selected_options, list):
                        # Verify all selected options are in the available options
                        if options:
                            valid_options = []
                            for selected in selected_options:
                                if selected in options:
                                    valid_options.append(selected)
                                else:
                                    # Try case-insensitive match
                                    for option in options:
                                        if option.lower() == selected.lower():
                                            valid_options.append(option)
                                            break
                            return valid_options if valid_options else None
                        return selected_options
                else:
                    # Single option provided, convert to list
                    if options and answer in options:
                        return [answer]
                    elif options:
                        # Try case-insensitive match
                        for option in options:
                            if option.lower() == answer.lower():
                                return [option]
                return None
            except json.JSONDecodeError:
                self.logger.warning(f"Could not parse multiselect answer as JSON: {answer}")
                return None
        
        elif field_type == QuestionType.DATE:
            # Validate date format
            try:
                # Try to parse the date to validate format
                datetime.strptime(answer, "%m/%d/%Y")
                return answer
            except ValueError:
                self.logger.warning(f"Invalid date format from AI: {answer}")
                return None
        
        elif field_type == QuestionType.CHECKBOX:
            # Process checkbox response - normalize to "Yes" or "No"
            answer_lower = answer.lower().strip()
            if answer_lower in ['yes', 'true', '1', 'check', 'checked']:
                return "Yes"
            elif answer_lower in ['no', 'false', '0', 'uncheck', 'unchecked']:
                return "No"
            else:
                self.logger.warning(f"Invalid checkbox response from AI: {answer}, defaulting to 'No'")
                return "No"
        
        elif field_type == QuestionType.NUMBER:
            # Process number response - extract numeric value
            try:
                # Remove any non-numeric characters except decimal point and minus sign
                cleaned_answer = ''.join(c for c in answer if c.isdigit() or c in '.-')
                
                # Handle edge cases
                if not cleaned_answer or cleaned_answer == '.' or cleaned_answer == '-':
                    self.logger.warning(f"Invalid number format from AI: {answer}")
                    return None
                
                # Convert to float first to handle both integers and decimals
                number_value = float(cleaned_answer)
                
                # Return as integer if it's a whole number, otherwise as float
                if number_value.is_integer():
                    return str(int(number_value))
                else:
                    return str(number_value)
                    
            except (ValueError, TypeError):
                self.logger.warning(f"Could not parse number from AI response: {answer}")
                return None
        
        else:  # INPUT type
            return answer.strip()
    
    def generate_cover_letter(self, custom_prompt: Optional[str] = None) -> Optional[str]:
        """
        Generate a cover letter using AI based on user profile and job description.
        
        Args:
            custom_prompt: Optional custom prompt to include in the generation
            
        Returns:
            Generated cover letter text or None if generation fails
        """
        try:
            # Build the prompt for cover letter generation
            prompt = self._build_cover_letter_prompt(custom_prompt)
            
            # Use higher temperature for more creative writing and more tokens for longer content
            temperature = 0.7
            max_tokens = 1000
            
            # Generate the cover letter using unified AI call - always use OpenAI for cover letters
            cover_letter = self._call_ai(prompt, temperature=temperature, max_tokens=max_tokens, field_type=QuestionType.TEXTAREA, is_cover_letter=True)
            
            if cover_letter is None:
                self.logger.error("Cover letter generation failed - no response from AI")
                return None
            
            if cover_letter.lower().strip() == "null":
                self.logger.error("Cover letter generation failed - response was null")
                return None
            
            # Clean the cover letter to ensure it only contains the letter content
            cleaned_cover_letter = self._clean_cover_letter(cover_letter)
            
            self.logger.info(f"Generated cover letter with {len(cleaned_cover_letter)} characters")
            return cleaned_cover_letter
            
        except Exception as e:
            self.logger.error(f"Error generating cover letter: {str(e)}")
            return None
    
    def _clean_cover_letter(self, cover_letter: str) -> str:
        """
        Clean the cover letter to ensure it only contains the letter content from 
        "Dear Hiring Manager" to "Sincerely, [Name]" without any header details.
        
        Args:
            cover_letter: Raw cover letter text from AI
            
        Returns:
            Cleaned cover letter text
        """
        try:
            # Remove any leading/trailing whitespace
            cover_letter = cover_letter.strip()
            
            # Find the start of the letter (various salutation patterns)
            start_patterns = [
                "Dear Hiring Manager",
                "Dear Hiring Team",
                "Dear Recruiter",
                "Dear [Company Name] Team",
                "Dear Sir/Madam",
                "To Whom It May Concern"
            ]
            
            start_index = -1
            for pattern in start_patterns:
                start_index = cover_letter.find(pattern)
                if start_index != -1:
                    break
            
            # If no salutation found, try to find the first paragraph
            if start_index == -1:
                # Look for common letter starters
                lines = cover_letter.split('\n')
                for i, line in enumerate(lines):
                    line_lower = line.strip().lower()
                    if any(starter in line_lower for starter in ['dear', 'to whom', 'i am writing', 'i would like']):
                        start_index = cover_letter.find(line)
                        break
                
                # If still not found, start from the beginning
                if start_index == -1:
                    start_index = 0
            
            # Find the end of the letter (various closing patterns)
            end_patterns = [
                "Sincerely,",
                "Best regards,",
                "Kind regards,",
                "Thank you,",
                "Respectfully,",
                "Yours truly,"
            ]
            
            end_index = -1
            for pattern in end_patterns:
                end_index = cover_letter.find(pattern, start_index)
                if end_index != -1:
                    # Find the end of the closing (look for the name or end of text)
                    closing_start = end_index
                    closing_end = cover_letter.find('\n', closing_start)
                    if closing_end == -1:
                        closing_end = len(cover_letter)
                    
                    # Look for a name after the closing
                    name_patterns = [
                        '\n\n',  # Double line break after closing
                        '\n',    # Single line break after closing
                        ' '      # Space after closing
                    ]
                    
                    for name_pattern in name_patterns:
                        name_start = cover_letter.find(name_pattern, closing_start)
                        if name_start != -1:
                            # Look for the end of the name (next line break or end)
                            name_end = cover_letter.find('\n', name_start + len(name_pattern))
                            if name_end == -1:
                                name_end = len(cover_letter)
                            
                            # Check if there's actual content after the closing
                            name_content = cover_letter[name_start:name_end].strip()
                            if name_content and len(name_content) > 2:  # At least 3 characters for a name
                                end_index = name_end
                                break
                    
                    break
            
            # If no closing found, use the entire text from start
            if end_index == -1:
                end_index = len(cover_letter)
            
            # Extract the cleaned cover letter
            cleaned_letter = cover_letter[start_index:end_index].strip()
            
            # Ensure it starts with a proper salutation
            if not any(cleaned_letter.lower().startswith(pattern.lower()) for pattern in start_patterns):
                # Add a default salutation if none found
                cleaned_letter = "Dear Hiring Manager,\n\n" + cleaned_letter
            
            # Ensure it ends with a proper closing
            if not any(pattern.lower() in cleaned_letter.lower()[-50:] for pattern in end_patterns):
                # Add a default closing if none found
                user_name = self.user_profile.split('\n')[0].replace('Name: ', '').strip()
                if user_name:
                    cleaned_letter += f"\n\nSincerely,\n{user_name}"
                else:
                    cleaned_letter += "\n\nSincerely,\n[Your Name]"
            
            return cleaned_letter
            
        except Exception as e:
            self.logger.error(f"Error cleaning cover letter: {str(e)}")
            return cover_letter  # Return original if cleaning fails
    
    def _build_cover_letter_prompt(self, custom_prompt: Optional[str] = None) -> str:
        """Build the prompt for cover letter generation."""
        prompt = f"""User Profile:
{self.user_profile}

Task: Write a professional cover letter based on the user profile above.

Instructions:
1. Write a compelling cover letter that highlights relevant experience and skills
2. Keep it professional and concise
3. Focus on how the candidate's background aligns with typical job requirements
4. Use specific examples from the profile when possible
5. Start with "Dear Hiring Manager," and end with "Sincerely," followed by the candidate's name
6. Do NOT include any header details, contact information, or formatting - only the letter content
7. Make it personalized but professional
8. The letter should be between 200-350 words
9. Consider the current date ({self.current_date.strftime('%B %d, %Y')}) when describing graduation status, employment duration, or time-based achievements
"""
        
        if self.job_description:
            prompt += f"\nJob Description:\n{self.job_description[:500]}\n\nTailor the cover letter to this specific job posting.\n"
        
        if custom_prompt:
            prompt += f"\nCustom Prompt:\n{custom_prompt}\n"

        prompt += "\nGenerate the cover letter (only the letter content, no headers or formatting):"
        
        return prompt
    
    def summarize_job_descriptions(self, jobs_df: pd.DataFrame, batch_size: int = 10) -> pd.DataFrame:
        """
        Summarize job descriptions in batch to extract structured information.
        
        Args:
            jobs_df: DataFrame containing job listings with 'description' column
            batch_size: Number of jobs to process in each batch (default: 50)
            
        Returns:
            DataFrame with additional columns extracted from job descriptions
        """
        try:
            import pandas as pd
            
            if jobs_df.empty:
                self.logger.warning("Empty DataFrame provided for job summarization")
                return jobs_df
            
            if 'description' not in jobs_df.columns:
                self.logger.error("DataFrame must contain 'description' column")
                return jobs_df
            
            # Create a copy to avoid modifying the original
            result_df = jobs_df.copy()
            self.logger.info(f"BEfore setting new columns {len(result_df)}")
            # Initialize new columns with default values
            result_df['provides_sponsorship'] = True
            result_df['responsibilities'] = [[] for _ in range(len(result_df))]
            result_df['requirements'] = [[] for _ in range(len(result_df))]
            result_df['short_responsibilities'] = None
            result_df['short_qualifications'] = None
            result_df['salary_min_range'] = None
            result_df['salary_max_range'] = None
            result_df['company_description'] = None
            result_df['salary_currency'] = None
            result_df['company_size'] = None
            result_df['skills'] = [[] for _ in range(len(result_df))]
            
            # Process jobs in batches
            total_jobs = len(result_df)
            self.logger.info(f"Starting job summarization for {total_jobs} jobs in batches of {batch_size}")
            
            for i in range(0, total_jobs, batch_size):
                batch_end = min(i + batch_size, total_jobs)
                batch_df = result_df.iloc[i:batch_end]
                
                self.logger.info(f"Processing batch {i//batch_size + 1}: jobs {i+1}-{batch_end}")
                
                # Extract job descriptions for this batch
                batch_descriptions = []
                batch_indices = []
                
                for idx in batch_df.index:
                    job_description = batch_df.loc[idx, 'description']
                    if pd.isna(job_description) or not job_description:
                        continue
                    
                    batch_descriptions.append(job_description)
                    batch_indices.append(idx)
                
                if not batch_descriptions:
                    self.logger.warning(f"No valid descriptions found in batch {i//batch_size + 1}")
                    continue
                
                # Process all descriptions in this batch with a single API call
                batch_results = self._extract_job_info_batch(batch_descriptions)
                
                # Update the DataFrame with extracted information
                for idx, extracted_info in zip(batch_indices, batch_results):
                    for key, value in extracted_info.items():
                        if key in result_df.columns:
                            try:
                                # Special handling for location field - only update if current value is null
                                if key == 'location':
                                    current_location = result_df.at[idx, key]
                                    if pd.isna(current_location) or current_location is None or current_location == '':
                                        # Only use AI value if current location is null
                                        formatted_location = self._format_location(value)
                                        result_df.at[idx, key] = formatted_location
                                        if formatted_location:
                                            self.logger.info(f"Updated null location for job {idx}: {value} -> {formatted_location}")
                                else:
                                    result_df.at[idx, key] = value
                            except Exception as assign_error:
                                self.logger.warning(f"Failed to assign {key} for job {idx}: {str(assign_error)}")
                                # Use loc as fallback
                                try:
                                    if key == 'location':
                                        current_location = result_df.loc[idx, key]
                                        if pd.isna(current_location) or current_location is None or current_location == '':
                                            formatted_location = self._format_location(value)
                                            result_df.loc[idx, key] = formatted_location
                                        else:
                                            result_df.loc[idx, key] = value
                                    else:
                                        result_df.loc[idx, key] = value
                                except Exception as loc_error:
                                    self.logger.warning(f"Loc assignment also failed for {key}: {str(loc_error)}")
                                    continue
                
                # Log progress
                self.logger.info(f"Completed batch {i//batch_size + 1}: processed {len(batch_descriptions)} jobs")
            
            self.logger.info(f"Job summarization completed for {total_jobs} jobs")
            return result_df
            
        except Exception as e:
            self.logger.error(f"Error in job summarization: {str(e)}")
            return jobs_df

    def _format_location(self, location: str) -> str:
        """
        Format location string. We receive "toronto-on" format, try to match to LOCATION_TYPE_MAPPING keys.
        If not found, convert to "City, State/Province" format.
        
        Args:
            location: Raw location string in "toronto-on" format
            
        Returns:
            Formatted location string in "City, State/Province" format if not in mapping
        """
        if not location or not isinstance(location, str):
            return None
        
        location = location.strip()
        if not location:
            return None
        
        # Import the location mapping from types
        from app.services.job_application.types import LOCATION_TYPE_MAPPING
        
        # Check if the location is already in our mapping keys (e.g., "toronto-on")
        if location in LOCATION_TYPE_MAPPING.keys():
            # Return the key if it exists
            return location
        
        # If not found in mapping, convert from "toronto-on" format to "City, State/Province" format
        # Split by hyphen to get city and state/province
        if '-' in location:
            parts = location.split('-')
            if len(parts) >= 2:
                city = parts[0].replace('-', ' ').title()
                state_province = parts[1].upper()
                return f"{city}, {state_province}"
        
        # If no hyphen found or can't parse, return the original
        return location

    def _extract_job_info_batch(self, job_descriptions: List[str]) -> List[Dict[str, Any]]:
        """
        Extract structured information from multiple job descriptions in a single API call.
        
        Args:
            job_descriptions: List of job description texts
            
        Returns:
            List of dictionaries containing extracted information for each job
        """
        try:
            # Build the batch extraction prompt
            prompt = self._build_batch_job_extraction_prompt(job_descriptions)
            
            # Use lower temperature for more consistent extraction
            temperature = 0.1
            max_tokens = 1000000  # Increased for batch processing
            
            # Generate extraction using AI
            extraction_result = self._call_ai(prompt, temperature=temperature, max_tokens=max_tokens)
            
            if extraction_result is None:
                self.logger.warning("Failed to extract job information from batch")
                return [self._get_default_job_info() for _ in job_descriptions]
            
            # Log the raw extraction result for debugging
            self.logger.info(f"Raw AI extraction result: {extraction_result[:200]}...")
            
            # Parse the batch extraction result
            parsed_results = self._parse_batch_job_extraction(extraction_result, len(job_descriptions))
            
            # Ensure we have the correct number of results
            if len(parsed_results) != len(job_descriptions):
                self.logger.warning(f"Expected {len(job_descriptions)} results but got {len(parsed_results)}")
                # Pad with default results if needed
                while len(parsed_results) < len(job_descriptions):
                    parsed_results.append(self._get_default_job_info())
                # Truncate if too many
                parsed_results = parsed_results[:len(job_descriptions)]
            
            return parsed_results
            
        except Exception as e:
            self.logger.error(f"Error extracting job info from batch: {str(e)}")
            return [self._get_default_job_info() for _ in job_descriptions]
    
    def _build_batch_job_extraction_prompt(self, job_descriptions: List[str]) -> str:
        """Build the prompt for batch job information extraction."""
        prompt = f"""Extract information from {len(job_descriptions)} job descriptions below.

"""
        
        for i, description in enumerate(job_descriptions, 1):
            prompt += f"""JOB {i}:
{description}

"""
        
        prompt += f"""For each job, extract the following information and return as a JSON array:

[
    {{
        "provides_sponsorship": boolean,  // ASSUME TRUE unless explicitly mentioned otherwise. For US jobs: true unless job description explicitly states "no sponsorship", "US citizens only", "no visa sponsorship", etc. For Canada jobs: ALWAYS true.
        "responsibilities": ["responsibility1", "responsibility2", ...],  // List of detailed responsibilities (be specific and descriptive)
        "requirements": ["requirement1", "requirement2", ...],  // List of detailed requirements/qualifications (be specific and descriptive)
        "short_responsibilities": "Brief summary of responsibilities (max 100 chars)",
        "short_qualifications": "Brief summary of qualifications (max 100 chars)",
        "salary_min_range": number or null,  // Minimum salary (CONVERT TO YEARLY if hourly/daily/monthly)
        "salary_max_range": number or null,  // Maximum salary (CONVERT TO YEARLY if hourly/daily/monthly)
        "description": "Detailed summary of the job description (max 300 chars)",
        "company_description": "Brief description of the company (max 150 chars)",
        "salary_currency": "string",  // Currency code (USD, EUR, GBP, etc.) or null if not mentioned
        "company_size": "string",  // Company size category: "startup" (1-50), "small" (51-200), "medium" (201-1000), "large" (1001-5000), "enterprise" (5000+) or null
        "skills": ["skill1", "skill2", "skill3", "skill4", "skill5"],  // Up to 5 most relevant technical skills (programming languages, frameworks, tools, etc.)
        "location": "string",  // Location of the job (city-state/province) or null if not mentioned
    }},
    // ... repeat for each job
]

IMPORTANT:
- Return ONLY the JSON array, no additional text
- The array must have exactly {len(job_descriptions)} objects
- Use null for missing information
- For salary ranges, extract only the numeric values (no currency symbols) and CONVERT TO YEARLY
- If salary is hourly, multiply by 2080 (40 hours/week * 52 weeks)
- If salary is daily, multiply by 260 (5 days/week * 52 weeks)
- If salary is monthly, multiply by 12
- Keep responsibility and requirement lists to 5-8 items maximum
- Make short summaries concise and informative
- For salary_currency, use standard 3-letter codes (USD, EUR, GBP, CAD, etc.)
- For company_size, use these categories based on employee count mentioned:
  * "startup" for 1-50 employees
  * "small" for 51-200 employees  
  * "medium" for 201-1000 employees
  * "large" for 1001-5000 employees
  * "enterprise" for 5000+ employees
  * null if no size information found
- For skills, extract the most relevant technical skills mentioned (max 5):
  * Programming languages (Python, JavaScript, Java, etc.)
  * Frameworks (React, Django, Spring, etc.)
  * Tools (Docker, AWS, Git, etc.)
  * Databases (PostgreSQL, MongoDB, etc.)
  * Other technical skills relevant to the role
- For provides_sponsorship:
  * DEFAULT: true (assume sponsorship is provided)
  * Set to false if its mentioned in the job description that sponsorship is not provided
  * For Canada jobs: ALWAYS true (Canada generally provides work permits)
  * For US jobs: true unless explicitly stated otherwise
- For location:
  * Extract the location of the job (city-state/province) or null if not mentioned
  * Example: "New York, NY" -> "new-york-ny", "Toronto, ON" -> "toronto-on", "San Francisco, CA" -> "san-francisco-ca"

RESPONSIBILITIES GUIDELINES:
- Be specific and descriptive, not generic
- Include context about scope, impact, and complexity

REQUIREMENTS GUIDELINES:
- Be specific about experience levels, technologies, and qualifications
- Include both technical and soft skill requirements

JOB DESCRIPTION GUIDELINES:
- Provide a comprehensive summary that captures the role's essence
- Include key aspects like role level, primary technologies, team context, and impact
- Make it informative enough for candidates to understand the role's scope and impact
"""
        return prompt
    
    def _parse_batch_job_extraction(self, extraction_result: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse the AI batch extraction result into structured data."""
        try:
            import json
            
            # Clean the result to extract JSON
            result = extraction_result.strip()
            
            # Remove any markdown formatting
            if result.startswith('```json'):
                result = result[7:]
            if result.endswith('```'):
                result = result[:-3]
            
            # Log the cleaned result for debugging
            self.logger.info(f"Cleaned extraction result: {result[:200]}...")
            
            # Parse JSON array
            parsed_array = json.loads(result)
            
            if not isinstance(parsed_array, list):
                self.logger.error(f"Expected JSON array but got {type(parsed_array)}")
                return [self._get_default_job_info() for _ in range(expected_count)]
            
            if len(parsed_array) == 0:
                self.logger.error("Parsed array is empty")
                return [self._get_default_job_info() for _ in range(expected_count)]
            
            self.logger.info(f"Successfully parsed {len(parsed_array)} job objects")
            
            # Process each job in the array
            processed_jobs = []
            for i, parsed in enumerate(parsed_array):
                if not isinstance(parsed, dict):
                    self.logger.warning(f"Job {i+1} is not a dictionary, using defaults")
                    processed_jobs.append(self._get_default_job_info())
                    continue
                
                # Validate and clean the parsed data
                cleaned = {}
                
                # Boolean fields
                cleaned['provides_sponsorship'] = bool(parsed.get('provides_sponsorship', True))
                
                # List fields
                cleaned['responsibilities'] = self._clean_list_field(parsed.get('responsibilities', []))
                cleaned['requirements'] = self._clean_list_field(parsed.get('requirements', []))
                cleaned['skills'] = self._clean_list_field(parsed.get('skills', []))
                
                # String fields
                cleaned['short_responsibilities'] = self._clean_string_field(parsed.get('short_responsibilities'))
                cleaned['short_qualifications'] = self._clean_string_field(parsed.get('short_qualifications'))
                cleaned['description'] = self._clean_string_field(parsed.get('description'))
                cleaned['company_description'] = self._clean_string_field(parsed.get('company_description'))
                cleaned['salary_currency'] = self._clean_string_field(parsed.get('salary_currency'))
                cleaned['company_size'] = self._clean_string_field(parsed.get('company_size'))
                cleaned['location'] = self._format_location(parsed.get('location'))
                # Numeric fields
                cleaned['salary_min_range'] = self._clean_numeric_field(parsed.get('salary_min_range'))
                cleaned['salary_max_range'] = self._clean_numeric_field(parsed.get('salary_max_range'))
                
                processed_jobs.append(cleaned)
            
            self.logger.info(f"Processed {len(processed_jobs)} jobs successfully")
            
            # Ensure we have the right number of results
            while len(processed_jobs) < expected_count:
                self.logger.warning(f"Adding default job info to reach expected count of {expected_count}")
                processed_jobs.append(self._get_default_job_info())
            
            return processed_jobs[:expected_count]
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse batch job extraction JSON: {str(e)}")
            self.logger.error(f"Raw result was: {extraction_result}")
            return [self._get_default_job_info() for _ in range(expected_count)]
        except Exception as e:
            self.logger.error(f"Error parsing batch job extraction: {str(e)}")
            return [self._get_default_job_info() for _ in range(expected_count)]

    def _clean_list_field(self, value: Any) -> List[str]:
        """Clean and validate a list field."""
        if not isinstance(value, list):
            return []
        
        # Filter out empty strings and limit to 8 items
        cleaned = []
        for item in value:
            if item is not None and str(item).strip():
                cleaned.append(str(item).strip())
        return cleaned[:8]
    
    def _clean_string_field(self, value: Any) -> Optional[str]:
        """Clean and validate a string field."""
        if not value or not isinstance(value, str):
            return None
        
        cleaned = str(value).strip()
        return cleaned if cleaned else None
    
    def _clean_numeric_field(self, value: Any) -> Optional[float]:
        """Clean and validate a numeric field."""
        if value is None:
            return None
        
        try:
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                # Remove currency symbols and commas
                cleaned = value.replace('$', '').replace(',', '').replace('k', '000').replace('K', '000')
                return float(cleaned)
            return None
        except (ValueError, TypeError):
            return None
    
    def _get_default_job_info(self) -> Dict[str, Any]:
        """Get default job information structure."""
        return {
            'provides_sponsorship': True,
            'responsibilities': [],
            'requirements': [],
            'short_responsibilities': None,
            'short_qualifications': None,
            'salary_min_range': None,
            'salary_max_range': None,
            'description': None,
            'company_description': None,
            'salary_currency': None,
            'company_size': None,
            'skills': [],
            'location': None
        } 