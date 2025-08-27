"""
Robust JSON extraction helper module for RecruitIQ.

This module provides improved JSON extraction capabilities for handling
responses from local LLM models that may not always return perfectly
formatted JSON.
"""
import json
import re
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

def extract_json_robustly(text: str, default_result: Any = None) -> Any:
    """
    Robustly extract JSON from potentially malformed text with multiple fallback mechanisms.
    
    Args:
        text: The text that may contain JSON
        default_result: Default value to return if extraction fails
        
    Returns:
        Extracted JSON object or default_result if extraction fails
    """
    if not text:
        logger.warning("Empty text provided for JSON extraction")
        return default_result
        
    # Store original text length for logging
    original_length = len(text)
    logger.debug(f"Attempting to extract JSON from {original_length} chars of text")
    
    # Try direct JSON parsing first (fastest)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, trying extraction methods")
    
    # Method 1: Find the outermost matching JSON braces/brackets
    try:
        # For arrays
        if '[' in text and ']' in text:
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    logger.debug("Failed to parse array with simple extraction")
        
        # For objects
        if '{' in text and '}' in text:
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    logger.debug("Failed to parse object with simple extraction")
    except Exception as e:
        logger.debug(f"Simple extraction method failed: {str(e)}")
    
    # Method 2: Use regex to find JSON patterns
    try:
        # Find array pattern with nested content
        array_match = re.search(r'\[(.*)\]', text, re.DOTALL)
        if array_match:
            try:
                json_str = f"[{array_match.group(1)}]"
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.debug("Failed to parse array with regex")
        
        # Find object pattern with nested content
        object_match = re.search(r'\{(.*)\}', text, re.DOTALL)
        if object_match:
            try:
                json_str = f"{{{object_match.group(1)}}}"
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.debug("Failed to parse object with regex")
    except Exception as e:
        logger.debug(f"Regex extraction method failed: {str(e)}")
    
    # Method 3: Progressive repair of JSON
    try:
        repaired = attempt_json_repair(text)
        if repaired is not None:
            return repaired
    except Exception as e:
        logger.debug(f"JSON repair method failed: {str(e)}")
    
    # Method 4: Extract any JSON-like structures
    try:
        for pattern in [r'\{[^{]*?\}', r'\[[^[]*?\]']:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    result = json.loads(match)
                    if result:  # Only return non-empty results
                        return result
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.debug(f"Pattern extraction method failed: {str(e)}")
    
    # If all methods fail, return the default
    logger.warning(f"All JSON extraction methods failed for {original_length} chars of text")
    return default_result

def attempt_json_repair(text: str) -> Optional[Any]:
    """
    Attempt to repair malformed JSON by fixing common issues.
    
    Args:
        text: Potentially malformed JSON text
        
    Returns:
        Parsed JSON object or None if repair fails
    """
    # Remove markdown code block markers
    text = re.sub(r'```(?:json)?', '', text)
    text = text.strip()
    
    # Check if we have potential JSON brackets/braces
    if not (('[' in text and ']' in text) or ('{' in text and '}' in text)):
        return None
    
    # Try fixing common JSON errors
    repairs = [
        # Fix unquoted property names
        (r'(\s*)(\w+)(\s*):(\s*)', r'\1"\2"\3:\4'),
        # Fix trailing commas in arrays
        (r',(\s*)]', r'\1]'),
        # Fix trailing commas in objects
        (r',(\s*)}', r'\1}'),
        # Fix missing quotes around string values (limited cases)
        (r':\s*([a-zA-Z][a-zA-Z0-9_]*?)(\s*[,}])', r': "\1"\2'),
        # Fix single quotes used instead of double quotes
        (r"'([^']*?)'", r'"\1"'),
        # Fix line breaks within string literals
        (r'(".*?)[\n\r](.*?")', r'\1\\n\2'),
    ]
    
    # Apply repairs in sequence
    repaired = text
    for pattern, replacement in repairs:
        repaired = re.sub(pattern, replacement, repaired)
    
    # Try to parse the repaired JSON
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        # Try one more approach - find the innermost valid JSON
        try:
            # For arrays
            if '[' in repaired and ']' in repaired:
                array_matches = list(re.finditer(r'\[(.*?)\]', repaired, re.DOTALL))
                for match in reversed(array_matches):  # Try innermost matches first
                    try:
                        json_str = match.group(0)
                        result = json.loads(json_str)
                        if result:  # Only return non-empty results
                            return result
                    except json.JSONDecodeError:
                        continue
            
            # For objects
            if '{' in repaired and '}' in repaired:
                object_matches = list(re.finditer(r'\{(.*?)\}', repaired, re.DOTALL))
                for match in reversed(object_matches):  # Try innermost matches first
                    try:
                        json_str = match.group(0)
                        result = json.loads(json_str)
                        if result:  # Only return non-empty results
                            return result
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
    
    return None

def extract_structured_data(text: str, entry_type: str = "experience") -> List[Dict[str, Any]]:
    """
    Extract a list of structured data entries from model output text,
    with smart fallbacks for different formats.
    
    Args:
        text: Model output text
        entry_type: Type of entries to extract (experience, education, skills)
        
    Returns:
        List of structured data dictionaries
    """
    # Start with robust JSON extraction
    extracted = extract_json_robustly(text, default_result=[])
    
    # Handle different possible formats
    if isinstance(extracted, dict):
        # Format: {"experience": [...]} or {"entries": [...]}
        for key in [entry_type, "entries", "data", "items"]:
            if key in extracted and isinstance(extracted[key], list):
                return extracted[key]
        
        # Format: {"1": {...}, "2": {...}}
        numbered_entries = []
        for key, value in extracted.items():
            if isinstance(value, dict):
                numbered_entries.append(value)
        if numbered_entries:
            return numbered_entries
        
        # Single entry as dict
        return [extracted]
    
    elif isinstance(extracted, list):
        # Already a list, check if items are dicts
        if extracted and isinstance(extracted[0], dict):
            return extracted
        elif extracted and all(isinstance(item, (str, int, float, bool)) for item in extracted):
            # List of primitive values (e.g., skills)
            return [{"name": item} for item in extracted]
    
    # If extraction failed completely, return a default error entry
    logger.warning(f"Failed to extract structured {entry_type} data")
    error_entry = {
        "title": f"Parsing Error" if entry_type in ["experience", "education"] else "Error",
        "company" if entry_type == "experience" else "institution": "Unknown",
        "description": "Failed to extract structured data from model response"
    }
    return [error_entry]

def clean_and_standardize_entries(entries: List[Dict[str, Any]], entry_type: str) -> List[Dict[str, Any]]:
    """
    Clean and standardize extracted entries to ensure they have all required fields.
    
    Args:
        entries: List of extracted entries
        entry_type: Type of entries (experience, education, skills)
        
    Returns:
        Cleaned and standardized entries
    """
    if not entries:
        return []
    
    standardized = []
    
    # Define required fields for each entry type
    required_fields = {
        "experience": {
            "title": "",
            "company": "",
            "location": "",
            "date_range": "",
            "description": "",
            "start_date": "",
            "end_date": ""
        },
        "education": {
            "degree": "",
            "institution": "",
            "location": "",
            "date_range": "",
            "description": "",
            "start_date": "",
            "end_date": "",
            "gpa": None
        },
        "skills": {
            "name": "",
            "category": "technical"
        }
    }
    
    # Get the template for this entry type
    template = required_fields.get(entry_type, {"name": ""})
    
    # Process each entry
    for entry in entries:
        # Handle different field name variations
        field_mappings = {
            "experience": {
                "job_title": "title",
                "position": "title",
                "role": "title",
                "employer": "company",
                "organization": "company",
                "period": "date_range",
                "dates": "date_range",
                "duration": "date_range",
                "responsibilities": "description",
                "details": "description"
            },
            "education": {
                "school": "institution",
                "university": "institution",
                "college": "institution",
                "major": "degree",
                "field": "degree",
                "program": "degree",
                "period": "date_range",
                "dates": "date_range",
                "duration": "date_range",
                "details": "description"
            }
        }
        
        # Create a new entry with all required fields
        new_entry = template.copy()
        
        # Map variations to standard field names
        mapped_entry = {}
        for key, value in entry.items():
            # Convert key to lowercase for case-insensitive matching
            lower_key = key.lower()
            # Use mapping if available
            if entry_type in field_mappings and lower_key in field_mappings[entry_type]:
                mapped_key = field_mappings[entry_type][lower_key]
                mapped_entry[mapped_key] = value
            else:
                # Keep original key if no mapping exists
                mapped_entry[key] = value
        
        # Update the new entry with mapped values
        for key, value in mapped_entry.items():
            if key in new_entry:
                new_entry[key] = value
        
        # Special processing for description field - combine relevant fields
        if entry_type in ["experience", "education"]:
            description_fields = ["description", "responsibilities", "achievements", "details"]
            combined_desc = []
            for field in description_fields:
                if field in mapped_entry and mapped_entry[field]:
                    if isinstance(mapped_entry[field], list):
                        combined_desc.extend(mapped_entry[field])
                    else:
                        combined_desc.append(str(mapped_entry[field]))
            
            if combined_desc:
                new_entry["description"] = "\n".join(combined_desc)
        
        standardized.append(new_entry)
    
    return standardized
