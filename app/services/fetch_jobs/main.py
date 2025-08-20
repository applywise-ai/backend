import csv
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
from jobspy import scrape_jobs
from app.services.job_application.types import (INDUSTRY_SPECIALIZATION_MAPPING,
    LOCATION_TYPE_OPTIONS, ROLE_LEVEL_MAPPING, SUPPORTED_JOB_PORTALS)
from app.services.ai_assistant import AIAssistant

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobFetcher:
    """
    A class to fetch jobs from multiple job sites using jobspy library.
    Supports Linkedin for now.
    """
    
    def __init__(self, 
                 results_wanted: int = 500,
                 hours_old: int = 1,
                 linkedin_fetch_description: bool = True,
                 proxies: Optional[List[str]] = None):
        """
        Initialize JobFetcher with default parameters.
        
        Args:
            results_wanted: Maximum number of jobs to fetch (default: 500)
            hours_old: Only fetch jobs posted within this many hours (default: 1)
            linkedin_fetch_description: Whether to fetch detailed descriptions from LinkedIn (default: True)
            proxies: List of proxy servers to use (optional)
        """
        self.results_wanted = results_wanted
        self.hours_old = hours_old
        self.linkedin_fetch_description = linkedin_fetch_description
        self.proxies = proxies
        
        # Default job sites to search
        self.site_names = [
            "linkedin"
        ]
        
        # Initialize AI Assistant with empty profile
        self.ai_assistant = None
        try:
            self.ai_assistant = AIAssistant({}, override_gemini_model="gemini-1.5-flash")
            logger.info("AI Assistant initialized for job summarization")
        except Exception as e:
            logger.warning(f"Failed to initialize AI Assistant: {str(e)}")
        
        logger.info(f"JobFetcher initialized with results wanted: {results_wanted}, hours old: {hours_old}")
    
    def fetch_jobs(self, specialization: str, location: str) -> pd.DataFrame:
        """
        Fetch jobs from multiple sources for a given location.
        
        Args:
            location: The location to search for jobs (e.g., "San Francisco, CA")
            specialization: The specialization to search for jobs (e.g., "backend")
            
        Returns:
            pandas.DataFrame: DataFrame containing job listings
        """
        try:
            # Get the specialization from the specialization_options
            specialization_label = INDUSTRY_SPECIALIZATION_MAPPING[specialization]
            
            logger.info(f"Fetching jobs for specialization: '{specialization_label}' in location: {location}")
            
            # Prepare search parameters
            search_params = {
                "site_name": self.site_names,
                "search_term": specialization_label,
                "location": location,
                "results_wanted": self.results_wanted,
                "hours_old": self.hours_old,
                "linkedin_fetch_description": self.linkedin_fetch_description
            }
            
            if self.proxies:
                search_params["proxies"] = self.proxies
            
            # Fetch jobs using jobspy
            jobs_df = scrape_jobs(**search_params)
            
            # Filter jobs to only include those from supported job portals
            if not jobs_df.empty and 'job_url_direct' in jobs_df.columns:
                # Get the list of supported portal domains
                supported_domains = list(SUPPORTED_JOB_PORTALS.keys())
                
                # Filter jobs where job_url_direct contains any of the supported domains
                def is_supported_portal(url):
                    if pd.isna(url) or not url:
                        return False
                    return any(domain in url.lower() for domain in supported_domains)
                
                # Apply the filter
                initial_count = len(jobs_df)
                jobs_df = jobs_df[jobs_df['job_url_direct'].apply(is_supported_portal)]
                filtered_count = len(jobs_df)
                
                logger.info(f"Filtered jobs from {initial_count} to {filtered_count} supported portal jobs")
            else:
                logger.warning("No 'job_url_direct' column found in jobs DataFrame or DataFrame is empty")
            
            # Log results
            logger.info(f"Successfully fetched {len(jobs_df)} jobs for location: {location}")
            
            # Add metadata
            jobs_df['posted_at'] = datetime.now().isoformat()
            jobs_df['specialization'] = specialization
            
            return jobs_df
            
        except Exception as e:
            logger.error(f"Error fetching jobs for location {location}: {str(e)}")
            raise
    
    def fetch_multiple_searches(self, searches: List[Dict[str, str]], summarize_descriptions: bool = True) -> pd.DataFrame:
        """
        Fetch jobs from multiple search terms and locations and combine results.
        
        Args:
            searches: List of dictionaries with 'specialization' and 'location' keys
                     Example: [{'specialization': 'backend', 'location': 'San Francisco, CA'},
                              {'specialization': 'backend', 'location': 'New York, NY'}]
            summarize_descriptions: Whether to use AI to summarize job descriptions (default: True)
            
        Returns:
            pandas.DataFrame: Combined DataFrame containing job listings from all searches
        """
        all_jobs = []
        
        for search in searches:
            try:
                specialization = search.get('specialization')
                location = search.get('location')
                
                if not specialization or not location:
                    logger.warning(f"Skipping invalid search: {search}")
                    continue
                
                jobs_df = self.fetch_jobs(specialization, location)
                all_jobs.append(jobs_df)
                
            except Exception as e:
                logger.error(f"Failed to fetch jobs for search {search}: {str(e)}")
                continue
        
        if not all_jobs:
            logger.warning("No jobs were successfully fetched from any search")
            return pd.DataFrame()
        
        # Filter out empty DataFrames and ensure consistent columns
        non_empty_jobs = []
        expected_columns = None
        
        for jobs_df in all_jobs:
            if jobs_df.empty:
                logger.info("Skipping empty DataFrame")
                continue
                
            # Set expected columns from the first non-empty DataFrame
            if expected_columns is None:
                expected_columns = list(jobs_df.columns)
                non_empty_jobs.append(jobs_df)
            else:
                # Ensure this DataFrame has the same columns as the first one
                missing_cols = set(expected_columns) - set(jobs_df.columns)
                extra_cols = set(jobs_df.columns) - set(expected_columns)
                
                if missing_cols:
                    logger.info(f"Adding missing columns to DataFrame: {missing_cols}")
                    for col in missing_cols:
                        jobs_df[col] = None
                
                if extra_cols:
                    logger.info(f"Dropping extra columns from DataFrame: {extra_cols}")
                    jobs_df = jobs_df[expected_columns]
                
                non_empty_jobs.append(jobs_df)
        
        if not non_empty_jobs:
            logger.warning("No non-empty job DataFrames to combine")
            return pd.DataFrame()
        
        # Combine all results with consistent columns
        combined_jobs = pd.concat(non_empty_jobs, ignore_index=True)
        
        # Remove duplicates based on job title, company, and location
        combined_jobs = combined_jobs.drop_duplicates(
            subset=['job_url_direct'], 
            keep='first'
        )
        
        logger.info(f"Combined {len(combined_jobs)} unique jobs from {len(searches)} searches")
        
        # Summarize job descriptions using AI if requested and AI assistant is available
        if summarize_descriptions and self.ai_assistant and not combined_jobs.empty:
            logger.info("Starting AI-powered job description summarization...")
            try:
                combined_jobs = self.ai_assistant.summarize_job_descriptions(combined_jobs)
                logger.info("Job description summarization completed")
            except Exception as e:
                logger.error(f"Error during job summarization: {str(e)}")
                logger.info("Continuing without job summarization")
        
        return combined_jobs
    
    def save_jobs_to_csv(self, jobs_df: pd.DataFrame, filename: str = None) -> str:
        """
        Save jobs DataFrame to CSV file.
        
        Args:
            jobs_df: DataFrame containing job listings
            filename: Output filename (if None, generates timestamped filename)
            
        Returns:
            str: Path to the saved CSV file
        """
        try:
            if filename is None:
                filename = f"jobs.csv"
            
            # Ensure the filename has .csv extension
            if not filename.endswith('.csv'):
                filename += '.csv'
            
            jobs_df.to_csv(
                filename, 
                quoting=csv.QUOTE_NONNUMERIC, 
                escapechar="\\", 
                index=False
            )
            logger.info(f"Jobs saved to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving jobs to {filename}: {str(e)}")
            raise
    
    def _format_for_upload(self, jobs_df: pd.DataFrame) -> pd.DataFrame:
        """
        Format jobs DataFrame for upload by cleaning and standardizing columns.
        
        Args:
            jobs_df: DataFrame containing job listings
            
        Returns:
            pandas.DataFrame: Formatted DataFrame ready for upload
        """
        try:
            # Create a copy to avoid modifying the original
            formatted_df = jobs_df.copy()
            
            logger.info(f"Formatting {len(formatted_df)} jobs for upload")
            
            # Clean job_level column - remove spaces and "level" if present
            if 'job_level' in formatted_df.columns:
                logger.info("Cleaning job_level column...")
                formatted_df['job_level'] = formatted_df['job_level'].astype(str).apply(
                    lambda x: x.replace(' ', '').replace('level', '').replace('Level', '') if not pd.isna(x) and x != 'nan' else x
                )
                logger.info(f"Job levels after cleaning: {formatted_df['job_level'].unique()}")
            
            # Set experience level to "director" if title contains "staff"
            if 'title' in formatted_df.columns and 'job_level' in formatted_df.columns:
                logger.info("Mapping job levels based on title...")
                
                def map_job_level(row):
                    reg_title = str(row['title']) if not pd.isna(row['title']) else ""
                    title = str(row['title']).lower() if not pd.isna(row['title']) else ""
                    for level in ROLE_LEVEL_MAPPING.keys():
                        if level in title:
                            return level
                    if ' staff' in title or 'staff ' in title:
                        return 'director'
                    elif 'new grad' in title:
                        return 'entry'
                    elif 'intern ' in title or ' intern' in title:
                        return 'internship'
                    elif 'junior' in title:
                        return 'associate'
                    elif 'VP' in reg_title:
                        return 'director'
                    elif 'manager' in title:
                        return 'mid-senior'
                    return row['job_level']
                
                formatted_df['job_level'] = formatted_df.apply(map_job_level, axis=1)
            
            # Clean location column - remove ", Canada" and convert to values
            if 'location' in formatted_df.columns:
                logger.info("Cleaning location column...")
                
                # Remove ", Canada" from location strings
                formatted_df['location'] = formatted_df['location'].astype(str).apply(
                    lambda x: x.replace(', Canada', '').replace(', CANADA', '') if not pd.isna(x) and x != 'nan' else x
                )
                
                # Create a mapping from labels to values for LOCATION_TYPE_OPTIONS
                location_mapping = {option['label']: option['value'] for option in LOCATION_TYPE_OPTIONS}
                
                # Convert location labels to values
                def map_location_to_value(location_str):
                    if pd.isna(location_str) or location_str == 'nan':
                        return None
                    
                    # Try exact match first
                    if location_str in location_mapping:
                        return location_mapping[location_str]
                    
                    # Try case-insensitive match
                    location_lower = location_str.lower()
                    for label, value in location_mapping.items():
                        if label.lower() == location_lower:
                            return value
                    
                    # If no match found, return the original string
                    logger.warning(f"No location mapping found for: {location_str}")
                    return location_str
                
                formatted_df['location'] = formatted_df['location'].apply(map_location_to_value)
                
                logger.info(f"Locations after mapping: {formatted_df['location'].unique()}")
            
            logger.info("Job formatting completed successfully")
            return formatted_df
            
        except Exception as e:
            logger.error(f"Error formatting jobs for upload: {str(e)}")
            raise
    
    def upload_jobs(self, jobs_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Upload jobs to database using column mapping and PostgresManager.
        
        Args:
            jobs_df: DataFrame containing job listings
            
        Returns:
            Dict: Upload statistics from database operation
        """
        try:
            # First format the data using the existing method
            formatted_df = self._format_for_upload(jobs_df)
            
            logger.info(f"Preparing {len(formatted_df)} jobs for database upload")
            
            # Define column mapping for database upload (df -> db)
            column_mapping = {
                'id': 'id',
                'title': 'title',
                'company': 'company',
                'company_logo': 'logo',
                'company_url': 'company_url',
                'company_description': 'company_description',
                'company_size': 'company_size',
                'location': 'location',
                'salary_min_range': 'salary_min_range',
                'salary_max_range': 'salary_max_range',
                'salary_currency': 'salary_currency',
                'job_type': 'job_type',
                'description': 'description',
                'posted_at': 'posted_date',
                'job_level': 'experience_level',
                'specialization': 'specialization',
                'responsibilities': 'responsibilities',
                'requirements': 'requirements',
                'job_url_direct': 'job_url',
                'skills': 'skills',
                'short_responsibilities': 'short_responsibilities',
                'short_qualifications': 'short_qualifications',
                'is_remote': 'is_remote',
                'provides_sponsorship': 'provides_sponsorship'
            }
            
            # Initialize PostgresManager and upload to database
            from app.db.supabase import SupabaseManager
            
            supabase_manager = SupabaseManager()
            upload_stats = supabase_manager.upload_jobs_dataframe(formatted_df, column_mapping)
            
            logger.info(f"Database upload completed:")
            logger.info(f"  Total rows: {upload_stats['total_rows']}")
            logger.info(f"  Successful uploads: {upload_stats['successful_uploads']}")
            logger.info(f"  Failed uploads: {upload_stats['failed_uploads']}")
            
            if upload_stats['errors']:
                logger.warning(f"  Errors: {len(upload_stats['errors'])}")
                for error in upload_stats['errors'][:3]:  # Log first 3 errors
                    logger.warning(f"    - {error}")
            
            return upload_stats
            
        except Exception as e:
            logger.error(f"Error uploading jobs to database: {str(e)}")
            raise
    

def main():
    """
    Fetch jobs for all specializations in United States and Canada and upload them to the database.
    """
    print("🚀 Starting job fetching for all specializations in US and Canada...")
    
    # Initialize JobFetcher with AI assistant
    job_fetcher = JobFetcher(hours_old=24)
    
    # Get all specializations from the mapping
    all_specializations = list(INDUSTRY_SPECIALIZATION_MAPPING.keys())
    
    # Create searches for all specializations in US and Canada
    searches = []
    locations = ['United States', 'Canada']
    
    for specialization in all_specializations:
        for location in locations:
            searches.append({
                'specialization': specialization,
                'location': location
            })
    
    try:
        print(f"📋 Fetching jobs for {len(searches)} search combinations...")
        print(f"🎯 Specializations: {len(all_specializations)}")
        print("   - " + ", ".join(all_specializations))
        print(f"🌍 Locations: {len(locations)}")
        print("   - " + ", ".join(locations))
        
        # Fetch jobs from all locations and specializations
        print("\n🔍 Fetching jobs from LinkedIn...")
        jobs_df = job_fetcher.fetch_multiple_searches(searches, summarize_descriptions=True)
        
        if jobs_df.empty:
            print("❌ No jobs were fetched. Exiting.")
            return
        
        print(f"✅ Successfully fetched {len(jobs_df)} jobs")
        
        # Display job statistics
        print("\n📊 Job Statistics:")
        print(f"   Total jobs: {len(jobs_df)}")
        if 'company' in jobs_df.columns:
            unique_companies = jobs_df['company'].nunique()
            print(f"   Unique companies: {unique_companies}")
        if 'location' in jobs_df.columns:
            unique_locations = jobs_df['location'].nunique()
            print(f"   Unique locations: {unique_locations}")
        if 'specialization' in jobs_df.columns:
            unique_specializations = jobs_df['specialization'].nunique()
            print(f"   Unique specializations: {unique_specializations}")
            # Show breakdown by specialization
            print("\n📈 Jobs by Specialization:")
            specialization_counts = jobs_df['specialization'].value_counts()
            for spec, count in specialization_counts.items():
                print(f"   - {spec}: {count} jobs")
        
        # Upload jobs to database
        print("\n🗄️ Uploading jobs to database...")
        upload_stats = job_fetcher.upload_jobs(jobs_df)
        
        # Display upload results
        print("\n📈 Upload Results:")
        print(f"   Total rows processed: {upload_stats['total_rows']}")
        print(f"   ✅ Successful uploads: {upload_stats['successful_uploads']}")
        print(f"   ❌ Failed uploads: {upload_stats['failed_uploads']}")
        if 'skipped_duplicates' in upload_stats:
            print(f"   ⏭️ Skipped duplicates: {upload_stats['skipped_duplicates']}")
        
        if upload_stats['errors']:
            print(f"   ⚠️ Errors: {len(upload_stats['errors'])}")
            for error in upload_stats['errors'][:3]:  # Show first 3 errors
                print(f"      - {error}")
        
        # Success summary
        success_rate = (upload_stats['successful_uploads'] / upload_stats['total_rows']) * 100 if upload_stats['total_rows'] > 0 else 0
        print(f"\n🎉 Upload completed with {success_rate:.1f}% success rate!")
        
        print(f"\n✅ All specializations job fetching and upload completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during job fetching and upload: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
