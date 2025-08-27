import streamlit as st
import json
import re
from typing import Any, Dict, List, Union

def sanitize_html(text: str) -> str:
    """
    Remove HTML tags and decode HTML entities from text to prevent XSS and display issues.
    
    Args:
        text: Text that may contain HTML
        
    Returns:
        str: Sanitized text with HTML tags removed
    """
    if not isinstance(text, str):
        return str(text)
    
    # Remove HTML tags
    html_pattern = re.compile(r'<[^>]+>')
    text = html_pattern.sub('', text)
    
    # Replace common HTML entities
    html_entities = {
        '&lt;': '<',
        '&gt;': '>',
        '&amp;': '&',
        '&quot;': '"',
        '&#39;': "'",
        '&nbsp;': ' '
    }
    
    for entity, char in html_entities.items():
        text = text.replace(entity, char)
    
    return text.strip()







def safe_get_skill_name(skill: Union[str, Dict[str, Any]]) -> str:
    """
    Safely extract skill name from various skill data formats.
    
    Args:
        skill: Can be a string, dictionary with 'name' key, or other format
        
    Returns:
        str: Clean skill name with HTML sanitized
    """
    if isinstance(skill, str):
        # Check if it looks like a dictionary string representation
        if skill.startswith("{'") or skill.startswith('{"'):
            try:
                # Try to parse as JSON or eval as dict
                if skill.startswith('{"'):
                    skill_dict = json.loads(skill)
                else:
                    skill_dict = eval(skill)  # Careful with eval, but needed for dict-like strings
                skill_name = skill_dict.get('name', str(skill_dict))
                return sanitize_html(skill_name)
            except (json.JSONDecodeError, SyntaxError, ValueError):
                # If parsing fails, return the original string sanitized
                return sanitize_html(skill)
        return sanitize_html(skill)
    elif isinstance(skill, dict):
        skill_name = skill.get('name', skill.get('skill_name', str(skill)))
        return sanitize_html(skill_name)
    else:
        return sanitize_html(str(skill))

def format_skills_list(skills: List[Union[str, Dict[str, Any]]]) -> List[str]:
    """
    Format a list of skills, handling mixed data types.
    
    Args:
        skills: List of skills in various formats
        
    Returns:
        List[str]: List of clean skill names
    """
    if not skills:
        return []
    
    formatted_skills = []
    for skill in skills:
        try:
            skill_name = safe_get_skill_name(skill)
            if skill_name and skill_name.strip():  # Skip empty skills
                formatted_skills.append(skill_name.strip())
        except Exception as e:
            # Log error but continue processing
            st.write(f"Warning: Could not process skill: {skill}")
            continue
    
    return formatted_skills

def display_skills_badges(skills: List[Union[str, Dict[str, Any]]], 
                         max_per_row: int = 4,
                         badge_style: str = "default") -> None:
    """
    Display skills as badges using native Streamlit components.
    
    Args:
        skills: List of skills in various formats
        max_per_row: Maximum number of skills per row
        badge_style: Style variant for badges (ignored in native version)
    """
    if not skills:
        st.info("No skills listed")
        return
    
    # Format skills safely
    formatted_skills = format_skills_list(skills)
    
    if not formatted_skills:
        st.info("No valid skills found")
        return
    
    # Create grid layout using native Streamlit formatting
    rows = [formatted_skills[i:i + max_per_row] for i in range(0, len(formatted_skills), max_per_row)]
    
    for row in rows:
        # Use code formatting for skills which is more reliable than HTML
        skill_badges = " ".join([f"`{skill}`" for skill in row])
        st.markdown(skill_badges)

def clean_display_text(text: Union[str, Dict[str, Any], List]) -> str:
    """
    Clean text for display, handling various data types that might be incorrectly formatted.
    
    Args:
        text: Text to clean, can be string, dict, or list
        
    Returns:
        str: Clean text for display with HTML sanitized
    """
    if isinstance(text, str):
        # Check if it looks like a dictionary or list string representation
        if text.startswith(("{'", '{"', '[{')):
            try:
                if text.startswith('['):
                    # It's a list of items
                    items = json.loads(text.replace("'", '"'))
                    if isinstance(items, list) and len(items) > 0:
                        if isinstance(items[0], dict):
                            # List of skill dictionaries
                            skill_names = [item.get('name', str(item)) for item in items]
                            return ", ".join([sanitize_html(name) for name in skill_names])
                        else:
                            # List of strings
                            return ", ".join([sanitize_html(str(item)) for item in items])
                else:
                    # It's a single dictionary
                    item = json.loads(text.replace("'", '"'))
                    if isinstance(item, dict):
                        skill_name = item.get('name', str(item))
                        return sanitize_html(skill_name)
            except (json.JSONDecodeError, ValueError):
                # If parsing fails, return the original string sanitized
                pass
        return sanitize_html(text)
    elif isinstance(text, dict):
        skill_name = text.get('name', text.get('skill_name', str(text)))
        return sanitize_html(skill_name)
    elif isinstance(text, list):
        cleaned_items = [clean_display_text(item) for item in text]
        return ", ".join(cleaned_items)
    else:
        return sanitize_html(str(text))

def extract_metrics_from_text(text: Union[str, List]) -> List[str]:
    """
    Extract metrics and quantifiable achievements from text.
    
    Args:
        text: Text to extract metrics from, can be string or list of strings
        
    Returns:
        List[str]: Extracted metrics
    """
    if not text:
        return []
        
    # Convert list to string if needed
    if isinstance(text, list):
        text = ' '.join(text)
        
    # Patterns to match common metrics formats
    patterns = [
        r'\d+%\s*(?:increase|decrease|improvement|reduction|growth|drop|ROI|higher|lower)',
        r'\$\d+(?:\.\d+)?(?:K|M|B)?\s*(?:revenue|sales|savings|cost|budget|investment)',
        r'(?:increased|decreased|reduced|improved|grew|cut)\s+\w+\s+by\s+\d+(?:\.\d+)?%',
        r'(?:team|group|department) of \d+(?:\+)? (?:people|employees|staff|members)',
        r'\d+(?:\+)? (?:clients|customers|users|accounts)',
        r'(?:saved|generated|produced|delivered)\s+\$\d+(?:\.\d+)?(?:K|M|B)?',
        r'\d+(?:\.\d+)?[xX] (?:improvement|increase|growth|faster|better)',
        r'(?:top|bottom) \d+%',
        r'\d+(?:\.\d+)?(?:K|M|B|T) (?:users|customers|revenue|sales)',
        r'(?:within|under) \d+ (?:days|weeks|months|quarters|years)',
        r'(?:over|more than) \d+(?:\.\d+)? (?:years|months)'
    ]
    
    metrics = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        metrics.extend(matches)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_metrics = []
    for m in metrics:
        if m not in seen:
            seen.add(m)
            unique_metrics.append(m)
    
    return unique_metrics

def fix_merged_text(text: str) -> str:
    """
    Fix common text merging issues in job descriptions and AI outputs.
    
    Args:
        text: Text to fix
        
    Returns:
        str: Fixed text
    """
    if not text or not isinstance(text, str):
        return text
        
    # Fix common merged patterns
    patterns = [
        # Revenue/financial patterns - more comprehensive
        (r'(\d+(?:\.\d+)?)Minrevenue', r'\1M in revenue'),
        (r'(\d+(?:\.\d+)?)Mrevenue', r'\1M revenue'),
        (r'(\d+(?:\.\d+)?)Kinrevenue', r'\1K in revenue'),
        (r'(\d+(?:\.\d+)?)millionrevenue', r'\1 million revenue'),
        (r'(\d+(?:\.\d+)?)EBITDA', r'\1 EBITDA'),
        (r'(\d+(?:\.\d+)?)Min', r'\1M in'),
        (r'revenueimpact', r'revenue impact'),
        (r'revenuethrough', r'revenue through'),
        
        # Action words that get merged - comprehensive list
        (r'Developedand', r'Developed and'),
        (r'Developand', r'Develop and'),
        (r'Buildand', r'Build and'),
        (r'Createand', r'Create and'),
        (r'Designand', r'Design and'),
        (r'Implementand', r'Implement and'),
        (r'Manageand', r'Manage and'),
        (r'Leadand', r'Lead and'),
        (r'Ledand', r'Led and'),
        (r'Executedand', r'Executed and'),
        (r'Optimizedand', r'Optimized and'),
        (r'Deliveredand', r'Delivered and'),
        (r'Collaboratedand', r'Collaborated and'),
        
        # Complex execution patterns
        (r'executeenterprise', r'execute enterprise'),
        (r'executehighly', r'execute highly'),
        (r'executeend-to-end', r'execute end-to-end'),
        (r'enterprise-levelsolutions', r'enterprise-level solutions'),
        (r'levelsolutions', r'level solutions'),
        (r'solutionsfor', r'solutions for'),
        
        # Agency and spend patterns
        (r'Reducedagencyspend', r'Reduced agency spend'),
        (r'reducedagency', r'reduced agency'),
        (r'agencyspend', r'agency spend'),
        (r'spendby', r'spend by'),
        
        # Impact and strategic patterns
        (r'impactthroughstrategic', r'impact through strategic'),
        (r'impactthrough', r'impact through'),
        (r'throughstrategic', r'through strategic'),
        (r'throughhighly', r'through highly'),
        (r'highlystrateg', r'highly strategic'),
        (r'strategichires', r'strategic hires'),
        (r'strategichiring', r'strategic hiring'),
        
        # Team and management patterns
        (r'Manageteam', r'Manage team'),
        (r'manageteam', r'manage team'),
        (r'teamof(\d+)', r'team of \1'),
        (r'teamof', r'team of'),
        (r'Ledteamof', r'Led team of'),
        (r'Ledteam', r'Led team'),
        (r'employeesand', r'employees and'),
        (r'andlead', r'and lead'),
        (r'lead(\d+)', r'lead \1'),
        
        # Project and process patterns
        (r'majorprojects', r'major projects'),
        (r'projectsover', r'projects over'),
        (r'overthe', r'over the'),
        (r'the(\d+)', r'the \1'),
        (r'yearperiod', r'year period'),
        (r'automatedprocesses', r'automated processes'),
        (r'processesto', r'processes to'),
        (r'todeliver', r'to deliver'),
        (r'deliverROI', r'deliver ROI'),
        (r'implementedautomated', r'implemented automated'),
        
        # Technology and tools
        (r'usingSQL', r'using SQL'),
        (r'withSQL', r'with SQL'),
        (r'SQLServer', r'SQL Server'),
        (r'PowerBI', r'Power BI'),
        (r'MachineLearning', r'Machine Learning'),
        (r'XGBoost', r'XGBoost'),
        (r'LightGBM', r'LightGBM'),
        
        # Common word merges
        (r'andexecute', r'and execute'),
        (r'andimplement', r'and implement'),
        (r'anddevelop', r'and develop'),
        (r'andcreate', r'and create'),
        (r'andmanage', r'and manage'),
        (r'andlead', r'and lead'),
        
        # Time-related merges
        (r'(\d+)years', r'\1 years'),
        (r'(\d+)months', r'\1 months'),
        (r'(\d+)weeks', r'\1 weeks'),
        
        # Percentage merges - more comprehensive
        (r'(\d+)%improvement', r'\1% improvement'),
        (r'(\d+)%increase', r'\1% increase'),
        (r'(\d+)%reduction', r'\1% reduction'),
        (r'by(\d+)%', r'by \1%'),
        (r'spendby(\d+)', r'spend by \1'),
        
        # Add spaces around slashes for better readability
        (r'(\w)/(\w)', r'\1 / \2'),
        
        # Fix capitalization issues - more aggressive
        (r'\b([a-z])([A-Z])', r'\1 \2'),  # camelCase to spaced words
        
        # Generic pattern for common merged words at word boundaries
        (r'([a-z])([A-Z][a-z])', r'\1 \2'),  # Better camelCase handling
    ]
    
    # Apply all patterns
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    
    # Normalize line endings to preserve paragraph/list structure
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Collapse runs of spaces/tabs but DO NOT collapse newlines
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Trim spaces around newlines
    text = re.sub(r'[ \t]*\n[ \t]*', '\n', text)
    
    # Limit excessive blank lines to a maximum of one empty line between blocks
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Final trim
    text = text.strip()
    
    return text






