"""
Date Utility Functions
Provides helper functions for parsing and standardizing dates from resumes.
"""
import logging
from datetime import datetime
from dateutil.parser import parse

logger = logging.getLogger(__name__)

def normalize_date(date_str: str) -> str:
    """
    Parses a date string and returns it in 'YYYY-MM-DD' format.
    Handles common resume date formats, including 'Present' or 'Current'.

    Args:
        date_str (str): The date string to parse (e.g., 'Jan 2022', '2021', 'Present').

    Returns:
        str: The standardized date string, or None if parsing fails.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    clean_date_str = date_str.strip()

    # Handle 'Present', 'Current', etc.
    if clean_date_str.lower() in ['present', 'current', 'now', 'today']:
        return datetime.now().strftime('%Y-%m-%d')

    try:
        # The `default` parameter sets the day and month to 1 if they are not present.
        # This is useful for formats like '2021'.
        dt = parse(clean_date_str, default=datetime(datetime.now().year, 1, 1))
        return dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        logger.warning(f"Could not parse date: {date_str}")
        return None

def normalize_date_range(date_range_str: str):
    """
    Parses a date range string (e.g., "Mar 2021 - Mar 2023", "May 2024 - Present")
    and returns a tuple of (start_date, end_date) in 'YYYY-MM-DD' format.
    """
    if not date_range_str or not isinstance(date_range_str, str):
        return None, None

    parts = [p.strip() for p in date_range_str.split('-')]
    
    start_date_str = parts[0]
    end_date_str = parts[1] if len(parts) > 1 else 'Present'
    
    start_date = normalize_date(start_date_str)
    
    # If end date is 'Present' or similar, normalize_date will return today's date
    # We want it to be None for 'current' roles.
    if end_date_str.lower().strip() in ['present', 'current', 'now', 'today']:
        end_date = None
    else:
        end_date = normalize_date(end_date_str)
        
    return start_date, end_date
