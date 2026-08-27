# RecruitIQ API Documentation

## Table of Contents
- [Authentication](#authentication)
- [Base URL](#base-url)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Endpoints](#endpoints)
  - [Authentication](#authentication-endpoints)
  - [Candidates](#candidates-endpoints)
  - [Jobs](#jobs-endpoints)
  - [Matching](#matching-endpoints)
  - [Resume Parsing](#resume-parsing-endpoints)
  - [Analytics](#analytics-endpoints)

## Authentication

All API requests require authentication using a JWT token. Include the token in the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

### Getting an Access Token

```http
POST /api/v1/auth/token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=yourpassword
```

**Response**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## Base URL

All API endpoints are prefixed with `/api/v1`.

## Rate Limiting

- **Rate Limit**: 100 requests per minute per IP
- **Headers**:
  - `X-RateLimit-Limit`: Total allowed requests
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Time when limit resets (UTC epoch seconds)

## Error Handling

### Error Response Format
```json
{
  "detail": [
    {
      "loc": ["string"],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

### Common Status Codes
- `200 OK`: Request successful
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Endpoints

### Authentication

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

#### Refresh Token
```http
POST /api/v1/auth/refresh
Authorization: Bearer <refresh_token>
```

### Candidates

#### List Candidates
```http
GET /api/v1/candidates
```

**Query Parameters**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20)
- `status`: Filter by status
- `skills`: Comma-separated list of skills

#### Get Candidate
```http
GET /api/v1/candidates/{candidate_id}
```

#### Create Candidate
```http
POST /api/v1/candidates
Content-Type: multipart/form-data

{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "phone": "+1234567890",
  "resume": <file>,
  "source": "website"
}
```

### Jobs

#### List Jobs
```http
GET /api/v1/jobs
```

#### Create Job
```http
POST /api/v1/jobs
Content-Type: application/json

{
  "title": "Senior Software Engineer",
  "department": "Engineering",
  "location": "Remote",
  "type": "Full-time",
  "description": "Job description here...",
  "requirements": ["Python", "Docker", "AWS"],
  "min_salary": 120000,
  "max_salary": 160000,
  "status": "open"
}
```

### Matching

#### Match Candidates to Job
```http
GET /api/v1/matching/jobs/{job_id}/candidates
```

**Query Parameters**
- `limit`: Maximum number of matches (default: 10)
- `min_score`: Minimum match score (0-100)
- `skills_weight`: Weight for skills in matching (default: 0.5)
- `experience_weight`: Weight for experience (default: 0.3)
- `education_weight`: Weight for education (default: 0.2)

### Resume Parsing

RecruitIQ's resume parsing system uses Nebius AI (Phi-4) as the primary parsing engine with fallback to regex-based extraction. All endpoints support both synchronous and asynchronous processing.

### Parse Resume
```http
POST /api/v1/resumes/parse
Content-Type: multipart/form-data

{
  "file": <file>,
  "strategy": "comprehensive",  // 'fast' or 'comprehensive'
  "extract_skills": true,
  "extract_education": true,
  "extract_experience": true,
  "enhance_with_web": true,  // Enhance with web search
  "job_id": "optional-job-id"  // For job-specific parsing
}
```

**Response**
```json
{
  "success": true,
  "data": {
    "personal_info": {
      "name": "Jacob Smith",
      "email": "jacob.smith@email.com",
      "phone": "768-987-1029",
      "location": "Denver, CO",
      "linkedin": "www.linkedin.com/profile6",
      "website": null
    },
    "experience": [
      {
        "title": "Lead Product Data Scientist",
        "company": "Paypal",
        "start_date": "2023-07-01",
        "end_date": null,
        "location": "Remote",
        "description": "Led data science initiatives...",
        "currently_working": true
      }
    ],
    "education": [
      {
        "institution": "University of Montana",
        "degree": "Ph.D.",
        "field_of_study": "Physics",
        "start_year": "2010",
        "end_year": "2015"
      }
    ],
    "skills": {
      "technical": ["Python", "SQL", "Machine Learning"],
      "soft": ["Leadership", "Communication"],
      "certifications": ["AWS Certified", "PMP"]
    },
    "quality_assessment": {
      "clarity_score": 8,
      "impact_score": 7,
      "skills_relevance": 9,
      "overall_score": 8
    },
    "metadata": {
      "parser_version": "2.1.0",
      "processing_time_ms": 2450,
      "strategy_used": "comprehensive",
      "enhanced_with_web": true
    }
  }
}
```

### Batch Resume Parsing
```http
POST /api/v1/resumes/batch
Content-Type: application/json

{
  "file_urls": [
    "https://example.com/resumes/resume1.pdf",
    "https://example.com/resumes/resume2.docx"
  ],
  "strategy": "fast",
  "callback_url": "https://your-webhook.com/callback"
}
```

### Get Resume Analysis
```http
GET /api/v1/resumes/{resume_id}/analysis
```

### Parse Job Description
```http
POST /api/v1/jobs/parse
Content-Type: multipart/form-data

{
  "file": <file>,
  "enhance_with_web": true
}
```

### Analytics

#### Hiring Funnel
```http
GET /api/v1/analytics/hiring-funnel
```

**Query Parameters**
- `start_date`: Start date (ISO format)
- `end_date`: End date (ISO format)
- `department`: Filter by department
- """
}
```

## API Versioning

API versioning is handled through the URL path (`/api/v1/`). Breaking changes will result in a new version number.

## Webhooks

### Available Events
- `candidate.created`
- `candidate.updated`
- `job.created`
- `job.updated`
- `application.received`
- `application.status_changed`

### Webhook Payload Example
```json
{
  "event": "candidate.created",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "timestamp": "2025-08-28T18:45:30Z"
}
```

## SDKs

### Python
```python
from recruitiq import RecruitIQ

client = RecruitIQ(api_key="your_api_key")

# Get candidates
candidates = client.candidates.list()

# Parse resume
with open("resume.pdf", "rb") as f:
    result = client.resumes.parse(f)
```

### JavaScript
```javascript
const RecruitIQ = require('recruitiq-sdk');

const client = new RecruitIQ({ apiKey: 'your_api_key' });

// Create a job
client.jobs.create({
  title: 'Senior Developer',
  department: 'Engineering',
  // ...other fields
}).then(console.log);
```

## Changelog

### v2.1.0 (2025-08-28)
- Enhanced resume parsing with Nebius AI (Phi-4) integration
- Added batch processing support
- Improved job description parsing
- Added quality assessment metrics
- Web enhancement for candidate profiles

### v2.0.0 (2025-07-15)
- Refactored to ExtractThinker architecture
- Added contract-based validation
- Improved error handling and fallbacks
- Enhanced document processing pipeline

### v1.0.0 (2025-05-01)
- Initial API release
- Support for candidates, jobs, and matching
- Basic resume parsing
- Analytics endpoints

## Support

For API support, please contact api-support@recruitiq.com or visit our [developer portal](https://developers.recruitiq.com).

---
*Last Updated: August 2025*
