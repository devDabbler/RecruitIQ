# RecruitIQ

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Documentation Status](https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat)](./docs/README.md)

RecruitIQ is an AI-powered recruiting platform that helps teams quickly screen resumes, match candidates to live roles, and surface insights from existing talent pools.

## Features

- **Candidate Management** - Track candidates through the recruitment pipeline
- **Resume Parsing** - Automatically extract key information from resumes
- **Job Management** - Create and manage job postings
- **AI Matching** - Match candidates to jobs using semantic search and embeddings
- **AI Assistant** - Get help with job descriptions, interview questions and more
- **Market Intelligence** - Analyze job market trends and salary data
- **Communication Tools** - Manage candidate communications and templates

## Value Proposition

- **Frustrated with your ATS?**
- **Have a database of valuable resumes and applications trapped in your ATS—candidates who could be hired now if you only knew about them?**
- **Does your current search tool waste your time surfacing unqualified or previously rejected candidates?**

RecruitIQ unlocks the value of your existing talent pool—no migration required. Whether you switch platforms or stay with your current ATS, our solution delivers actionable insights and ROI from day one.

## Feature Flags & Subscription Tiers

RecruitIQ supports feature flag controls to enable or restrict features based on the user's subscription tier (e.g., `basic` vs `premium`).

- The frontend uses a `user_tier` value in Streamlit's `st.session_state` to control access to premium features.
- By default, this is set to `basic`. Change to `premium` for testing premium features:

```python
st.session_state.user_tier = "premium"
```

- Each panel/component checks the user tier and:
  - Hides or greys out premium features for basic users
  - Shows an upgrade prompt/button for features requiring a higher tier
  - See inline TODOs in the code for where to integrate real user profile/tier logic from backend

## Backend Integration (Panels)

- **Jobs/Candidates**: Fully wired to backend APIs (async fetch pattern)
- **Interviews/Tasks/Notifications**: Use demo data by default. Async fetch placeholders and TODOs are present for easy backend integration when endpoints are ready.
- All panels include error handling, loading states, and fallback logic for backend downtime.

## Technical Overview

RecruitIQ consists of:

1. **Frontend** - A Streamlit-based web interface
2. **Backend API** - A FastAPI application providing RESTful endpoints
3. **Database** - SQLAlchemy with PostgreSQL for data storage
4. **AI Services** - Language models for resume parsing, embeddings, and assistant features
5. **Vector Database** - Neo4j for storing and querying vector embeddings
6. **Storage** - MinIO for document storage

## Recruiting Database Transformation Service

RecruitIQ offers a comprehensive service to transform legacy recruiting databases into AI-powered talent intelligence platforms. This service leverages advanced RAG (Retrieval-Augmented Generation), semantic search, and data enrichment to unlock actionable insights from existing candidate data.

### Key Strengths
- **Advanced Candidate-Job Matching**: Sophisticated algorithms using skills, experience, and vector-based semantic search (Neo4j).
- **RAG Implementation**: Specialized vector stores, context compression, and query classification for relevant, routed results.
- **Comprehensive Dashboard**: Multi-module frontend, AI assistant, resume parsing, and data extraction.

### Service Phases
1. **Assessment & Audit**: Analyze the client’s ATS/database, identify data quality gaps, and estimate ROI. _Deliverable: Data Transformation Roadmap._
2. **Data Transformation Service**: Connect to databases, parse/normalize resumes, extract entities/skills, and generate embeddings. _Deliverable: Enriched, AI-ready candidate database._
3. **Platform License**: SaaS offering with tiered pricing, optional add-on modules, and recurring revenue model.

### Add-on Modules
- **Advanced Matching Engine**: Skill gap analysis, culture fit, experience level matching, and explainable job-candidate matching.
- **Market Intelligence Suite**: Salary benchmarking, competitive analysis, hiring timeline estimation, skill demand forecasting.
- **AI Recruiting Assistant**: Candidate summarization, chat-based insights, and automated recruiter workflows.

### Pricing Model
- **Data Transformation Service**: One-time fee based on database size/complexity.
- **Platform License**: Recurring fee based on features and database size.

## Enhanced Resume Parsing & Matching System

RecruitIQ features a newly enhanced hybrid resume processing system that combines locally trained models with optional API-based matching capabilities.

### Key Enhancements

#### 1. Hybrid Architecture

- **Local Resume Parsing**: Uses a locally trained model for all resume parsing (data privacy, speed, reliability)
- **Optional API-Based Matching**: Can use external APIs for advanced matching while integrating local model data
- **Smart Fallback**: Automatically falls back to local matching if API calls fail

#### 2. Parser Improvements

- **Enhanced Pattern Recognition**: Integrated 11,449 patterns from training data for improved section detection
- **Education Extraction Improvements**:
  - Fixed date formatting to convert datetime objects to properly formatted strings
  - Improved degree and institution extraction
- **Experience Description Completeness**: Increased character limit from 400-500 to 1000 characters for more comprehensive job descriptions
- **Military Experience Detection**: Added better patterns for military service recognition and extraction

#### 3. Component Separation

- **EnhancedResumeParser**: Focused solely on accurate data extraction
- **CandidateAnalyzer**: Handles all AI-powered analysis and job matching
- **Clear API Boundaries**: Well-defined interfaces between components

#### 4. Database Integration

- **PostgreSQL** (`ats_db`): Stores parsed resume data and job information
- **Neo4j** (`neograph`): Powers graph-based skill relationships and semantic search

### Using the System

```python
# Basic parsing and matching
from backend.utils.enhanced_resume_parser import EnhancedResumeParser
from backend.utils.candidate_analyzer import CandidateAnalyzer

# Initialize components
parser = EnhancedResumeParser()
analyzer = CandidateAnalyzer(use_api=False)  # Local-only mode

# Parse a resume
resume_data = parser.parse_resume("path/to/resume.pdf")

# Match to a job
job_data = {
    'title': 'Software Engineer',
    'required_skills': ['Python', 'SQL', 'JavaScript'],
    'preferred_skills': ['AWS', 'Docker'],
    'min_years_experience': 3
}

match_results = analyzer.match_to_job(resume_data, job_data)
```

For full documentation, see `README-HYBRID-SYSTEM.md`.

## Requirements

- Python 3.9+
- Poetry (for dependency management)
- PostgreSQL
- MinIO (optional)
- Redis (optional)
- Neo4j (optional)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/RecruitIQ.git
cd RecruitIQ
```

2. Install dependencies:
```bash
poetry install
```

3. Set up environment variables (create a `.env` file):
```
DATABASE_URL=postgresql://user:password@localhost/recruitiq
API_VERSION=v1
ENABLE_SWAGGER=true
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j
```

## Running the Application

### Option 1: Run both frontend and backend with a single command

```bash
poetry run python run.py
```

### Option 2: Run each component separately

Run the backend server:
```bash
poetry run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Run the frontend:
```bash
poetry run streamlit run frontend/app.py
```

Then open your browser to http://localhost:8501

## API Documentation

When the backend server is running, API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

### Project Structure

```
RecruitIQ/
├── backend/                   # Backend API
│   ├── models/                # Database and data models
│   ├── routers/               # API routes
│   ├── services/              # Business logic (intent detection, web search, LLM, crawling, storage, etc.)
│   │   ├── intent_processor.py        # Intent detection and processing for chatbot
│   │   ├── web_search_service.py      # Web search integration for dynamic queries
│   │   ├── job_service.py             # Job service for embedding generation and storage
│   │   ├── resume_service.py          # Resume service for parsing and embedding generation
│   │   ├── graph_service.py           # Neo4j integration for vector storage and search
│   │   ├── rag_service.py             # Retrieval-augmented generation for semantic search
│   ├── utils/                 # Utility functions
│   ├── scripts/               # Helper scripts
│   └── main.py                # Application entry point
├── frontend/                  # Streamlit frontend
│   ├── modules/               # Frontend page modules
│   ├── components/            # Reusable UI components
│   ├── static/                # Static assets
│   └── app.py                 # Frontend entry point
├── data/                      # Sample data and fixtures
├── docs/                      # Documentation
├── tests/                     # Tests
├── run.py                     # Script to run the full application
└── pyproject.toml            # Project dependencies
```

## Testing

Run tests with:
```bash
poetry run pytest
```

## License

[MIT License](LICENSE)