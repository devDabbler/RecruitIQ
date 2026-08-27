# RecruitIQ MCP (Model Context Protocol) Usage Guide

## Overview

This guide helps AI assistants understand and effectively use the RecruitIQ MCP server to assist with development tasks. The MCP server provides direct access to the RecruitIQ recruitment intelligence platform's core functionality, enabling AI assistants to perform real-time operations on the system.

## ✅ Current System Status (January 2025)

**🎉 AI ASSISTANT SYSTEM: 100% OPERATIONAL**
- All 10 core functionalities tested and working perfectly
- Comprehensive intent detection with robust pattern matching
- Database integration with multiple fallback mechanisms
- Real-time candidate search and job matching capabilities
- Complete test suite with 100% success rate

## What is MCP?

Model Context Protocol (MCP) enables AI assistants to access tools and data directly from your codebase, allowing them to:
- Execute real-time operations on your system
- Access live data from your database
- Perform complex analysis tasks
- Help with debugging and development
- Provide contextual assistance based on actual system state

Unlike regular HTTP APIs, MCP provides a more integrated experience where AI assistants can directly interact with your application's internals.

## Available Tools

### 1. System Status (`get_system_status`)
**Purpose**: Check the health and status of the RecruitIQ system
**Use Cases**:
- Verify if backend and frontend are running
- Diagnose system issues
- Confirm service availability before performing operations

**Example Usage**:
```json
{
  "name": "get_system_status",
  "arguments": {}
}
```

### 2. Candidate Search (`search_candidates`)
**Purpose**: Search for candidates in the database based on skills, experience, or other criteria
**Parameters**:
- `query` (required): Search terms (skills, experience, location, etc.)
- `limit` (optional): Maximum number of results (default: 10)

**Use Cases**:
- Find candidates with specific skills
- Search for candidates in particular locations
- Identify candidates with certain experience levels
- Help with candidate sourcing

**Example Usage**:
```json
{
  "name": "search_candidates",
  "arguments": {
    "query": "Python developer with 5+ years experience",
    "limit": 15
  }
}
```

### 3. Job Search (`search_jobs`)
**Purpose**: Search for job postings in the database
**Parameters**:
- `query` (required): Search terms (title, skills, location, company, etc.)
- `limit` (optional): Maximum number of results (default: 10)

**Use Cases**:
- Find jobs matching specific criteria
- Search for jobs in particular locations
- Identify jobs requiring specific skills
- Help with job market analysis

**Example Usage**:
```json
{
  "name": "search_jobs",
  "arguments": {
    "query": "Software Engineer remote Python",
    "limit": 20
  }
}
```

### 4. Resume Analysis (`analyze_resume`)
**Purpose**: Parse and analyze resume files to extract candidate information
**Parameters**:
- `file_path` (required): Path to the resume file (PDF, DOCX, etc.)

**Use Cases**:
- Extract candidate information from resumes
- Analyze candidate skills and experience
- Help with resume parsing improvements
- Debug resume parsing issues

**Example Usage**:
```json
{
  "name": "analyze_resume",
  "arguments": {
    "file_path": "path/to/candidate_resume.pdf"
  }
}
```

### 5. Candidate-Job Matching (`match_candidates_to_job`)
**Purpose**: Find the best candidates for a specific job using AI-powered matching
**Parameters**:
- `job_id` (required): ID of the job to match candidates for
- `limit` (optional): Maximum number of candidates to return (default: 10)

**Use Cases**:
- Find top candidates for job openings
- Analyze candidate-job fit scores
- Help with recruitment decisions
- Optimize matching algorithms

**Example Usage**:
```json
{
  "name": "match_candidates_to_job",
  "arguments": {
    "job_id": "job_123",
    "limit": 15
  }
}
```

### 6. Skills Listing (`list_skills`)
**Purpose**: Get all available skills in the system
**Parameters**:
- `limit` (optional): Maximum number of skills to return (default: 50)

**Use Cases**:
- Understand available skills in the system
- Help with skill normalization
- Analyze skill distribution
- Improve skill matching

**Example Usage**:
```json
{
  "name": "list_skills",
  "arguments": {
    "limit": 100
  }
}
```

## Development Workflows

### 1. System Diagnostics
When helping with system issues:
1. Start with `get_system_status` to check system health
2. Use specific tools based on the issue (e.g., `search_candidates` for candidate-related problems)
3. Analyze results to identify patterns or issues

### 2. Resume Parsing Improvements
When working on resume parsing:
1. Use `analyze_resume` with test files to see current parsing results
2. Identify specific issues (missing fields, incorrect extractions)
3. Suggest improvements to the parsing logic
4. Test changes with the same files to verify improvements

### 3. Database Analysis
When analyzing data quality or system performance:
1. Use `search_candidates` and `search_jobs` to understand data distribution
2. Use `list_skills` to analyze skill coverage
3. Use `match_candidates_to_job` to test matching algorithms
4. Identify data gaps or inconsistencies

### 4. Feature Development
When developing new features:
1. Use existing tools to understand current functionality
2. Test new features with real data from the system
3. Validate that changes don't break existing functionality
4. Use tools to verify feature effectiveness

## Common Development Tasks

### Debugging Resume Parsing Issues
```json
// 1. Check system status first
{"name": "get_system_status", "arguments": {}}

// 2. Test resume parsing with problematic files
{"name": "analyze_resume", "arguments": {"file_path": "test_resume.pdf"}}

// 3. Analyze results and identify issues
// 4. Suggest specific fixes based on the output
```

### Optimizing Candidate Matching
```json
// 1. Search for candidates to understand data
{"name": "search_candidates", "arguments": {"query": "software engineer", "limit": 20}}

// 2. Search for relevant jobs
{"name": "search_jobs", "arguments": {"query": "software engineer", "limit": 10}}

// 3. Test matching with specific job
{"name": "match_candidates_to_job", "arguments": {"job_id": "job_123", "limit": 15}}

// 4. Analyze matching quality and suggest improvements
```

### Data Quality Analysis
```json
// 1. Check available skills
{"name": "list_skills", "arguments": {"limit": 100}}

// 2. Search for candidates with specific skills
{"name": "search_candidates", "arguments": {"query": "Python", "limit": 50}}

// 3. Analyze skill distribution and suggest improvements
```

## Error Handling

The MCP server includes comprehensive error handling:
- Database connection issues are caught and reported
- File not found errors for resume analysis
- Invalid parameters are validated
- All errors include descriptive messages

When errors occur:
1. Check the error message for specific details
2. Verify system status with `get_system_status`
3. Check if the issue is related to data availability or system configuration
4. Suggest specific fixes based on the error type

## Best Practices for AI Assistants

### 1. Always Check System Status First
Before performing operations, verify the system is running:
```json
{"name": "get_system_status", "arguments": {}}
```

### 2. Use Appropriate Limits
When searching or listing data, use reasonable limits to avoid overwhelming responses:
- Use `limit: 10-20` for initial searches
- Use `limit: 50-100` for comprehensive analysis
- Use `limit: 5-10` for quick checks

### 3. Provide Context in Queries
Use specific, descriptive queries for better results:
- Instead of "developer", use "Python developer with 3+ years experience"
- Instead of "engineer", use "Software Engineer remote React"
- Include relevant skills, experience levels, or locations

### 4. Analyze Results Thoroughly
When reviewing tool outputs:
- Look for patterns in the data
- Identify missing or inconsistent information
- Suggest improvements based on the results
- Consider the implications for system functionality

### 5. Suggest Specific Improvements
Based on tool outputs, provide actionable suggestions:
- Code improvements for parsing logic
- Database schema optimizations
- UI/UX enhancements
- Performance optimizations

## Integration with Development Workflow

### Code Review Assistance
Use MCP tools to:
- Verify that code changes work with real data
- Test new features against existing candidates/jobs
- Validate that improvements actually enhance functionality

### Testing Support
Use MCP tools to:
- Generate test data from real system data
- Verify test results against actual system behavior
- Debug test failures with real system state

### Documentation Updates
Use MCP tools to:
- Verify that documentation matches actual system behavior
- Generate examples based on real data
- Update guides with current system capabilities

## ✅ AI Assistant Testing & Monitoring

### Testing the AI Assistant System
The AI assistant includes comprehensive testing capabilities to verify all functionality:

```bash
# Run the complete test suite (100% success expected)
cd backend && poetry run python test_ai_assistant_comprehensive_fix.py

# Verify database schema and connectivity
cd backend && poetry run python verify_database_schema.py
```

### AI Assistant Test Coverage
The system tests all core functionalities:
- ✅ Basic greetings and general questions
- ✅ Skills information for various roles
- ✅ Company information and research
- ✅ Salary information and market data
- ✅ Web search and market trends
- ✅ Database candidate counting
- ✅ Candidate search by role and skills
- ✅ Real-time database integration

### Monitoring AI Assistant Health
Use these endpoints to monitor the AI assistant:

```json
// Test the main chat functionality
{
  "name": "test_ai_assistant",
  "arguments": {
    "message": "What's the salary for a software engineer in New York?",
    "expected_intent": "salary_info"
  }
}

// Check system status including AI assistant
{
  "name": "get_system_status",
  "arguments": {}
}
```

### AI Assistant Quick Tests
Verify specific AI assistant functions with these test queries:

```json
// Test greeting functionality
{"message": "Hello, how are you doing?"}

// Test skills information
{"message": "What skills do software engineers need?"}

// Test salary information  
{"message": "What's the salary for a software engineer in New York?"}

// Test candidate search
{"message": "Find me all data scientist candidates"}

// Test database integration
{"message": "How many candidates are in the database?"}
```

## Troubleshooting

### AI Assistant Specific Issues

1. **AI Assistant not responding correctly**
   - Run the comprehensive test suite: `poetry run python test_ai_assistant_comprehensive_fix.py`
   - Check intent detection logs for pattern matching failures
   - Verify database connectivity with schema verification script
   - Review the AI Assistant Complete State Documentation

2. **Intent detection failures**
   - Check if patterns are being matched in logs
   - Verify LLM service is available for fallback
   - Test with known working queries from the documentation
   - Review pattern matching logic in `backend/services/intent_processor.py`

3. **Database query failures**
   - Run database schema verification: `poetry run python verify_database_schema.py`
   - Check database connection and permissions
   - Verify candidate and job data exists in the database
   - Review error handling in `backend/routers/assistant.py`

### Common Issues and Solutions

1. **No candidates/jobs found**
   - Check if the system has data: `get_system_status`
   - Try broader search terms
   - Verify the database is properly populated

2. **Resume parsing errors**
   - Check file path and format
   - Verify the resume parser is working: `analyze_resume`
   - Look for specific parsing issues in the output

3. **Matching algorithm issues**
   - Test with known good candidates/jobs
   - Check skill coverage: `list_skills`
   - Analyze matching scores and patterns

4. **System connectivity issues**
   - Always start with `get_system_status`
   - Check if backend/frontend services are running
   - Verify database connections

## Conclusion

The RecruitIQ MCP server provides powerful tools for AI assistants to help with development tasks. By understanding the available tools and following best practices, AI assistants can provide more effective, context-aware assistance that directly leverages the system's capabilities.

Remember to always start with system status checks, use appropriate limits, provide specific queries, and analyze results thoroughly to provide the most helpful assistance possible. 