# RecruitIQ Developer Guide

## Table of Contents
- [Development Environment Setup](#development-environment-setup)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development)
  - [Testing](#testing)
- [Code Organization](#code-organization)
  - [Frontend Structure](#frontend-structure)
  - [Backend Structure](#backend-structure)
  - [Shared Libraries](#shared-libraries)
- [Development Workflow](#development-workflow)
  - [Branching Strategy](#branching-strategy)
  - [Code Reviews](#code-reviews)
  - [Versioning](#versioning)
- [API Development](#api-development)
  - [REST API Guidelines](#rest-api-guidelines)
  - [Authentication](#authentication)
  - [Error Handling](#error-handling)
- [Testing Strategy](#testing-strategy)
  - [Unit Tests](#unit-tests)
  - [Integration Tests](#integration-tests)
  - [E2E Tests](#e2e-tests)
- [Performance Considerations](#performance-considerations)
- [Security Best Practices](#security-best-practices)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Development Environment Setup

### Prerequisites

- Python 3.9+
- Node.js 16+
- PostgreSQL 13+
- Redis 6+
- Poetry (Python package manager)
- Docker (optional, for containerized development)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/RecruitIQ.git
   cd RecruitIQ
   ```

2. **Set up Python environment**
   ```bash
   # Install Poetry if not already installed
   curl -sSL https://install.python-poetry.org | python3 -
   
   # Install dependencies
   poetry install
   
   # Activate the virtual environment
   poetry shell
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

4. **Set up databases**
   ```bash
   # Start PostgreSQL and Redis
   docker-compose up -d postgres redis
   
   # Run migrations
   alembic upgrade head
   ```

5. **Start development servers**
   ```bash
   # Backend (FastAPI)
   uvicorn backend.main:app --reload
   
   # Frontend (Streamlit)
   streamlit run frontend/app.py
   ```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_module.py

# Run with coverage report
pytest --cov=backend tests/
```

## Code Organization

### Frontend Structure
```
frontend/
├── components/     # Reusable UI components
├── pages/         # Page components
├── services/      # API clients and services
├── store/         # State management
├── styles/        # Global styles and themes
└── utils/         # Utility functions
```

### Backend Structure
```
backend/
├── api/           # API routes
├── core/          # Core application logic
├── models/        # Database models
├── schemas/       # Pydantic models
├── services/      # Business logic
├── tasks/         # Background tasks
└── utils/         # Utility functions
```

### Shared Libraries
- **resume_parser**: Resume parsing functionality
- **matching_engine**: Candidate-job matching logic
- **ai_services**: AI/ML model integrations

## Development Workflow

### Branching Strategy

We follow GitFlow:
- `main`: Production releases
- `develop`: Integration branch
- `feature/*`: New features
- `bugfix/*`: Bug fixes
- `release/*`: Release preparation

### Code Reviews

1. Create a pull request from your feature branch to `develop`
2. Request reviews from at least one team member
3. Address all comments
4. Squash and merge when approved

### Versioning

We use [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: Backwards-compatible features
- PATCH: Backwards-compatible bug fixes

## API Development

### REST API Guidelines

- Use nouns in plural form for resources (`/candidates`, `/jobs`)
- Use HTTP methods appropriately:
  - `GET`: Retrieve resources
  - `POST`: Create resources
  - `PUT`: Replace resources
  - `PATCH`: Update resources partially
  - `DELETE`: Remove resources

### Authentication

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = await get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
```

### Error Handling

```python
from fastapi import HTTPException

async def get_item(item_id: str):
    item = await get_item_from_db(item_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
            headers={"X-Error": "Item not found"},
        )
    return item
```

## Testing Strategy

### Unit Tests
- Test individual functions and methods
- Mock external dependencies
- Focus on business logic

### Integration Tests
- Test API endpoints
- Test database interactions
- Test service integrations

### E2E Tests
- Test complete user flows
- Use real browser automation
- Run in a production-like environment

## Performance Considerations

- Use database indexes for frequently queried fields
- Implement caching for expensive operations
- Use pagination for large result sets
- Optimize database queries with `EXPLAIN ANALYZE`

## Security Best Practices

- Validate all user input
- Use parameterized queries to prevent SQL injection
- Implement rate limiting
- Use HTTPS in production
- Keep dependencies updated
- Follow the principle of least privilege

## Deployment

### Staging
- Automatically deployed from `develop` branch
- Used for QA and testing

### Production
- Manually deployed from `main` branch
- Requires approval from maintainers

### Infrastructure as Code
- Terraform for infrastructure provisioning
- Kubernetes for container orchestration
- Helm charts for application deployment

## Troubleshooting

### Common Issues

#### Database Connection Issues
- Verify PostgreSQL is running
- Check connection string in `.env`
- Run migrations with `alembic upgrade head`

#### Frontend Not Updating
- Clear browser cache
- Check browser console for errors
- Restart the Streamlit server

#### Test Failures
- Run tests with `pytest -v` for verbose output
- Check for database state issues
- Run `pytest --lf` to run only failed tests

### Getting Help
- Check the project's GitHub issues
- Ask in the team's Slack channel
- Schedule a pair programming session

---
*Last Updated: August 2025*
