"""
Validation utilities for job application form questions.
"""

import logging
from typing import Any, Dict, List, Union
from datetime import datetime
from app.schemas.application import QuestionType, FormQuestion

logger = logging.getLogger(__name__)


def validate_and_convert_form_questions(form_questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and convert form question answers based on their type and pruned status.
    
    Args:
        form_questions: List containing form questions with their answers
        
    Returns:
        List with validated and converted form questions
    """
    validated_questions = []
    
    for question in form_questions:
        try:
            question_id = question.get('unique_label_id')
            question_type = question.get('type')
            answer = question.get('answer')
            is_pruned = question.get('pruned', False)
            options = question.get('options', [])
            
            logger.info(f"Validating question {question_id}: type={question_type}, pruned={is_pruned}, answer={answer}")
            
            # Skip validation if no answer
            if answer is None:
                validated_questions.append(question)
                continue
            
            validated_answer = None
            
            # Handle both string and enum types
            if question_type == QuestionType.SELECT or question_type == 'select':
                validated_answer = _validate_select_answer(answer, is_pruned, options, question_id)
            elif question_type == QuestionType.MULTISELECT or question_type == 'multiselect':
                validated_answer = _validate_multiselect_answer(answer, is_pruned, options, question_id)
            elif question_type == QuestionType.DATE or question_type == 'date':
                validated_answer = _validate_date_answer(answer, question_id)
            elif question_type == QuestionType.NUMBER or question_type == 'number':
                validated_answer = _validate_number_answer(answer, question_id)
            else:
                # For other types (INPUT, TEXTAREA, FILE), keep as is
                validated_answer = answer
            
            # Update the question data with validated answer
            question['answer'] = validated_answer
            validated_questions.append(question)
            
            logger.info(f"Question {question_id} validated: {answer} -> {validated_answer}")
            
        except Exception as e:
            logger.error(f"Error validating question {question.get('unique_label_id', 'unknown')}: {str(e)}")
            # Keep original data if validation fails
            validated_questions.append(question)
    
    return validated_questions


def _validate_select_answer(answer: Any, is_pruned: bool, options: List[str], question_id: str) -> Union[int, str]:
    """
    Validate and convert select answer.
    
    Args:
        answer: The answer to validate
        is_pruned: Whether the question is pruned
        options: List of available options
        question_id: Question identifier for logging
        
    Returns:
        Validated answer (int for non-pruned, string for pruned)
    """
    if is_pruned:
        # For pruned select, answer should be a string
        if isinstance(answer, str):
            return answer
        else:
            logger.warning(f"Pruned select question {question_id}: expected string, got {type(answer)}")
            return str(answer) if answer is not None else None
    else:
        # For non-pruned select, answer should be an integer index
        if isinstance(answer, int):
            if 0 <= answer < len(options):
                return answer
            else:
                logger.warning(f"Select question {question_id}: index {answer} out of range [0, {len(options)})")
                return 0 if len(options) > 0 else None
        elif isinstance(answer, str):
            # Try to convert string to int
            try:
                index = int(answer)
                if 0 <= index < len(options):
                    return index
                else:
                    logger.warning(f"Select question {question_id}: string index {answer} out of range")
                    return 0 if len(options) > 0 else None
            except ValueError:
                logger.warning(f"Select question {question_id}: cannot convert '{answer}' to int")
                return 0 if len(options) > 0 else None
        else:
            logger.warning(f"Select question {question_id}: expected int, got {type(answer)}")
            return 0 if len(options) > 0 else None


def _validate_multiselect_answer(answer: Any, is_pruned: bool, options: List[str], question_id: str) -> Union[List[int], str]:
    """
    Validate and convert multiselect answer.
    
    Args:
        answer: The answer to validate
        is_pruned: Whether the question is pruned
        options: List of available options
        question_id: Question identifier for logging
        
    Returns:
        Validated answer (list of ints for non-pruned, comma-separated string for pruned)
    """
    if is_pruned:
        # For pruned multiselect, answer should be a comma-separated string
        if isinstance(answer, str):
            return answer
        elif isinstance(answer, list):
            # Convert list to comma-separated string
            return ', '.join(str(item) for item in answer)
        else:
            logger.warning(f"Pruned multiselect question {question_id}: expected string or list, got {type(answer)}")
            return str(answer) if answer is not None else None
    else:
        # For non-pruned multiselect, answer should be a list of integer indices
        if isinstance(answer, list):
            validated_indices = []
            for item in answer:
                if isinstance(item, int):
                    if 0 <= item < len(options):
                        validated_indices.append(item)
                    else:
                        logger.warning(f"Multiselect question {question_id}: index {item} out of range")
                elif isinstance(item, str):
                    try:
                        index = int(item)
                        if 0 <= index < len(options):
                            validated_indices.append(index)
                        else:
                            logger.warning(f"Multiselect question {question_id}: string index {item} out of range")
                    except ValueError:
                        logger.warning(f"Multiselect question {question_id}: cannot convert '{item}' to int")
            
            # Remove duplicates while preserving order
            seen = set()
            unique_indices = []
            for index in validated_indices:
                if index not in seen:
                    seen.add(index)
                    unique_indices.append(index)
            
            return unique_indices
        elif isinstance(answer, str):
            # Try to parse comma-separated string as list of indices
            try:
                indices = [int(x.strip()) for x in answer.split(',') if x.strip()]
                validated_indices = []
                for index in indices:
                    if 0 <= index < len(options):
                        validated_indices.append(index)
                    else:
                        logger.warning(f"Multiselect question {question_id}: index {index} out of range")
                return validated_indices
            except ValueError:
                logger.warning(f"Multiselect question {question_id}: cannot parse '{answer}' as comma-separated indices")
                return []
        else:
            logger.warning(f"Multiselect question {question_id}: expected list or string, got {type(answer)}")
            return []


def _validate_date_answer(answer: Any, question_id: str) -> str:
    """
    Validate and convert date answer to MM/DD/YYYY format.
    
    Args:
        answer: The answer to validate
        question_id: Question identifier for logging
        
    Returns:
        Validated date string in MM/DD/YYYY format
    """
    if not answer:
        return None
    
    if isinstance(answer, str):
        # Try to parse and format the date
        try:
            # Try different date formats
            date_formats = [
                '%m/%d/%Y', '%m/%d/%y',  # MM/DD/YYYY, MM/DD/YY
                '%Y-%m-%d', '%y-%m-%d',  # YYYY-MM-DD, YY-MM-DD
                '%d/%m/%Y', '%d/%m/%y',  # DD/MM/YYYY, DD/MM/YY
                '%B %d, %Y', '%b %d, %Y',  # January 1, 2023, Jan 1, 2023
                '%d %B %Y', '%d %b %Y',  # 1 January 2023, 1 Jan 2023
            ]
            
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(answer, fmt)
                    formatted_date = parsed_date.strftime('%m/%d/%Y')
                    logger.info(f"Date question {question_id}: '{answer}' -> '{formatted_date}'")
                    return formatted_date
                except ValueError:
                    continue
            
            logger.warning(f"Date question {question_id}: cannot parse date '{answer}'")
            return answer
            
        except Exception as e:
            logger.warning(f"Date question {question_id}: error parsing '{answer}': {str(e)}")
            return answer
    else:
        logger.warning(f"Date question {question_id}: expected string, got {type(answer)}")
        return str(answer) if answer is not None else None 


def _validate_number_answer(answer: Any, question_id: str) -> Union[int, float, str]:
    """
    Validate and convert number answer.
    
    Args:
        answer: The answer to validate
        question_id: Question identifier for logging
        
    Returns:
        Validated number (int, float, or string representation)
    """
    if answer is None:
        return None
    
    if isinstance(answer, (int, float)):
        return answer
    
    if isinstance(answer, str):
        # Remove any non-numeric characters except decimal point and minus sign
        cleaned_answer = ''.join(c for c in answer if c.isdigit() or c in '.-')
        
        # Handle edge cases
        if not cleaned_answer or cleaned_answer == '.' or cleaned_answer == '-':
            logger.warning(f"Number question {question_id}: invalid format '{answer}'")
            return None
        
        try:
            # Convert to float first to handle both integers and decimals
            number_value = float(cleaned_answer)
            
            # Return as integer if it's a whole number, otherwise as float
            if number_value.is_integer():
                return int(number_value)
            else:
                return number_value
                
        except (ValueError, TypeError):
            logger.warning(f"Number question {question_id}: cannot parse '{answer}' as number")
            return None
    else:
        logger.warning(f"Number question {question_id}: expected number or string, got {type(answer)}")
        return None 