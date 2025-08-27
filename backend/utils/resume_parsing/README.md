# Resume Parser

A modular, robust resume parsing system for extracting structured information from resumes in various formats.

## Features

- **Multiple Document Formats**: Supports PDF, DOCX, TXT, and image formats with OCR fallback
- **Robust Extraction**: Multiple extraction strategies (NLP, Local Models, Regex) with automatic fallbacks
- **Modular Architecture**: Easy to extend with new document processors or extraction strategies
- **Parallel Processing**: Concurrent extraction for improved performance
- **Comprehensive Data Model**: Structured schema for all resume components

## Architecture

The resume parser follows a pipeline architecture:

1. **Document Processing**:
   - OCR Processing (extracts text with OCR fallback)
   - Markdown Processing (converts to structured markdown)
   - Section Processing (identifies and extracts sections)

2. **Information Extraction**:
   - NLP Extraction (spaCy-based named entity recognition)
   - Model Extraction (local ML models)
   - Regex Extraction (fallback pattern matching)

3. **Result Merging**:
   - Combines results from all extractors
   - Deduplicates entities
   - Validates and normalizes data

## Installation

### Prerequisites

- Python 3.8+
- Poetry (recommended) or pip

### Dependencies

The parser requires the following main dependencies:

- spaCy (with `en_core_web_lg` or `en_core_web_sm` model)
- PyPDF2
- pdfplumber
- python-docx
- pytesseract (optional, for OCR)
- EasyOCR (optional, for enhanced OCR)

Install using Poetry:

```bash
cd RecruitIQ
poetry install
```

For OCR support, additional installation steps may be required:

```bash
# For pytesseract
# Windows: Download and install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki

# For EasyOCR
poetry add easyocr
```

## Usage

### Basic Usage

```python
import asyncio
from backend.utils.resume_parsing import create_resume_parser

async def parse_resume(file_path):
    # Create parser with default configuration
    parser = create_resume_parser()
    
    # Parse the resume
    resume_data = await parser.parse(file_path)
    
    # Access structured data
    print(f"Name: {resume_data.personal_info.name}")
    print(f"Email: {resume_data.personal_info.email}")
    print(f"Experience: {len(resume_data.experience)} entries")
    print(f"Education: {len(resume_data.education)} entries")
    print(f"Skills: {len(resume_data.skills)} entries")
    
    return resume_data

# Run the async function
resume_data = asyncio.run(parse_resume("path/to/resume.pdf"))
```

### Using with CandidateAnalyzer

```python
import asyncio
from backend.utils.candidate_analyzer import CandidateAnalyzer

async def analyze_resume(file_path):
    # Create analyzer instance
    analyzer = CandidateAnalyzer()
    
    # Parse the resume
    resume_data = await analyzer.parse_resume(file_path)
    
    # Analyze the resume data
    analysis = analyzer.analyze_candidate(resume_data)
    
    print(f"AI Score: {analysis.get('ai_score')}")
    print(f"Recommendation: {analysis.get('recommendation')}")
    print(f"Skill Gaps: {analysis.get('skill_gaps')}")
    
    return resume_data, analysis

# Run the async function
resume_data, analysis = asyncio.run(analyze_resume("path/to/resume.pdf"))
```

### Advanced Configuration

You can customize the parser behavior by providing a configuration file:

```python
parser = create_resume_parser("path/to/config.json")
```

## Development and Extension

### Adding New Processors

1. Create a new class that inherits from `BaseProcessor`
2. Implement the `process` method
3. Register the processor in the `ResumeParser` class

### Adding New Extractors

1. Create a new class that inherits from `BaseExtractor`
2. Implement the `extract` method
3. Register the extractor in the `ResumeParser._initialize_extractors` method

## Testing

Run the tests with:

```bash
cd RecruitIQ
python -m unittest discover -s backend/utils/resume_parsing/tests
```
