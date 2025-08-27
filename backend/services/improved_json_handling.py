"""
Improved JSON handling for LLM responses.
This module provides enhanced functionality for extracting and repairing JSON from LLM outputs.
"""
import json
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def extract_json_from_llm_response(response_text: str) -> Dict[str, Any]:
    """
    Extract JSON from LLM response text with extensive cleanup and repair.
    
    Args:
        response_text: Text response from the model
        
    Returns:
        Dict extracted from JSON in response
    """
    # Log the response we're trying to parse (truncated)
    logger.info(f"Attempting to extract JSON from response (truncated): {response_text[:200]}...")
    
    # Remove any markdown code block markers and leading/trailing whitespace
    response_text = response_text.strip()
    
    # Try to clean up code blocks first
    if "```json" in response_text:
        # Extract content from code blocks
        code_block_pattern = r'```(?:json\s*)?([\s\S]*?)```'
        code_blocks = re.findall(code_block_pattern, response_text)
        if code_blocks:
            # Use the longest code block
            code_blocks.sort(key=len, reverse=True)
            response_text = code_blocks[0].strip()
            logger.info(f"Extracted from code block: {response_text[:100]}...")
    
    # If the response starts with 'Here is the output in valid JSON format:' or similar, remove it
    response_text = re.sub(r'^[^{\[]*', '', response_text, flags=re.DOTALL).strip()
    
    # If we have multiple JSON objects, try to find the most complete one
    if response_text.count('{') > 1:
        # Find all JSON objects
        json_objects = []
        stack = []
        start_index = 0
        
        for i, char in enumerate(response_text):
            if char == '{':
                if not stack:
                    start_index = i
                stack.append(char)
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack:  # Found a complete object
                        json_objects.append(response_text[start_index:i+1])
        
        if json_objects:
            # Sort by length (longest first) and use the most complete one
            json_objects.sort(key=len, reverse=True)
            response_text = json_objects[0]
            logger.info(f"Extracted most complete JSON object: {response_text[:100]}...")
    
    # Try to find JSON pattern in the response
    try:
        # Find a JSON object pattern (start and end braces with content in between)
        # This pattern is more permissive to handle malformed JSON
        json_pattern = r'\{(?:[^{}\[\]]|\[.*?\]|".*?(?<!\\)")*\}'
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        
        if matches:
            # Start with the longest match which is likely the complete JSON
            matches.sort(key=len, reverse=True)
            json_text = matches[0]
            
            # Initial cleanup
            json_text = (
                json_text
                .replace('\\"', '"')  # Fix escaped quotes
                .replace('\\n', '\n')  # Fix escaped newlines
                .replace('\t', ' ')     # Replace tabs with spaces
                .replace('\n', ' ')     # Replace newlines with spaces
                .replace('\r', '')      # Remove carriage returns
                .strip()
            )
            
            # Fix common JSON issues
            json_text = re.sub(r',\s*([}\]])', r'\1', json_text)  # Remove trailing commas
            json_text = re.sub(r'([{\[,])\s*([}\],])', r'\1\2', json_text)  # Fix empty objects/arrays
            
            # Fix unquoted keys
            json_text = re.sub(r'([{,]\s*)(\w+)(\s*:)'
                             , lambda m: f"{m.group(1)}\"{m.group(2).strip()}\"{m.group(3)}"
                             , json_text)
            
            # Fix single quotes
            json_text = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', json_text)  # Keys
            json_text = re.sub(r'"""([^\"]*?)"""', r'"\1"', json_text)  # Triple quotes
            
            # Fix unescaped quotes in values
            json_text = re.sub(r'([:{\[,]\s*)"([^"]*?)([^\\])"([,}\\]]|$)'
                             , lambda m: f"{m.group(1)}\"" + m.group(2).replace('"', '\\\\"') + f'"{m.group(4)}'
                             , json_text)
            
            logger.debug(f"Cleaned JSON text: {json_text}")
            
            try:
                # Try parsing the cleaned JSON
                parsed_data = json.loads(json_text)
                logger.info("Successfully parsed JSON from response")
                return parsed_data
            except json.JSONDecodeError:
                # Move to more aggressive cleaning methods
                pass
        
        # If we couldn't parse the JSON or didn't find a valid pattern,
        # try more aggressive methods
        
        # Method 1: Try to extract from opening to closing brace
        logger.info("Trying basic JSON extraction...")
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        
        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            
            # Basic cleaning
            json_text = (
                json_text
                .replace('\\"', '"')
                .replace('\\n', '\n')
                .replace('\t', ' ')
            )
            
            try:
                parsed_data = json.loads(json_text)
                logger.info("Successfully parsed JSON with basic extraction")
                return parsed_data
            except:
                logger.info("Basic extraction failed, trying additional cleanup...")
        
        # Method 2: Fix common JSON syntax errors
        logger.info("Applying syntax fixes to extracted JSON...")
        
        # Get the potential JSON text again (might be modified in the previous steps)
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        
        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            
            # More aggressive cleaning
            # 1. Fix unquoted keys
            json_text = re.sub(r'([{,])\s*(\w+)\s*:', r'\1"\2":', json_text)
            
            # 2. Fix single quotes used instead of double quotes
            json_text = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', json_text)
            
            # 3. Fix trailing commas in arrays
            json_text = re.sub(r',\s*\]', ']', json_text)
            
            # 4. Fix trailing commas in objects
            json_text = re.sub(r',\s*\}', '}', json_text)
            
            # 5. Ensure proper array formatting
            json_text = re.sub(r'\[\s*,', '[', json_text)
            
            try:
                parsed_data = json.loads(json_text)
                logger.info("Successfully parsed JSON after syntax fixes")
                return parsed_data
            except json.JSONDecodeError as e:
                # If we still can't parse it, log the error and move to fallback
                logger.warning(f"JSON syntax fixing failed: {str(e)}")
        
        # Method 3: Reconstruct a minimal valid JSON with the fields we can extract
        logger.info("Trying to reconstruct valid JSON from fragments...")
        
        # Try to extract keys and values with regex patterns
        key_value_pattern = r'"(\w+)"\s*:\s*(?:"([^"]*)"|([\\d\\.]+)|\[(.*?)\]|\{(.*?)\}|(true|false|null))'
        key_values = re.findall(key_value_pattern, response_text)
        
        if key_values:
            reconstructed = {}
            
            for match in key_values:
                key = match[0]
                # Find the first non-empty value group
                value = next((v for v in match[1:] if v), "")
                
                # Try to convert to appropriate type
                if value.lower() == 'true':
                    reconstructed[key] = True
                elif value.lower() == 'false':
                    reconstructed[key] = False
                elif value.lower() == 'null':
                    reconstructed[key] = None
                else:
                    try:
                        # Try to convert to number if it looks like one
                        if re.match(r'^-?\d+(\.\d+)?$', value):
                            if '.' in value:
                                reconstructed[key] = float(value)
                            else:
                                reconstructed[key] = int(value)
                        else:
                            reconstructed[key] = value
                    except:
                        reconstructed[key] = value
            
            logger.info(f"Reconstructed a JSON object with {len(reconstructed)} keys")
            return reconstructed
        
        # If we get here, all methods failed
        logger.warning("All JSON extraction methods failed")
        
        # Last resort: Construct a minimal default response
        return create_default_resume_response(response_text)
        
    except Exception as e:
        logger.error(f"Unexpected error extracting JSON: {str(e)}\n{traceback.format_exc()}")
        logger.error(f"Problematic response text: {response_text[:500]}...")
        return create_default_resume_response(response_text)

def create_default_resume_response(response_text: str) -> Dict[str, Any]:
    """Create a minimal default response when JSON extraction fails."""
    try:
        # Try to extract name and email with regex
        name_pattern = r'name[\"\':\s]+(.*?)[\"\',\n}]'
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        name_match = re.search(name_pattern, response_text, re.IGNORECASE)
        email_match = re.search(email_pattern, response_text)
        
        # Create a basic response structure
        response = {
            "personal_info": {
                "name": name_match.group(1).strip() if name_match else "",
                "email": email_match.group(0) if email_match else ""
            },
            "skills": [],
            "education": [],
            "experience": []
        }
        
        logger.info("Created default response structure")
        return response
    except Exception as e:
        logger.error(f"Error creating default response: {str(e)}")
        # Return an empty but valid structure
        return {
            "personal_info": {},
            "skills": [],
            "education": [],
            "experience": []
        }
