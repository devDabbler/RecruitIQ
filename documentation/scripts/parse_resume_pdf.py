import httpx
import asyncio
import json
import os
import logging
import time
import sys
import PyPDF2
import io

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', 'config.json')
    default_config = {
        "ollama_endpoint": "http://localhost:11434/api/generate",
        "model": "resume-parser:latest",
        "timeout": 45.0,  # Reduced timeout to 45 seconds
        "temperature": 0.1,
        "max_tokens": 4000,
        "max_retries": 3,
        "retry_delay": 5.0,
        "chunk_size": 2000,  # Process resume in chunks of 2000 characters
        "overlap": 200  # Overlap between chunks to maintain context
    }
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            try:
                loaded_config = json.load(f)
                default_config.update(loaded_config)
                logging.info(f"Loaded configuration from {config_path}")
            except json.JSONDecodeError:
                logging.error(f"Error parsing config file {config_path}")
    else:
        logging.warning(f"Config file not found at {config_path}, using defaults")
        
    return default_config

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file"""
    logging.info(f"Extracting text from PDF: {pdf_path}")
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text() + "\n"
                
            logging.info(f"Successfully extracted {len(text)} characters from {len(reader.pages)} pages")
            return text
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {str(e)}")
        return None

async def test_ollama_connection(config):
    """Test if we can connect to the Ollama API endpoint"""
    # Extract base URL from the generate endpoint
    base_url = config["ollama_endpoint"].rsplit("/api/generate", 1)[0]
    version_url = f"{base_url}/api/version"
    
    logging.info(f"Testing connection to Ollama API at {version_url}")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(version_url)
            response.raise_for_status()
            version_info = response.json()
            logging.info(f"Successfully connected to Ollama API. Version: {version_info}")
            return True, version_info
    except Exception as e:
        logging.error(f"Failed to connect to Ollama API: {str(e)}")
        return False, str(e)

async def parse_resume_with_ollama(resume_text, config):
    """Parse a resume using the configured Ollama endpoint"""
    url = config["ollama_endpoint"]
    model = config["model"]
    timeout = config["timeout"]
    temperature = config["temperature"]
    max_tokens = config["max_tokens"]
    max_retries = config.get("max_retries", 3)
    retry_delay = config.get("retry_delay", 5.0)
    chunk_size = config.get("chunk_size", 2000)
    overlap = config.get("overlap", 200)
    
    logging.info(f"Using Ollama endpoint: {url}")
    logging.info(f"Using model: {model}")
    
    # Split resume into chunks if it's too long
    chunks = []
    if len(resume_text) > chunk_size:
        logging.info(f"Resume text length ({len(resume_text)}) exceeds chunk size ({chunk_size}), splitting into chunks")
        start = 0
        while start < len(resume_text):
            end = min(start + chunk_size, len(resume_text))
            # Try to find a good breaking point (newline or period)
            if end < len(resume_text):
                # Look for newline or period within overlap region
                break_point = resume_text.rfind('\n', end - overlap, end)
                if break_point == -1:
                    break_point = resume_text.rfind('. ', end - overlap, end)
                if break_point != -1:
                    end = break_point + 1
            chunks.append(resume_text[start:end])
            start = end - overlap if end < len(resume_text) else end
    else:
        chunks = [resume_text]
    
    logging.info(f"Split resume into {len(chunks)} chunks")
    
    # Create a more concise prompt
    prompt = """Extract resume information into JSON with this structure:
    {
        "personal_info": {"name": "", "email": "", "phone": "", "location": "", "linkedin": ""},
        "skills": [],
        "education": [{"degree": "", "institution": "", "date_range": "", "location": "", "field_of_study": ""}],
        "experience": [{"title": "", "company": "", "date_range": "", "location": "", "description": ""}],
        "certifications": [{"name": "", "institution": "", "date_range": ""}],
        "projects": [],
        "military_experience": [{"title": "", "company": "", "date_range": "", "location": "", "description": ""}],
        "summary": ""
    }
    
    Rules:
    1. For "Company | Location" format, split into company and location fields
    2. Include ALL job description details
    3. Don't repeat education as certifications
    4. Output ONLY valid JSON
    
    Resume:
    {resume_text}
    """.format(resume_text=resume_text)
    
    # Parameters for the request
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": temperature,
        "num_predict": max_tokens
    }
    
    logging.info(f"Sending request to Ollama server...")
    start_time = time.time()
    
    # Process each chunk
    results = []
    for i, chunk in enumerate(chunks):
        logging.info(f"Processing chunk {i+1}/{len(chunks)}")
        chunk_prompt = prompt.format(resume_text=chunk)
        payload["prompt"] = chunk_prompt
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    
                    response_json = response.json()
                    result = response_json.get("response", "")
                    
                    if not result:
                        logging.warning(f"Warning: Empty response received from Ollama (attempt {attempt + 1}/{max_retries})")
                        if "error" in response_json:
                            logging.error(f"Error from Ollama: {response_json['error']}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            continue
                        return None
                        
                    # Try to parse JSON
                    try:
                        parsed_json = json.loads(result)
                        results.append(parsed_json)
                        break  # Successfully parsed this chunk
                    except json.JSONDecodeError:
                        # Try to extract JSON using regex
                        import re
                        json_pattern = r'\{[\s\S]*\}'
                        match = re.search(json_pattern, result)
                        
                        if match:
                            try:
                                parsed_json = json.loads(match.group(0))
                                results.append(parsed_json)
                                break  # Successfully parsed this chunk
                            except json.JSONDecodeError:
                                pass
                        
                        logging.warning(f"Could not parse JSON from response (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            continue
                        return {"raw_text": result}
                        
            except httpx.TimeoutException:
                logging.warning(f"Request timed out after {timeout} seconds (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return None
            except Exception as e:
                logging.error(f"Error with Ollama request: {str(e)} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return None
    
    # Merge results from all chunks
    if not results:
        return None
        
    merged_result = results[0]  # Start with first chunk's result
    
    # Merge arrays from subsequent chunks
    for result in results[1:]:
        for key in ["skills", "education", "experience", "certifications", "projects", "military_experience"]:
            if key in result and isinstance(result[key], list):
                if key not in merged_result:
                    merged_result[key] = []
                # Add only unique items
                for item in result[key]:
                    if item not in merged_result[key]:
                        merged_result[key].append(item)
    
    elapsed = time.time() - start_time
    logging.info(f"Parsing completed in {elapsed:.2f} seconds")
    return merged_result

def post_process_resume_data(data):
    """Post-process the parsed resume data to fix common issues"""
    if not isinstance(data, dict):
        return data
    
    # Process experience entries to correctly separate company and location
    if "experience" in data and isinstance(data["experience"], list):
        for i, exp in enumerate(data["experience"]):
            # Handle company and location separation
            if "company" in exp and exp["company"] and "|" in exp["company"]:
                company_parts = exp["company"].split("|", 1)
                data["experience"][i]["company"] = company_parts[0].strip()
                
                # Only set location if it's not already set or is null
                if "location" not in exp or not exp["location"]:
                    data["experience"][i]["location"] = company_parts[1].strip()
            
            # Ensure job descriptions are properly formatted
            if "description" in exp and exp["description"]:
                # If description contains \r\n, ensure it's properly formatted
                if "\r\n" in exp["description"]:
                    # Split by \r\n and join with proper newlines
                    description_parts = exp["description"].split("\r\n")
                    # Filter out empty parts
                    description_parts = [part.strip() for part in description_parts if part.strip()]
                    # Join with newlines
                    data["experience"][i]["description"] = "\n".join(description_parts)
    
    # Process education entries to fix field_of_study
    if "education" in data and isinstance(data["education"], list):
        for i, edu in enumerate(data["education"]):
            # Check if degree contains field of study
            if "degree" in edu and edu["degree"]:
                if "," in edu["degree"]:
                    degree_parts = edu["degree"].split(",", 1)
                    data["education"][i]["degree"] = degree_parts[0].strip()
                    if "field_of_study" not in edu or not edu["field_of_study"]:
                        data["education"][i]["field_of_study"] = degree_parts[1].strip()
            
            # Check if institution contains date
            if "institution" in edu and edu["institution"] and "(" in edu["institution"] and ")" in edu["institution"]:
                # Extract date from institution field
                inst_parts = edu["institution"].split("(", 1)
                data["education"][i]["institution"] = inst_parts[0].strip()
                
                # Extract date if in parentheses
                if len(inst_parts) > 1 and ")" in inst_parts[1]:
                    date_str = inst_parts[1].split(")", 1)[0].strip()
                    if "date_range" not in edu or not edu["date_range"]:
                        data["education"][i]["date_range"] = date_str
    
    # Ensure certifications don't duplicate education entries
    if "certifications" in data and "education" in data:
        # Create a set of education entries to check against
        edu_set = set()
        for edu in data["education"]:
            if "degree" in edu and "institution" in edu:
                edu_set.add((edu.get("degree"), edu.get("institution")))
        
        # Filter out certifications that match education entries
        if isinstance(data["certifications"], list):
            filtered_certs = []
            for cert in data["certifications"]:
                if "name" in cert and "institution" in cert:
                    if (cert.get("name"), cert.get("institution")) not in edu_set:
                        filtered_certs.append(cert)
            data["certifications"] = filtered_certs
    
    return data

async def main():
    # Check if a PDF file was provided
    if len(sys.argv) < 2:
        print("Usage: python parse_resume_pdf.py <path_to_pdf>")
        return
        
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        return
    
    # Load configuration
    config = load_config()
    # Increase timeout for more detailed parsing
    config["timeout"] = 180.0  # 3 minutes timeout
    logging.info(f"Using Ollama endpoint: {config['ollama_endpoint']}")
    
    # Test connection to Ollama API
    connected, version_info = await test_ollama_connection(config)
    
    if not connected:
        logging.error("Failed to connect to Ollama API. Please check your configuration and network.")
        return
    
    # Extract text from PDF
    resume_text = extract_text_from_pdf(pdf_path)
    if not resume_text:
        print("Failed to extract text from PDF. Check logs for details.")
        return
    
    # Test resume parsing
    logging.info("Parsing resume...")
    result = await parse_resume_with_ollama(resume_text, config)
    
    if result:
        if isinstance(result, dict) and "raw_text" not in result:
            # Post-process the result to fix common issues
            result = post_process_resume_data(result)
            
            print("\nParsed Result:")
            print(json.dumps(result, indent=2))
            
            # Save result to a JSON file
            output_path = os.path.splitext(pdf_path)[0] + "_parsed.json"
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\nParsed result saved to: {output_path}")
        else:
            print("\nRaw Result (JSON parsing failed):")
            if isinstance(result, dict) and "raw_text" in result:
                print(result["raw_text"])
            else:
                print(result)
    else:
        print("\nFailed to parse resume. Check logs for details.")

if __name__ == "__main__":
    asyncio.run(main())
