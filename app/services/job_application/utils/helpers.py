"""Helper functions for cleaning strings and labels."""
import re

def clean_string(s):
    """Clean a string by removing special characters and replacing hyphens and underscores with spaces."""
    s = s.replace("-", " ").replace("_", " ")
    return re.sub(r'[^A-Za-z0-9 ]+', '', s)

def clean_label(s):
    """Clean a label by removing special characters and replacing hyphens and underscores with spaces."""
    # Keep important characters
    s = s.replace("-", " ").replace("_", " ")
    cleaned = re.sub(r"[^A-Za-z0-9?!/.' ]+", '', s)

    # Strip extra spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Capitalize if all lowercase
    return cleaned.capitalize() if cleaned.islower() else cleaned
