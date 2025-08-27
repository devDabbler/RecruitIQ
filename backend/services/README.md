# Resume Parsing and AI Assistant Services

This directory contains the new services for resume parsing and AI-powered job analysis.

## Components

### ResumeService (`resume_service_new.py`)

A service that wraps the resume parsing functionality with the following features:

- Uses Nebius AI parser as the primary parsing method
- Falls back to NLP extractor if Nebius AI fails
- Implements caching for improved performance (24-hour cache)
- Handles error cases gracefully

### AIAssistant (`ai_assistant.py`)

An AI assistant service that analyzes resumes against job descriptions:

- Parses resumes using the ResumeService
- Performs job matching analysis
- Calculates match scores between resumes and job descriptions

### Cache Utilities (`utils/cache/`)

Caching utilities for performance optimization:

- `@cache_result` decorator for caching function results
- Configurable cache expiry times

### Logging Utilities (`utils/logging.py`)

Logging utilities for error tracking and debugging:

- `log_parsing_errors` function for consistent error logging
- Context-aware error reporting

## API Endpoints

### Resume Analysis (`api/routes/resume.py`)

- `POST /analyze-resume` - Analyze a resume against a job description

## Dependencies

The following dependencies were added to `pyproject.toml`:

- `python-memcached` - For caching functionality

## Testing

Unit tests have been added for all new components:

- `tests/test_resume_service.py`
- `tests/test_ai_assistant.py`
- `tests/test_cache_utils.py`
- `tests/test_logging.py`

## Usage

### Parsing a Resume

```python
from backend.services.resume_service_new import ResumeService

service = ResumeService()
result = await service.parse_resume("Sample resume text")
```

### Analyzing a Resume for a Job

```python
from backend.services.ai_assistant import AIAssistant

assistant = AIAssistant()
result = await assistant.analyze_resume_for_job(
    "Sample resume text", 
    "Job description text"
)
```

### Using the Cache Decorator

```python
from backend.utils.cache.cache_utils import cache_result

@cache_result(expiry=3600)
async def expensive_function(param: str):
    # Expensive operation here
    return result
```

### Logging Errors

```python
from backend.utils.logging import log_parsing_errors

try:
    # Resume parsing operation
    pass
except Exception as e:
    log_parsing_errors(e, resume_text, metadata)
```
