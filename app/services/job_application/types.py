"""Types and constants for job application service."""

from app.schemas.application import QuestionType
from typing import List

# Job Types
JOB_TYPE_OPTIONS = [
    {'value': 'fulltime', 'label': 'Full-time'},
    {'value': 'parttime', 'label': 'Part-time'},
    {'value': 'temporary', 'label': 'Temporary'},
    {'value': 'contract', 'label': 'Contract'},
    {'value': 'internship', 'label': 'Internship'}
]

# Location Types
LOCATION_TYPE_OPTIONS = [
    # US Locations
    {'value': 'new-york-ny', 'label': 'New York, NY'},
    {'value': 'mountain-view-ca', 'label': 'Mountain View, CA'},
    {'value': 'san-francisco-ca', 'label': 'San Francisco, CA'},
    {'value': 'san-jose-ca', 'label': 'San Jose, CA'},
    {'value': 'sunnyvale-ca', 'label': 'Sunnyvale, CA'},
    {'value': 'san-mateo-ca', 'label': 'San Mateo, CA'},
    {'value': 'redwood-city-ca', 'label': 'Redwood City, CA'},
    {'value': 'palo-alto-ca', 'label': 'Palo Alto, CA'},
    {'value': 'menlo-park-ca', 'label': 'Menlo Park, CA'},
    {'value': 'foster-city-ca', 'label': 'Foster City, CA'},
    {'value': 'belmont-ca', 'label': 'Belmont, CA'},
    {'value': 'bellevue-wa', 'label': 'Bellevue, WA'},
    {'value': 'seattle-wa', 'label': 'Seattle, WA'},
    {'value': 'austin-tx', 'label': 'Austin, TX'},
    {'value': 'boston-ma', 'label': 'Boston, MA'},
    {'value': 'los-angeles-ca', 'label': 'Los Angeles, CA'},
    {'value': 'chicago-il', 'label': 'Chicago, IL'},
    {'value': 'denver-co', 'label': 'Denver, CO'},
    {'value': 'miami-fl', 'label': 'Miami, FL'},
    {'value': 'washington-dc', 'label': 'Washington, DC'},
    {'value': 'portland-or', 'label': 'Portland, OR'},
    {'value': 'atlanta-ga', 'label': 'Atlanta, GA'},
    {'value': 'dallas-tx', 'label': 'Dallas, TX'},
    {'value': 'san-diego-ca', 'label': 'San Diego, CA'},
    {'value': 'nashville-tn', 'label': 'Nashville, TN'},
    {'value': 'philadelphia-pa', 'label': 'Philadelphia, PA'},
    {'value': 'phoenix-az', 'label': 'Phoenix, AZ'},
    {'value': 'minneapolis-mn', 'label': 'Minneapolis, MN'},
    {'value': 'pittsburgh-pa', 'label': 'Pittsburgh, PA'},
    {'value': 'raleigh-nc', 'label': 'Raleigh, NC'},
    # Canada Locations
    {'value': 'toronto-on', 'label': 'Toronto, Ontario'},
    {'value': 'vancouver-bc', 'label': 'Vancouver, British Columbia'},
    {'value': 'montreal-qc', 'label': 'Montreal, Quebec'},
    {'value': 'calgary-ab', 'label': 'Calgary, Alberta'},
    {'value': 'ottawa-on', 'label': 'Ottawa, Ontario'},
    {'value': 'edmonton-ab', 'label': 'Edmonton, Alberta'},
    {'value': 'halifax-ns', 'label': 'Halifax, Nova Scotia'},
    {'value': 'victoria-bc', 'label': 'Victoria, British Columbia'},
    {'value': 'winnipeg-mb', 'label': 'Winnipeg, Manitoba'},
    {'value': 'quebec-city-qc', 'label': 'Quebec City, Quebec'},
    {'value': 'hamilton-on', 'label': 'Hamilton, Ontario'},
    {'value': 'kitchener-on', 'label': 'Kitchener, Ontario'},
    {'value': 'mississauga-on', 'label': 'Mississauga, Ontario'},
    {'value': 'burnaby-bc', 'label': 'Burnaby, British Columbia'},
    {'value': 'surrey-bc', 'label': 'Surrey, British Columbia'},
    {'value': 'remote', 'label': 'Remote'}
]

# Role Levels
ROLE_LEVEL_OPTIONS = [
    {'value': 'internship', 'label': 'Intern & Co-op'},
    {'value': 'entry', 'label': 'Entry Level & New Grad'},
    {'value': 'associate', 'label': 'Junior (1-3 years)'},
    {'value': 'mid-senior', 'label': 'Senior (3-5 years)'},
    {'value': 'director', 'label': 'Director & Lead'},
    {'value': 'executive', 'label': 'Executive'}
]

# Industry Specializations
INDUSTRY_SPECIALIZATION_OPTIONS = [
    {'value': 'backend', 'label': 'Backend Engineer'},
    {'value': 'frontend', 'label': 'Frontend Engineer'},
    {'value': 'fullstack', 'label': 'Full Stack Engineer'},
    {'value': 'mobile', 'label': 'Mobile Development'},
    {'value': 'devops', 'label': 'DevOps & Infrastructure'},
    {'value': 'data_science', 'label': 'Data Science'},
    {'value': 'data_engineer', 'label': 'Data Engineer'},
    {'value': 'ml_ai', 'label': 'Machine Learning & AI'},
    {'value': 'product', 'label': 'Product Management'},
    {'value': 'ux_ui', 'label': 'UX/UI Design'},
    {'value': 'qa', 'label': 'QA & Testing'},
    {'value': 'security', 'label': 'Security Engineer'},
    {'value': 'cloud', 'label': 'Cloud Computing'},
    {'value': 'blockchain', 'label': 'Blockchain'},
    {'value': 'game_dev', 'label': 'Game Development'},
    {'value': 'ar_vr', 'label': 'AR/VR Development'},
    {'value': 'embedded', 'label': 'Embedded Systems'},
    {'value': 'iot', 'label': 'IoT Engineer'},
    {'value': 'robotics', 'label': 'Robotics'},
    {'value': 'fintech', 'label': 'Fintech'},
    {'value': 'healthtech', 'label': 'Healthtech'},
    {'value': 'edtech', 'label': 'Edtech'},
    {'value': 'ecommerce', 'label': 'E-commerce'},
    {'value': 'martech', 'label': 'Marketing Technology'},
    {'value': 'enterprise', 'label': 'Enterprise Software'}
]

# Company Sizes
COMPANY_SIZE_OPTIONS = [
    {'value': 'startup', 'label': 'Startup (1-50 employees)'},
    {'value': 'small', 'label': 'Small (51-200 employees)'},
    {'value': 'medium', 'label': 'Medium (201-1000 employees)'},
    {'value': 'large', 'label': 'Large (1001-5000 employees)'},
    {'value': 'enterprise', 'label': 'Enterprise (5000+ employees)'}
]

# Education Degrees
DEGREE_OPTIONS = [
    {'value': 'high_school', 'label': 'High School'},
    {'value': 'associate', 'label': 'Associate Degree'},
    {'value': 'bachelor', 'label': "Bachelor's Degree"},
    {'value': 'master', 'label': "Master's Degree"},
    {'value': 'doctorate', 'label': 'Doctorate'},
    {'value': 'other', 'label': 'Other'}
]

# Supported job portals
SUPPORTED_JOB_PORTALS = {
    'lever.co': 'Lever',
    'greenhouse.io': 'Greenhouse',
    'ashbyhq.com': 'Ashby',
    'workable.com': 'Workable'
}

# Create lookup dictionaries for easy value to label mapping
JOB_TYPE_MAPPING = {option['value']: option['label'] for option in JOB_TYPE_OPTIONS}
LOCATION_TYPE_MAPPING = {option['value']: option['label'] for option in LOCATION_TYPE_OPTIONS}
ROLE_LEVEL_MAPPING = {option['value']: option['label'] for option in ROLE_LEVEL_OPTIONS}
INDUSTRY_SPECIALIZATION_MAPPING = {option['value']: option['label'] for option in INDUSTRY_SPECIALIZATION_OPTIONS}
COMPANY_SIZE_MAPPING = {option['value']: option['label'] for option in COMPANY_SIZE_OPTIONS}
DEGREE_MAPPING = {option['value']: option['label'] for option in DEGREE_OPTIONS}

# Related specializations map for expanding specialization filters
RELATED_SPECIALIZATIONS_MAP = {
    'frontend': ['fullstack', 'ux_ui'],
    'backend': ['fullstack', 'devops', 'security'],
    'fullstack': ['frontend', 'backend'],
    'mobile': ['frontend', 'game_dev', 'ar_vr'],
    'devops': ['backend', 'cloud', 'security'],
    'ml_ai': ['data_science', 'data_engineer'],
    'data_science': ['ml_ai', 'data_engineer'],
    'ux_ui': ['frontend', 'product'],
    'qa': ['backend'],
    'security': ['backend', 'devops'],
    'data_engineer': ['backend', 'data_science', 'ml_ai'],
    'product': ['ux_ui'],
    'cloud': ['devops', 'backend'],
    'blockchain': ['backend', 'security', 'fintech'],
    'game_dev': ['frontend', 'mobile', 'ar_vr'],
    'ar_vr': ['frontend', 'mobile', 'game_dev'],
    'embedded': ['backend', 'iot'],
    'iot': ['embedded', 'backend', 'cloud'],
    'robotics': ['embedded', 'ml_ai', 'iot'],
    'fintech': ['backend', 'security', 'data_science'],
    'healthtech': ['backend', 'data_science', 'ml_ai'],
    'edtech': ['frontend', 'backend', 'product'],
    'ecommerce': ['frontend', 'backend', 'product'],
    'martech': ['frontend', 'data_science', 'product'],
    'enterprise': ['backend', 'devops', 'security']
}

def get_related_specializations(specialization: str) -> List[str]:
    """Get related specializations for a given specialization."""
    return RELATED_SPECIALIZATIONS_MAP.get(specialization, [])

def expand_specializations(specializations: List[str]) -> List[str]:
    """Expand a list of specializations to include related ones."""
    expanded = set(specializations)  # Start with original specializations
    
    for spec in specializations:
        related = get_related_specializations(spec)
        expanded.update(related)
    
    return list(expanded)


def get_field_type(field_type_string: str, tag_name: str = None) -> QuestionType:
    """Convert string field type to QuestionType enum."""
    try:
        if tag_name == 'textarea':
            return QuestionType.TEXTAREA
        elif tag_name == 'select' or tag_name == 'select-one':
            return QuestionType.SELECT
        
        return QuestionType(field_type_string.lower())
    except ValueError:
        return QuestionType.INPUT

def map_profile_value(profile_key: str, profile_value) -> str:
    """Map profile values to their display labels using the type mappings."""
    if not profile_value:
        return profile_value
    
    # Handle list values (convert to comma-separated string of labels)
    if isinstance(profile_value, list):
        if profile_key == 'jobTypes':
            return ', '.join([JOB_TYPE_MAPPING.get(val, val) for val in profile_value])
        elif profile_key == 'locationPreferences':
            return ', '.join([LOCATION_TYPE_MAPPING.get(val, val) for val in profile_value])
        elif profile_key == 'industrySpecializations':
            return ', '.join([INDUSTRY_SPECIALIZATION_MAPPING.get(val, val) for val in profile_value])
        else:
            return ', '.join(profile_value)
    
    # Handle single values
    if profile_key == 'roleLevel':
        return ROLE_LEVEL_MAPPING.get(profile_value, profile_value)
    elif profile_key == 'companySize':
        return COMPANY_SIZE_MAPPING.get(profile_value, profile_value)
    elif profile_key == 'degree':
        return DEGREE_MAPPING.get(profile_value, profile_value)
    
    return profile_value