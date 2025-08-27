"""
Simplified script to analyze education extraction from John Doe's resume.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimplePDFLoader:
    """Simple PDF loader that uses PyPDF2."""
    
    def __init__(self):
        try:
            import PyPDF2
            self.PyPDF2 = PyPDF2
        except ImportError:
            logger.error("PyPDF2 is not installed. Please install it with 'pip install PyPDF2'")
            sys.exit(1)
    
    def load_pdf(self, file_path):
        """Load a PDF file."""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = self.PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    text += pdf_reader.pages[page_num].extract_text()
            return text
        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
            return ""

async def call_nebius_api(text, prompt):
    """Call Nebius AI API."""
    from backend.services.nebius_ai_service import get_nebius_ai_service
    
    try:
        nebius_service = get_nebius_ai_service()
        response = await nebius_service.generate_text(prompt, max_tokens=8192, temperature=0.1)
        return response
    except Exception as e:
        logger.error(f"Error calling Nebius API: {e}")
        return None

def create_education_extraction_prompt(text):
    """Create a prompt specifically for education extraction."""
    prompt = f"""You are an expert resume parser. Analyze the following resume text and extract ONLY the education information in a structured JSON format.

**EDUCATION EXTRACTION REQUIREMENTS:**
- Always extract COMPLETE education information including institution, degree type, and field of study
- Look for degree types like: B.S., B.A., Bachelor of Science, Master of Arts, M.S., PhD, etc.
- Look for degree fields like: Computer Science, Business Administration, Engineering, etc.
- Common degree patterns: "Bachelor of Science in Computer Science", "B.S. in Computer Science", "Master's in Business Administration"
- If only institution is explicitly mentioned but degree can be inferred from context, include the degree
- Parse the entire resume for education info, not just dedicated education sections
- Education dates should be extracted when available
- If a degree is specified but missing its type, use the field of study to infer a likely degree type

**Expected JSON Format:**
```json
[
  {{
    "institution": "University Name",
    "degree": "Degree Type (e.g., Bachelor of Science, Master's, etc.)",
    "field_of_study": "Field of Study (e.g., Computer Science, Engineering, etc.)",
    "start_date": "Start Date (if available)",
    "end_date": "End Date (if available)"
  }},
  // Additional education entries...
]
```

**Resume Text:**
```text
{text}
```

Your response must be a single, valid JSON array as described above. Do not include any explanatory text or markdown formatting around the JSON.

**REMEMBER:** Extract ALL education details, especially institution name, degree type, and field of study.
"""
    return prompt

async def extract_text_from_pdf(pdf_path):
    """Extract text from PDF."""
    loader = SimplePDFLoader()
    text = loader.load_pdf(pdf_path)
    return text

async def main():
    """Main function."""
    if len(sys.argv) != 2:
        logger.error("Usage: python debug_education_extraction.py <path/to/resume.pdf>")
        return 1
    
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        logger.error(f"File does not exist: {pdf_path}")
        return 1
    
    logger.info(f"Analyzing education extraction from: {pdf_path}")
    
    # Extract text from PDF
    text = await extract_text_from_pdf(pdf_path)
    if not text:
        logger.error("Failed to extract text from PDF")
        return 1
    
    logger.info(f"Successfully extracted {len(text)} characters of text from PDF")
    
    # Print the first 500 characters to see what we're working with
    logger.info(f"First 500 characters of text:\n{text[:500]}...")
    
    # Create education extraction prompt
    prompt = create_education_extraction_prompt(text)
    
    # Call Nebius API
    logger.info("Calling Nebius API for education extraction...")
    response = await call_nebius_api(text, prompt)
    
    if not response:
        logger.error("Failed to get response from Nebius API")
        return 1
    
    logger.info(f"Raw API response:\n{response}")
    
    # Try to parse the response as JSON
    try:
        # Clean the response by stripping markdown and leading/trailing whitespace
        cleaned_text = response.strip()
        if cleaned_text.startswith('```json'):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.endswith('```'):
            cleaned_text = cleaned_text[:-3]
        
        cleaned_text = cleaned_text.strip()
        
        education_data = json.loads(cleaned_text)
        logger.info(f"Parsed education data:\n{json.dumps(education_data, indent=2)}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse response as JSON: {e}")
        return 1
    
    logger.info("Analysis completed successfully")
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
