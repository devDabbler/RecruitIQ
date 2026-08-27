# RecruitIQ MCP Quick Reference

## ✅ Current Status (January 2025)
**🎉 AI ASSISTANT: 100% OPERATIONAL - All tests passing!**

## System Health Check
```bash
# Verify 100% functionality
cd backend && poetry run python test_ai_assistant_comprehensive_fix.py
# Expected: 100% success rate (10/10 tests)
```

### AI Assistant Chat
```json
{"name": "chat_with_assistant", "arguments": {
  "message": "What skills do software engineers need?",
  "conversation_history": [],
  "conversation_context": {}
}}
```

### AI Assistant Testing
```json
{"name": "test_ai_assistant", "arguments": {
  "test_type": "comprehensive"
}}
```

## ✅ Validated AI Assistant Test Queries (100% Pass Rate)

### Core Functionality Tests
```json
// Greeting Test
{"name": "chat_with_assistant", "arguments": {"message": "Hello, how are you doing?"}}

// Skills Information Test  
{"name": "chat_with_assistant", "arguments": {"message": "What skills do software engineers need?"}}

// Data Scientist Skills Test
{"name": "chat_with_assistant", "arguments": {"message": "What skills do data scientists need?"}}

// Salary Information Test (RECENTLY FIXED!)
{"name": "chat_with_assistant", "arguments": {"message": "What's the salary for a software engineer in New York?"}}

// Company Information Test
{"name": "chat_with_assistant", "arguments": {"message": "Tell me about Google as a company"}}

// Market Trends Test
{"name": "chat_with_assistant", "arguments": {"message": "What are the current market trends in tech?"}}

// Database Count Test
{"name": "chat_with_assistant", "arguments": {"message": "How many candidates are in the database?"}}

// Candidate Search by Role Test
{"name": "chat_with_assistant", "arguments": {"message": "Find me all data scientist candidates"}}

// Candidate Search by Skills Test  
{"name": "chat_with_assistant", "arguments": {"message": "Find candidates with Python skills"}}
```

## Core AI Assistant Tools

### Search Operations
```json
// Find candidates
{"name": "search_candidates", "arguments": {"query": "Python developer", "limit": 10}}

// Find jobs  
{"name": "search_jobs", "arguments": {"query": "Software Engineer", "limit": 10}}

// List skills
{"name": "list_skills", "arguments": {"limit": 50}}
```

### Analysis Operations
```json
// Parse resume
{"name": "analyze_resume", "arguments": {"file_path": "path/to/resume.pdf"}}

// Match candidates to job
{"name": "match_candidates_to_job", "arguments": {"job_id": "job_123", "limit": 10}}
```

## 🔧 Common Development Workflows

### 1. Debug System Issues
1. `get_system_status` - Check if services are running
2. `search_candidates` - Test database connectivity
3. `list_skills` - Verify data availability

### 2. Resume Parsing Debug
1. `analyze_resume` with test file
2. Identify missing fields (name, phone, company, etc.)
3. Suggest regex/parsing improvements
4. Test again with same file

### 3. Data Quality Analysis
1. `list_skills` - Check skill coverage
2. `search_candidates` - Analyze candidate data
3. `search_jobs` - Analyze job data
4. Identify gaps/inconsistencies

### 4. Feature Testing
1. Use relevant tools to get baseline data
2. Test new feature with real data
3. Compare results to verify improvements
4. Suggest optimizations

## 📊 Expected Response Formats

### System Status
```
✅ Backend: Running (http://localhost:8000)
✅ Frontend: Running (http://localhost:8501)
```

### Candidate Search
```
Found X candidates for query '...':
1. **Name**
   - Skills: skill1, skill2, skill3
   - Experience: level
   - Location: city, state
```

### Job Search
```
Found X jobs for query '...':
1. **Job Title**
   - Company: company name
   - Location: city, state
   - Skills: skill1, skill2, skill3
```

### Resume Analysis
```
**Resume Analysis Results**

**Personal Information:**
- Name: John Doe
- Email: john@example.com
- Phone: (555) 123-4567
- Location: San Francisco, CA

**Skills:**
- Python, JavaScript, React

**Experience:**
- Software Engineer at Tech Corp
  Duration: 2020-2023
```

## ⚠️ Common Error Patterns

### Database Issues
- "Error searching candidates: connection failed"
- "No candidates found" (check if database has data)

### File Issues  
- "Resume file not found: path/to/file.pdf"
- "Error analyzing resume: file format not supported"

### System Issues
- "Backend: Not running" - Start backend service
- "Frontend: Not responding" - Check frontend service

## 🎯 Best Practices

### Query Optimization
- Use specific terms: "Python developer 3+ years" vs "developer"
- Include location: "Software Engineer San Francisco"
- Add experience level: "Senior Python developer"

### Limit Management
- Quick checks: `limit: 5-10`
- Analysis: `limit: 20-50` 
- Comprehensive: `limit: 100+`

### Error Handling
- Always check `get_system_status` first
- Verify file paths exist before `analyze_resume`
- Use broader queries if no results found

## 🔍 Troubleshooting Checklist

### No Results Found
- [ ] Check system status
- [ ] Try broader search terms
- [ ] Verify database has data
- [ ] Check if services are running

### Resume Parsing Issues
- [ ] Verify file exists and is readable
- [ ] Check file format (PDF, DOCX supported)
- [ ] Look for specific parsing errors in output
- [ ] Test with known good resume file

### System Errors
- [ ] Check backend service (port 8000)
- [ ] Check frontend service (port 8501) 
- [ ] Verify database connection
- [ ] Check MCP server logs

## 💡 Pro Tips

1. **Start with status** - Always verify system health first
2. **Use specific queries** - More specific = better results
3. **Test incrementally** - Start with small limits, increase as needed
4. **Analyze patterns** - Look for data quality issues in responses
5. **Suggest improvements** - Based on tool outputs, provide actionable feedback

## 📞 Emergency Commands

### System Reset
```bash
# Restart backend
poetry run python start_backend.py

# Restart frontend  
poetry run python start_frontend.py

# Restart MCP server
poetry run python mcp_server.py
```

### Database Check
```bash
# Check database connection
poetry run python -c "from backend.database.db_connection import get_postgres_connection; print('DB OK')"
```

Remember: When in doubt, start with `get_system_status`! 🚀 