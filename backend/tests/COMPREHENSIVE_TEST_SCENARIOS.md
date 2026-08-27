# Comprehensive AI Assistant Test Scenarios

This document outlines all the different types of questions and scenarios that users might ask the RecruitIQ AI assistant, including the new market research functionality.

## 🎯 **Test Categories Overview**

### 1. **Market Research Questions (NEW)**
### 2. **Resume Analysis & Matching**
### 3. **Job Management**
### 4. **Candidate Management**
### 5. **Travel & Logistics**
### 6. **Email Generation**
### 7. **Company Research**
### 8. **Salary & Compensation**
### 9. **General Questions**
### 10. **Edge Cases & Error Handling**

---

## 📊 **1. MARKET RESEARCH QUESTIONS (NEW FUNCTIONALITY)**

### **1.1 City Viability Reports**
**Purpose**: Assess sourcing viability for specific roles in specific cities.

**Test Scenarios**:
- `"Externally, assess the sourcing viability for a senior Python developer in Boise"`
- `"What's the talent market like for data scientists in Austin over the last 6 months?"`
- `"How viable is hiring a senior product manager in Nashville?"`
- `"Assess the market for frontend developers in Salt Lake City"`
- `"What's the talent supply like for DevOps engineers in Denver?"`

**Expected Responses**:
- Talent supply estimates (high/medium/low)
- Active postings volume and trends
- Major employers hiring this role
- University pipeline strength
- Salary bands and market rates
- Cost-of-living impact
- Remote work willingness
- Expected time-to-fill
- Key risks and challenges
- Actionable sourcing tactics

### **1.2 City Comparisons**
**Purpose**: Compare sourcing viability between two cities.

**Test Scenarios**:
- `"Compare sourcing a senior product manager in Boise vs San Francisco"`
- `"How does hiring a frontend developer in Nashville compare to Seattle?"`
- `"Compare talent markets for data scientists in Austin vs Boston"`
- `"Which is better for hiring senior engineers: Denver or Portland?"`
- `"Compare sourcing viability for DevOps in Charlotte vs Atlanta"`

**Expected Responses**:
- Side-by-side comparison
- Talent pool size and availability
- Job postings density
- Competition intensity
- Salary deltas
- Relocation feasibility
- Clear recommendation with confidence level

### **1.3 Non-Tech Hub Shortlists**
**Purpose**: Identify top non-tech hub cities for sourcing.

**Test Scenarios**:
- `"Identify the top 5 non-tech hub cities to source a senior software engineer"`
- `"What are the best non-tech hub cities for hiring a DevOps engineer?"`
- `"List top 3 non-tech hub cities for data scientists"`
- `"Find the best non-tech hub cities for product managers"`
- `"Top non-tech hub cities for frontend developers"`

**Expected Responses**:
- Ranked list of cities
- Rationale for each city
- Key advantages for sourcing
- Expected time-to-fill
- Competition index

### **1.4 Sourcing Plans**
**Purpose**: Generate detailed sourcing strategies.

**Test Scenarios**:
- `"Create a sourcing plan for a senior data scientist in Denver"`
- `"Generate a sourcing strategy for frontend developers in Nashville"`
- `"Develop a sourcing plan for product managers in Salt Lake City"`
- `"Create sourcing tactics for DevOps engineers in Charlotte"`

**Expected Responses**:
- Top channels (LinkedIn, meetups, Slack groups)
- Boolean search strings
- Outreach messaging approach
- Weekly activity targets
- Timeline expectations
- Risk mitigation strategies
- Local networking opportunities

### **1.5 Hiring Manager Briefings**
**Purpose**: Create executive briefings on hiring challenges.

**Test Scenarios**:
- `"Prepare a briefing for hiring managers on hiring challenges for a senior product manager in Portland"`
- `"Create an executive briefing on hiring data scientists in Austin"`
- `"Generate a briefing on frontend developer hiring challenges in Nashville"`

**Expected Responses**:
- Executive summary
- Market evidence and data
- Salary/competition pressures
- Realistic timelines
- Alternative approaches
- Actionable recommendations

### **1.6 JSON Data Requests**
**Purpose**: Generate structured data for dashboards.

**Test Scenarios**:
- `"Return only valid JSON for a senior backend engineer in Atlanta"`
- `"Generate JSON data for data scientist market in Seattle"`
- `"Provide JSON report for product manager hiring in Denver"`

**Expected Responses**:
- Valid JSON structure
- Talent supply estimates
- Postings volume
- Top companies
- Universities
- Salary bands
- Cost of living index
- Competition index
- Remote readiness
- Time to fill estimates

---

## 📄 **2. RESUME ANALYSIS & MATCHING**

### **2.1 Basic Resume Analysis**
**Test Scenarios**:
- `"Analyze this resume for a senior software engineer position"`
- `"Evaluate this candidate's resume for a data scientist role"`
- `"Review this resume for a product manager position"`
- `"Assess this resume for a frontend developer role"`

### **2.2 Candidate-Job Matching**
**Test Scenarios**:
- `"Match this candidate to our open positions"`
- `"Find the best job matches for this candidate"`
- `"Which of our roles would this candidate be best suited for?"`
- `"Rate this candidate's fit for our senior developer role"`

### **2.3 Skills Analysis**
**Test Scenarios**:
- `"What are the key skills highlighted in this resume?"`
- `"Analyze the technical skills in this candidate's resume"`
- `"What experience level does this resume indicate?"`
- `"Identify gaps in this candidate's skill set"`

---

## 💼 **3. JOB MANAGEMENT**

### **3.1 Job Creation**
**Test Scenarios**:
- `"Create a job posting for a senior data scientist"`
- `"Generate a job description for a frontend developer"`
- `"Write a job posting for a product manager"`
- `"Create a job description for a DevOps engineer"`

### **3.2 Job Analysis**
**Test Scenarios**:
- `"Analyze this job posting for potential issues"`
- `"Review this job description for clarity"`
- `"What improvements can be made to this job posting?"`
- `"Check this job description for bias"`

### **3.3 Job Requirements**
**Test Scenarios**:
- `"What are the essential requirements for a senior developer role?"`
- `"List the key qualifications for a data scientist position"`
- `"What skills are typically required for a product manager?"`

---

## 👥 **4. CANDIDATE MANAGEMENT**

### **4.1 Candidate Search**
**Test Scenarios**:
- `"Find candidates with Python and machine learning experience"`
- `"Search for senior frontend developers"`
- `"Find candidates with 5+ years of experience"`
- `"Search for candidates in the Austin area"`

### **4.2 Candidate Evaluation**
**Test Scenarios**:
- `"Evaluate this candidate for our senior developer role"`
- `"Assess this candidate's fit for our team"`
- `"What are this candidate's strengths and weaknesses?"`
- `"Rate this candidate's technical skills"`

### **4.3 Candidate Pipeline**
**Test Scenarios**:
- `"What's the status of our candidate pipeline?"`
- `"How many candidates are in each stage?"`
- `"Which candidates need follow-up?"`

---

## 🚗 **5. TRAVEL & LOGISTICS**

### **5.1 Travel Time Queries**
**Test Scenarios**:
- `"How long does it take to travel from San Francisco to Austin?"`
- `"What's the travel time between Seattle and Portland?"`
- `"How long to get from NYC to Boston?"`
- `"Travel time from Denver to Salt Lake City"`

### **5.2 Transportation Options**
**Test Scenarios**:
- `"What are the transportation options from Seattle to Portland?"`
- `"How can I get from Austin to Dallas?"`
- `"Transportation options from SF to LA"`
- `"Best way to travel from Chicago to Detroit"`

---

## 📧 **6. EMAIL GENERATION**

### **6.1 Candidate Pitch Emails**
**Test Scenarios**:
- `"Generate a pitch email for a senior product manager candidate"`
- `"Create a candidate pitch email for a data scientist"`
- `"Write a pitch email for a frontend developer"`
- `"Generate a candidate outreach email"`

### **6.2 Recruiter Outreach Emails**
**Test Scenarios**:
- `"Create an outreach email to a potential candidate"`
- `"Generate a recruiter outreach message"`
- `"Write a follow-up email to a candidate"`
- `"Create a networking email"`

---

## 🏢 **7. COMPANY RESEARCH**

### **7.1 Company Information**
**Test Scenarios**:
- `"Tell me about Google's hiring practices"`
- `"What's the company culture like at Microsoft?"`
- `"Research hiring trends at Amazon"`
- `"Find information about startup hiring practices"`

### **7.2 Market Trends**
**Test Scenarios**:
- `"What are the current trends in tech hiring?"`
- `"How is the job market for developers?"`
- `"What are the latest hiring trends?"`
- `"Market analysis for tech talent"`

---

## 💰 **8. SALARY & COMPENSATION**

### **8.1 Salary Benchmarks**
**Test Scenarios**:
- `"What's the salary range for a senior data scientist in New York?"`
- `"Salary benchmark for frontend developers in Austin"`
- `"What do senior product managers earn in Seattle?"`
- `"Salary range for DevOps engineers in Denver"`

### **8.2 Compensation Analysis**
**Test Scenarios**:
- `"Analyze compensation packages for senior engineers"`
- `"Compare salary ranges across different cities"`
- `"What benefits are typical for tech roles?"`
- `"Compensation analysis for remote workers"`

---

## ❓ **9. GENERAL QUESTIONS**

### **9.1 Help Requests**
**Test Scenarios**:
- `"What can you help me with?"`
- `"How do I use this system?"`
- `"What are your capabilities?"`
- `"Show me available features"`

### **9.2 Clarification Requests**
**Test Scenarios**:
- `"I'm not sure what you mean"`
- `"Can you clarify that?"`
- `"I don't understand"`
- `"Please explain further"`

---

## ⚠️ **10. EDGE CASES & ERROR HANDLING**

### **10.1 Empty/Invalid Input**
**Test Scenarios**:
- `""` (empty message)
- `"   "` (whitespace only)
- `"???"` (unclear input)
- `"asdf"` (random characters)

### **10.2 Very Long Messages**
**Test Scenarios**:
- Messages exceeding normal limits
- Extremely detailed requests
- Multiple questions in one message

### **10.3 Special Characters**
**Test Scenarios**:
- `"What about hiring in São Paulo, Brazil? 🇧🇷"`
- `"Talent market in München, Germany?"`
- `"Hiring in 北京, China?"`

### **10.4 Ambiguous Requests**
**Test Scenarios**:
- `"Find developers in Austin"` (which type?)
- `"Analyze this"` (what to analyze?)
- `"Compare cities"` (which cities?)

### **10.5 Non-Existent Locations**
**Test Scenarios**:
- `"What's the talent market like in Atlantis?"`
- `"Hiring in Neverland?"`
- `"Market analysis for Hogwarts"`

---

## 🧪 **TESTING METHODOLOGY**

### **Difficulty Levels**
- **Basic**: Simple, straightforward questions
- **Intermediate**: Questions requiring analysis or comparison
- **Advanced**: Complex scenarios with multiple parameters
- **Edge Case**: Error conditions and unusual inputs

### **Response Quality Indicators**
- **Comprehensive Analysis**: Detailed, thorough responses
- **Specific Data**: Concrete numbers and facts
- **Actionable Insights**: Practical recommendations
- **Clear Structure**: Well-organized information
- **Error Handling**: Graceful handling of edge cases

### **Performance Metrics**
- Response time
- Accuracy of intent detection
- Completeness of responses
- Error recovery capability
- User satisfaction indicators

---

## 🚀 **USAGE EXAMPLES**

### **Quick Market Research**
```bash
# Test market research functionality
python run_comprehensive_assistant_tests.py --category market_research --verbose

# Test specific difficulty level
python run_comprehensive_assistant_tests.py --difficulty advanced

# Run all tests
python run_comprehensive_assistant_tests.py --all
```

### **Real-World Scenarios**
1. **Recruiter**: "I need to know if we can find senior Python developers in Boise"
2. **Hiring Manager**: "Compare hiring costs between Austin and Nashville"
3. **Talent Acquisition**: "Create a sourcing plan for data scientists in Denver"
4. **HR Director**: "Prepare a briefing on hiring challenges in Portland"

---

## 📈 **EXPECTED OUTCOMES**

### **Success Criteria**
- ✅ All basic functionality works correctly
- ✅ Market research provides valuable insights
- ✅ Error handling is graceful and helpful
- ✅ Response quality meets user expectations
- ✅ System remains dynamic and non-hardcoded

### **Limitations to Test**
- Token limits for long responses
- API rate limiting
- External service dependencies
- Network connectivity issues
- Data freshness and accuracy

### **Continuous Improvement**
- Monitor user feedback
- Track common failure patterns
- Update test cases based on real usage
- Expand coverage for new features
- Optimize response quality and speed

---

This comprehensive test suite ensures that the RecruitIQ AI assistant can handle all types of questions users might ask, providing valuable insights for recruiters and hiring managers while maintaining the system's dynamic and flexible nature.
