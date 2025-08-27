"""
RecruitIQ Text Formatting Utilities
====================================
This module provides text formatting functions to ensure consistent 
text presentation throughout the application UI.
"""

import re
from typing import Any, Dict, List, Union
import streamlit as st
from .ui_helpers import fix_merged_text, sanitize_html

def format_ui_text(text: Any) -> str:
    """
    Format text for UI display by applying multiple cleanup operations:
    1. Convert non-string types to strings
    2. Fix merged words and spacing issues
    3. Remove HTML tags
    4. Normalize whitespace
    
    Args:
        text: Any text to be displayed in the UI
        
    Returns:
        str: Cleaned and formatted text ready for UI display
    """
    if text is None:
        return ""
    
    # Convert to string
    if not isinstance(text, str):
        text = str(text)
    
    # Apply fix_merged_text to handle spacing issues
    text = fix_merged_text(text)
    
    # Apply HTML sanitization
    text = sanitize_html(text)
    
    # Remove double spaces and normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove "##" markdown header artifacts that might appear in text
    text = re.sub(r'##\s+', '', text)
    
    # Fix specific patterns we've seen in the UI
    text = re.sub(r'Benchmark:\s*##\s*', 'Benchmark: ', text)
    
    return text

def format_markdown_content(markdown_text: str) -> str:
    """
    Format markdown content to ensure proper spacing and structure.
    
    Args:
        markdown_text: Markdown text to format
        
    Returns:
        str: Properly formatted markdown text
    """
    if not markdown_text:
        return ""
    
    # Fix spacing issues while preserving markdown structure
    
    # Fix headers - ensure space after #
    markdown_text = re.sub(r'(#+)([^#\s])', r'\1 \2', markdown_text)
    
    # Fix list items - ensure space after markers
    markdown_text = re.sub(r'^([*+-])([^\s])', r'\1 \2', markdown_text, flags=re.MULTILINE)
    markdown_text = re.sub(r'^(\d+\.)([^\s])', r'\1 \2', markdown_text, flags=re.MULTILINE)
    
    # Fix merged text content but preserve markdown structure
    lines = markdown_text.split('\n')
    formatted_lines = []
    
    for line in lines:
        # Check if it's a header or list item
        if re.match(r'^#+\s', line) or re.match(r'^[*+-]\s', line) or re.match(r'^\d+\.\s', line):
            # Get the prefix (### or * or 1.)
            prefix_match = re.match(r'^(#+\s|[*+-]\s|\d+\.\s)', line)
            if prefix_match:
                prefix = prefix_match.group(0)
                content = line[len(prefix):]
                # Fix merged text in content only
                content = fix_merged_text(content)
                line = prefix + content
        else:
            # For regular text, fix merged text
            line = fix_merged_text(line)
        
        formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)

def format_salary(salary_value: Any) -> str:
    """
    Format salary values consistently.
    
    Args:
        salary_value: Salary value (can be string, int, float)
        
    Returns:
        str: Formatted salary string
    """
    if not salary_value:
        return ""
    
    # Convert to string if not already
    if not isinstance(salary_value, str):
        salary_str = str(salary_value)
    else:
        salary_str = salary_value
    
    # Clean up the salary string - remove extra characters but preserve numbers, $, K, M
    salary_str = re.sub(r'[^\d.$KkMm,\-]', '', salary_str)
    
    # Check if it already has K or M suffix
    if re.search(r'[KkMm]$', salary_str):
        return salary_str  # Return as-is, don't apply format_ui_text
    
    # Try to parse as float for formatting
    try:
        # Remove $ and commas if present for parsing
        parse_str = salary_str.replace('$', '').replace(',', '')
        salary_num = float(parse_str)
        
        # Format based on value
        if salary_num >= 1000000:
            return f"${salary_num/1000000:.1f}M"
        elif salary_num >= 1000:
            return f"${salary_num/1000:.0f}K"
        else:
            return f"${salary_num:,.0f}"
    except ValueError:
        # If parsing fails, return the original with basic cleanup but no format_ui_text
        return salary_str.strip()

def wrap_with_market_data_container(title: str, value: str, subtitle: str = "") -> str:
    """
    Wrap content in a market-data-container div with proper formatting.
    
    Args:
        title: Container title
        value: Main value to display
        subtitle: Optional subtitle
        
    Returns:
        str: HTML string with formatted container
    """
    # Format all text components
    title = format_ui_text(title)
    value = format_ui_text(value)
    subtitle = format_ui_text(subtitle) if subtitle else ""
    
    html = f"""
    <div class="market-data-container">
        <div class="market-data-title">{title}</div>
        <div class="market-data-value">{value}</div>
    """
    
    if subtitle:
        html += f'<div class="market-data-subtitle">{subtitle}</div>'
        
    html += "</div>"
    
    return html
