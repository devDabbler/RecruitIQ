# RecruitIQ FAQ

## Table of Contents
- [General](#general)
- [Account & Access](#account--access)
- [Resume Parsing](#resume-parsing)
- [Candidate Management](#candidate-management)
- [Job Postings](#job-postings)
- [Matching Engine](#matching-engine)
- [AI Assistant](#ai-assistant)
- [Troubleshooting](#troubleshooting)
- [Billing & Plans](#billing--plans)
- [Security & Privacy](#security--privacy)

## General

### What is RecruitIQ?
RecruitIQ is an AI-powered recruiting platform that streamlines the hiring process with features like resume parsing, candidate matching, interview scheduling, and market intelligence.

### What web browsers are supported?
RecruitIQ works best on the latest versions of:
- Google Chrome
- Mozilla Firefox
- Microsoft Edge
- Safari

### Is there a mobile app?
Not currently, but our web application is fully responsive and works on mobile browsers.

## Account & Access

### How do I reset my password?
1. Go to the login page
2. Click "Forgot Password?"
3. Enter your email address
4. Check your email for a password reset link
5. Create a new password

### How do I add team members?
1. Go to Settings > Team
2. Click "Invite Team Member"
3. Enter their email and select their role
4. Click "Send Invitation"

### What user roles are available?
- **Admin**: Full access to all features and settings
- **Hiring Manager**: Can view candidates, schedule interviews, and make hiring decisions
- **Recruiter**: Can source and screen candidates
- **Interviewer**: Can only view assigned candidates and submit feedback

## Resume Parsing

### What file formats are supported for resumes?
We support:
- PDF (.pdf)
- Microsoft Word (.doc, .docx)
- Text files (.txt)
- Images (.jpg, .png) with OCR

### Why is my resume not parsing correctly?
Common issues include:
- Scanned documents (use OCR for images)
- Complex formatting or tables
- Password-protected files
- Very large files (>10MB)

### How can I improve parsing accuracy?
- Use standard resume formats
- Avoid complex layouts and tables
- Ensure text is selectable (not an image of text)
- Include clear section headers (Experience, Education, etc.)
- For developers: Use the 'comprehensive' strategy for better accuracy

### Developer: How do I integrate the resume parsing API?
```python
import requests

url = "https://api.recruitiq.com/v1/resumes/parse"
headers = {"Authorization": "Bearer YOUR_API_KEY"}
files = {"file": open("resume.pdf", "rb")}
data = {"strategy": "comprehensive", "enhance_with_web": True}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())
```

## Candidate Management

### How do I import candidates from LinkedIn?
1. Go to Candidates > Import
2. Select "LinkedIn"
3. Follow the prompts to connect your account
4. Select candidates to import

### Can I export candidate data?
Yes, go to Candidates > Export to download candidate data in CSV or Excel format.

### How do I track candidate status?
Use the candidate pipeline view to drag and drop candidates between stages:
1. New Application
2. Screen
3. Interview
4. Offer
5. Hired

## Job Postings

### How do I post a job to multiple job boards?
1. Create a new job posting
2. Under "Distribution," select the job boards
3. Click "Publish"

### Can I schedule a job posting for later?
Yes, when creating or editing a job, use the "Publish Date" field to schedule it.

### How do I extend the application deadline?
1. Go to Jobs
2. Click on the job
3. Click "Edit"
4. Update the closing date
5. Click "Save"

## Matching Engine

### How does the matching algorithm work?
Our algorithm considers:
- Skills match (50% weight)
- Experience level (25%)
- Education (15%)
- Location preference (10%)

### Why isn't the system finding good matches?
Try these steps:
1. Review your job description for completeness
2. Adjust the matching criteria
3. Expand your search radius
4. Check for overly restrictive filters

### Can I adjust the matching criteria?
Yes, go to Settings > Matching to adjust the weights for different factors.

## AI Assistant

### What can the AI Assistant do?
- Screen resumes
- Answer candidate questions
- Schedule interviews
- Generate job descriptions
- Provide market insights

### Is the AI Assistant always accurate?
While highly accurate, we recommend reviewing all AI-generated content. The system learns and improves over time.

### How do I train the AI on my hiring preferences?
1. Go to AI Assistant > Training
2. Upload sample resumes of good/bad candidates
3. Provide feedback on AI suggestions
4. The system will adapt to your preferences

## Troubleshooting

### Common Resume Parsing Issues

#### Missing Education/Experience Entries
**Symptom**: Some education or experience entries are missing in the parsed output.
**Solution**:
1. Check the raw text extraction quality
2. Try the 'comprehensive' strategy
3. Verify the resume has clear section headers
4. Check logs for any extraction warnings

#### Broken Experience Descriptions
**Symptom**: Experience descriptions have broken sentences or incorrect formatting.
**Solution**:
1. Enable text cleaning in the API request
2. Check for special characters that might affect parsing
3. Use the latest parser version

### API Errors

#### 401 Unauthorized
- Verify your API token is correct and not expired
- Check token permissions in the dashboard
- Ensure proper header format: `Authorization: Bearer YOUR_TOKEN`

#### 429 Too Many Requests
- You've exceeded the rate limit (default: 100 requests/minute)
- Implement exponential backoff in your client
- Consider using batch endpoints for bulk operations

### Performance Issues

#### Slow Response Times
- Check your network latency
- Try the 'fast' parsing strategy
- Verify server status at status.recruitiq.com
- Check if your instance has sufficient resources

#### High CPU/Memory Usage
- Monitor resource usage with `docker stats` or cloud provider tools
- Scale your deployment horizontally
- Review recent code changes for performance regressions

## Billing & Plans

### How is pricing calculated?
Pricing is based on:
- Number of active users
- API call volume
- Storage usage
- Advanced features (AI matching, web enhancement)

### Self-Hosted vs. Cloud

| Feature | Self-Hosted | Cloud |
|---------|-------------|-------|
| Deployment | Your infrastructure | Fully managed |
| Pricing | One-time + support | Monthly/Annual |
| Maintenance | Your responsibility | Included |
| Updates | Manual | Automatic |
| Support | Community/Paid | Priority |

### How do I upgrade my plan?
1. Go to Billing
2. Click "Upgrade Plan"
3. Select your new plan
4. Enter payment details
5. Click "Confirm"

### Can I cancel anytime?
Yes, you can cancel your subscription at any time. You'll retain access until the end of your billing period.

### Do you offer discounts for non-profits?
Yes, we offer special pricing for registered non-profits. Contact our sales team for details.

## Security & Privacy

### Is my data secure?
Yes, we use industry-standard security measures including:
- Data encryption at rest and in transit
- Regular security audits
- Role-based access controls
- SOC 2 Type II compliance

### Where is my data stored?
Your data is stored in secure AWS data centers. You can choose your preferred region during setup.

### How do I request data deletion?
Submit a data deletion request through the Privacy section in your account settings, or contact our support team.

---
*Last Updated: August 2025*

### Still need help?
Contact our support team at support@recruitiq.com or call (555) 123-4567 (Mon-Fri, 9am-6pm EST)
