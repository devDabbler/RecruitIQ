"""
Enhanced description extraction for resume parser.

This patch improves the description extraction quality for both experience and education entries
by using a more detailed extraction approach with the local model.
"""
import logging
import json
import re
import asyncio
import traceback
from typing import Dict, List, Any, Optional, Union

from backend.models.resume import Experience, Education
from backend.services.local_model_service import get_local_model_service
from backend.patches import robust_json_extractor

# Configure logging
logger = logging.getLogger(__name__)

async def extract_detailed_descriptions(text: str, entries: List[Dict[str, Any]], entry_type: str = "experience") -> List[Dict[str, Any]]:
    """
    Enhances existing entries with more detailed descriptions by using a focused extraction.
    
    Args:
        text: The full resume text
        entries: List of existing entries (experience or education) with basic info
        entry_type: Type of entries - "experience" or "education"
        
    Returns:
        Enhanced entries with detailed descriptions
    """
    if not entries or not text:
        logger.warning(f"No {entry_type} entries or text to enhance")
        return entries
        
    # Get local model service with error handling
    try:
        local_model_service = get_local_model_service()
        if not local_model_service:
            logger.warning("Local model service not available, using fallback extraction")
            return extract_descriptions_fallback(text, entries, entry_type)
    except Exception as e:
        logger.error(f"Error getting local model service: {str(e)}")
        return extract_descriptions_fallback(text, entries, entry_type)
        
    # Prepare entries for focused extraction
    try:
        entry_titles = [str(e.get('title', '')) for e in entries]
        entry_orgs = [str(e.get('company' if entry_type == 'experience' else 'institution', '')) for e in entries]
    except Exception as e:
        logger.error(f"Error preparing entries: {str(e)}")
        return entries
    
    # Build a focused, LLM-friendly prompt
    extraction_prompt = f"""You are an AI assistant specialized in extracting detailed descriptions from resumes.

I have already identified the following {entry_type} entries from this resume:

"""
    # Add the identified entries to the prompt
    for i, (title, org) in enumerate(zip(entry_titles, entry_orgs)):
        if title and org:
            extraction_prompt += f"{i+1}. {title} at {org}\n"
        elif title:
            extraction_prompt += f"{i+1}. {title}\n"
        elif org:
            extraction_prompt += f"{i+1}. Position at {org}\n"
    extraction_prompt += f"""

For EACH of these {entry_type} entries, extract the FULL and DETAILED description from the resume text. 
- Include ALL available text, bullet points, responsibilities, achievements, and specific information for each entry.
- DO NOT summarize, rephrase, or abbreviate. Copy EVERY relevant detail exactly as written in the resume.
- If the entry has no description in the resume, return an empty string for that entry.

Format your response as a JSON array where each object has:
  - 'index': The number of the entry (1, 2, 3, etc. as listed above)
  - 'description': The complete, detailed description for that entry (including all bullet points and text)

Example:
[
  {{"index": 1, "description": "Managed a team of 5 recruiters.\n- Led campus hiring.\n- Achieved 120% of targets in 2022."}},
  {{"index": 2, "description": "Oversaw onboarding process.\n- Implemented new ATS system.\n- Reduced time-to-hire by 30%."}}
]

RESUME TEXT:
"  # Escaped curly braces for JSON example
    extraction_prompt += text
{text}
"""

    # Execute the extraction with timeout protection
    logger.info(f"Extracting detailed descriptions for {len(entries)} {entry_type} entries")
    try:
        result = await asyncio.wait_for(
            local_model_service._generate_response(
                model_name='resume-parser-code',
                prompt=extraction_prompt, 
                temperature=0.2,
                max_tokens=3000
            ),
            timeout=30.0  # Increased timeout for detailed extraction
        )
            
        # Parse the response with better error handling
        try:
            # Clean and normalize the response
            cleaned_response = result.strip()
            
            # Use robust extractor for JSON parsing
            try:
                descriptions = robust_json_extractor.extract_json_robustly(
                    cleaned_response, default_result=None
                )
                if descriptions is None:
                    logger.warning(f"No valid JSON found in LLM response. Raw output (snippet): {cleaned_response[:200]}...")
                    raise json.JSONDecodeError("No valid JSON found", cleaned_response, 0)
                
                # Map descriptions back to original entries
                if descriptions and isinstance(descriptions, list):
                    enhanced_count = 0
                    for desc_item in descriptions:
                        try:
                            if not isinstance(desc_item, dict):
                                continue
                            
                            # Try different possible field names for index
                            index = None
                            for idx_field in ['index', 'id', 'entry']:
                                if idx_field in desc_item:
                                    index = desc_item[idx_field]
                                    break
                            
                            # If no index found, try to match by title/company
                            if index is None and 'title' in desc_item and 'company' in desc_item:
                                for i, entry in enumerate(entries):
                                    if (desc_item.get('title', '').lower() == entry.get('title', '').lower() and 
                                        desc_item.get('company', '').lower() == entry.get('company', entry.get('institution', '')).lower()):
                                        index = i + 1
                                        break
                            
                            # If still no index, try to match by position in the list
                            if index is None and len(descriptions) == len(entries):
                                index = descriptions.index(desc_item) + 1
                            
                            # Get the description text
                            description = ''
                            for desc_field in ['description', 'desc', 'details', 'responsibilities']:
                                if desc_field in desc_item:
                                    description = str(desc_item[desc_field]).strip()
                                    if description:
                                        break
                            
                            if not description:
                                continue
                                
                            # Update the entry
                            if isinstance(index, int) and 1 <= index <= len(entries):
                                entries[index-1]['description'] = description
                                enhanced_count += 1
                            elif isinstance(index, str) and index.isdigit() and 1 <= int(index) <= len(entries):
                                entries[int(index)-1]['description'] = description
                                enhanced_count += 1
                                
                        except Exception as e:
                            logger.warning(f"Error processing description item: {str(e)}")
                            continue
                    
                    if enhanced_count > 0:
                        logger.info(f"Successfully enhanced {enhanced_count} out of {len(entries)} {entry_type} entries")
                    else:
                        logger.warning(f"Failed to enhance any {entry_type} entries - no valid descriptions found")
                else:
                    logger.warning(f"No valid descriptions found in response for {entry_type} entries")
            except json.JSONDecodeError as je:
                logger.warning(f"Direct JSON parse failed, trying to extract structured data: {str(je)}")
                # Fall back to simpler extraction
                descriptions = []
                for i, entry in enumerate(entries):
                    # Look for a section that matches the entry title/company
                    title = entry.get('title', '').lower()
                    company = entry.get('company', entry.get('institution', '')).lower()
                    
                    # Create a pattern to find this entry's description
                    pattern = re.escape(title) + r'[^\n]*' + re.escape(company) + r'[^\n]*\n(.*?)(?=\n\s*\S+\s*\n|$)'
                    match = re.search(pattern, cleaned_response, re.IGNORECASE | re.DOTALL)
                    if match:
                        descriptions.append({
                            'index': i + 1,
                            'description': match.group(1).strip()
                        })
                
                # Process these extracted descriptions
                enhanced_count = 0
                for desc_item in descriptions:
                    try:
                        index = desc_item.get('index')
                        description = desc_item.get('description', '')
                        
                        if description and isinstance(index, int) and 1 <= index <= len(entries):
                            entries[index-1]['description'] = description
                            enhanced_count += 1
                    except Exception as e:
                        logger.warning(f"Error processing fallback description: {str(e)}")
                
                if enhanced_count > 0:
                    logger.info(f"Fallback method enhanced {enhanced_count} out of {len(entries)} {entry_type} entries")
                
        except Exception as e:
            logger.error(f"Error in description enhancement: {str(e)}")
            traceback.print_exc()
    except asyncio.TimeoutError:
        logger.error(f"Timeout while extracting detailed descriptions for {entry_type}")
    except Exception as e:
        logger.error(f"Extraction error: {str(e)}")
        
    return entries

def extract_descriptions_fallback(text: str, entries: List[Dict[str, Any]], entry_type: str = "experience") -> List[Dict[str, Any]]:
    """
    Fallback method to extract descriptions for experience or education entries using regex patterns.
    
    Args:
        text: The full resume text
        entries: List of existing entries with basic info
        entry_type: Type of entries - "experience" or "education"
        
    Returns:
        Enhanced entries with descriptions from regex extraction
    """
    logger.info(f"Using regex fallback to extract {entry_type} descriptions")
    if not entries or not text:
        return entries
    
    # Create improved entries with descriptions
    for i, entry in enumerate(entries):
        # Get the entry title and organization
        title = entry.get('title', '').strip()
        org = entry.get('company' if entry_type == 'experience' else 'institution', '').strip()
        
        if not title and not org:
            continue
        
        # Create patterns to find relevant sections for this entry
        search_patterns = []
        
        # Use title and org together
        if title and org:
            # Match pattern like "[Title] at [Organization]" with following text
            search_patterns.append(fr"(?:{re.escape(title)}\s+(?:at|with|for)\s+{re.escape(org)}|{re.escape(org)}\s+{re.escape(title)})(?:\s*:|\s*\n)([\s\S]{{20,500}})(?:\n\n|\n[A-Z])")
        
        # Use just the title
        if title:
            search_patterns.append(fr"{re.escape(title)}\s*(?::|\n)([\s\S]{{20,500}})(?:\n\n|\n[A-Z])")
        
        # Use just the organization
        if org:
            search_patterns.append(fr"{re.escape(org)}\s*(?::|\n)([\s\S]{{20,500}})(?:\n\n|\n[A-Z])")
        
        # Try each pattern
        description_found = False
        for pattern in search_patterns:
            try:
                matches = re.search(pattern, text, re.IGNORECASE)
                if matches and matches.group(1):
                    description = matches.group(1).strip()
                    if len(description) > 20:  # Ensure we got a meaningful description
                        entry['description'] = description
                        description_found = True
                        logger.info(f"Found {entry_type} description for {title} at {org} using regex")
                        break
            except Exception as e:
                logger.error(f"Error with regex pattern: {str(e)}")
        
        # If regex approach didn't work, try to extract bullet points near the title/org
        if not description_found:
            try:
                # Find a section of text that might contain the entry (within 500 chars of title/org mention)
                search_text = title if title else org
                position = text.lower().find(search_text.lower())
                
                if position >= 0:
                    # Extract text from this position onward (up to 2000 chars to include full section)
                    context = text[position:position + 2000]
                    
                    # Look for bullet points or numbered list items
                    bullet_pattern = r'(?:^|\n)\s*(?:•|\*|-|\d+\.)\s+(.+?)(?=\n\s*(?:•|\*|-|\d+\.)|\n\n|$)'
                    bullet_matches = re.finditer(bullet_pattern, context, re.MULTILINE)
                    
                    bullet_points = []
                    for match in bullet_matches:
                        point = match.group(1).strip()
                        if len(point) > 10:  # Ensure it's a meaningful point
                            bullet_points.append(point)
                    
                    # If we found bullet points, use them as description
                    if bullet_points:
                        entry['description'] = "\n• " + "\n• ".join(bullet_points)
                        description_found = True
                        logger.info(f"Extracted {len(bullet_points)} bullet points for {entry_type} entry")
            except Exception as bullet_err:
                logger.error(f"Error extracting bullet points: {str(bullet_err)}")
        
        # If still no description, add a placeholder
        if not description_found and not entry.get('description'):
            if entry_type == 'experience':
                entry['description'] = f"Role at {org if org else 'the organization'}. See original resume for complete details."
            else:  # education
                entry['description'] = f"Studies at {org if org else 'the institution'}. See original resume for complete details."
    
    return entries

def apply_description_extractor_fix():
    return # Effectively disable this patch
    """Apply the description extractor fix to enhance descriptions in resume parsing."""
    
    logger.info("Applying description extractor fix to resume parser")
    
    # Store original parse method
    # original_parse = ResumeParser.parse
    
    # Create enhanced parse method
    def enhanced_parse(self, file_path: str):
        """Enhanced parse method with better description extraction."""
        # First, use the original parse method to get basic resume data
        result = original_parse(self, file_path)
        
        if result:
            try:
                # Enhance experience descriptions
                if hasattr(result, 'experience') and result.experience:
                    # Convert Experience objects to dicts for processing
                    experience_dicts = [exp.dict() for exp in result.experience]
                    enhanced_exp_dicts = experience_dicts  # Default to original if enhancement fails
                    
                    # Fix: Create the coroutine but don't call it yet
                    coroutine_exp = extract_detailed_descriptions(
                        self.text, 
                        experience_dicts,
                        entry_type="experience"
                    )
                    
                    # Now properly run the async function
                    try:
                        # Use direct synchronous approach to avoid event loop issues
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        enhanced_exp_dicts = loop.run_until_complete(coroutine_exp)
                        loop.close()
                    except Exception as async_err:
                        logger.error(f"Error running experience description extraction: {str(async_err)}")
                        # If async approach fails, try to extract descriptions using regex
                        enhanced_exp_dicts = extract_descriptions_fallback(self.text, experience_dicts, "experience")
                        logger.info("Used fallback method for experience descriptions")
                          
                    # Convert back to Experience objects
                    if enhanced_exp_dicts:
                        result.experience = [Experience(**exp) for exp in enhanced_exp_dicts]
                        logger.info(f"Enhanced {len(result.experience)} experience descriptions")
                
                # Enhance education descriptions
                if hasattr(result, 'education') and result.education:
                    # Convert Education objects to dicts for processing
                    education_dicts = [edu.dict() for edu in result.education]
                    enhanced_edu_dicts = education_dicts  # Default to original if enhancement fails
                    
                    # Fix: Create the coroutine but don't call it yet
                    coroutine_edu = extract_detailed_descriptions(
                        self.text, 
                        education_dicts,
                        entry_type="education"
                    )
                    
                    # Now properly run the async function
                    try:
                        # Use direct synchronous approach to avoid event loop issues
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        enhanced_edu_dicts = loop.run_until_complete(coroutine_edu)
                        loop.close()
                    except Exception as async_err:
                        logger.error(f"Error running education description extraction: {str(async_err)}")
                        # If async approach fails, try to extract descriptions using regex
                        enhanced_edu_dicts = extract_descriptions_fallback(self.text, education_dicts, "education")
                        logger.info("Used fallback method for education descriptions")
                    
                    # Convert back to Education objects
                    if enhanced_edu_dicts:
                        result.education = [Education(**edu) for edu in enhanced_edu_dicts]
                        logger.info(f"Enhanced {len(result.education)} education descriptions")
                        
            except Exception as e:
                logger.error(f"Error enhancing descriptions in parse result: {str(e)}")
                
        return result
    
    # Apply the patched method
    # ResumeParser.parse = enhanced_parse
    
    logger.info("Description extractor fix applied successfully")

# Apply the fix
apply_description_extractor_fix()