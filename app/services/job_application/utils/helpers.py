import re

def clean_string(s):
    return re.sub(r'[^A-Za-z0-9 ]+', '', s)