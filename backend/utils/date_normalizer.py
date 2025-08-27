"""
Date Normalization Utilities
Handles normalization of dates in various formats to standardized YYYY-MM format
"""
import re
from datetime import datetime
from typing import Optional, Tuple

def normalize_education_date(date_str: str) -> Optional[str]:
    """
    Normalize education date to YYYY-MM format
    
    Args:
        date_str: Date string in various formats (e.g., "2018-2022", "2018", "2018-05", "May 2018")
        
    Returns:
        Normalized date string in YYYY-MM format, or None if invalid
    """
    if not date_str:
        return None
        
    # Remove any extra whitespace
    date_str = date_str.strip()
    
    # Handle year ranges (e.g., "2018-2022")
    if '-' in date_str:
        parts = date_str.split('-')
        if len(parts) == 2:
            start_year = parts[0].strip()
            end_year = parts[1].strip()
            
            # Validate years
            if not (start_year.isdigit() and end_year.isdigit()):
                return None
                
            # Return start year with January as default month
            return f"{start_year}-01"
    
    # Handle single year (e.g., "2018")
    if date_str.isdigit() and len(date_str) == 4:
        return f"{date_str}-01"
    
    # Handle month-year format (e.g., "May 2018", "05/2018", "2018-05")
    month_patterns = [
        (r'(\d{4})-(\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}"),  # YYYY-MM
        (r'(\d{2})/(\d{4})', lambda m: f"{m.group(2)}-{m.group(1)}"),  # MM/YYYY
        (r'(\w+)\s+(\d{4})', lambda m: f"{m.group(2)}-{_month_to_number(m.group(1))}"),  # Month YYYY
    ]
    
    for pattern, formatter in month_patterns:
        match = re.match(pattern, date_str, re.IGNORECASE)
        if match:
            try:
                normalized = formatter(match)
                # Validate the date
                datetime.strptime(normalized, '%Y-%m')
                return normalized
            except (ValueError, AttributeError):
                continue
    
    return None

def _month_to_number(month_str: str) -> str:
    """Convert month name to two-digit number"""
    months = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    return months.get(month_str.lower()[:3], '01')

def normalize_education_dates(start_date: str, end_date: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize both start and end dates for education entries
    
    Args:
        start_date: Start date string
        end_date: End date string
        
    Returns:
        Tuple of (normalized_start_date, normalized_end_date) in YYYY-MM format
    """
    normalized_start = normalize_education_date(start_date)
    normalized_end = normalize_education_date(end_date)
    
    # If end date is "Present" or similar, use current date
    if end_date and end_date.lower() in ['present', 'current', 'now']:
        current_date = datetime.now()
        normalized_end = f"{current_date.year}-{current_date.month:02d}"
    
    return normalized_start, normalized_end 