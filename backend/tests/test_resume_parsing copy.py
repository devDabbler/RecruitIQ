#!/usr/bin/env python3
"""
Test script to debug resume parsing with actual text
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.utils.resume_parsing.resume_parser import ResumeParser
from backend.services.storage_service import StorageService
from backend.services.nebius_ai_service import NebiusAIService

async def test_resume_parsing():
    """Test resume parsing with actual text"""
    
    # The actual resume text from the logs
    resume_text = """### Clint Forest
425-098-5467 - clint.forest@email.com
- www.linkedin.com/profile4
453 Jones Blvd Bothell, WA

## Profile
Results-driven data analyst and machine learning practitioner with a strong
academic foundation and hands-on experience in both industry and research
settings.

## Work Experience

### Summer Associate - Data Analyst (May 2023 - August 2023)

### Credit Union - Alexandria, VA
Collaborated with the Lending Analytics team to develop Tableau dashboards, analyzing
Consumer Lending and Credit Card Portfolio models for NFCU's Capital Plan stress testing.
Delivered data-driven insights influencing over 50% of revenue from loan originations,
facilitating informed decision-making by NFCU management.
Optimized matrix models, revised loss rates for Education Lending Models, and participated in
Agile processes to streamline project efficiency.

### Data Analyst (July 2020 - August 2022)

### Cognizant - Chennai, India
Implemented supervised machine learning in Python to create a price optimization tool for
Consumer Products Goods (C.P.G.) during promotional periods.
Applied statistical models, including linear mixed effects regression and Bayesian hierarchical
modeling on Azure, leading to a 1% sales increase in the pet care segment; mentored interns
during the process.
Conducted Exploratory Data Analysis to determine correlations between key performance
indicators and data accuracy, and deployed a Python simulator for web tool backend,
forecasting a 30% reduction in volume for a seasonal pack optimization.

### Data Analyst (January 2020 - July 2020)

### Cognizant - Chennai, India
Created Python and R models for identifying high-opportunity food categories using sales data
from Google, Amazon.
Resolved conflicts and proposed strategies for optimizing brand positioning and boosting sales
in different food categories.

## Education
Georgia Technical Institute - Atlanta, GA (January 2016 - December 2023)

### Bachelor of Science, Computer Science

### Northwestern University - Boston, MA (January 2020 - January 2022)

### Masters of Science, Information Systems

## Skills
Python, SQL, T-SQL, PL/SQL, Java, C++, Talend Data Integration, XSV, Snowflake
Alteryx, Elasticsearch, Kibana, Trifacta, Tableau, Azure ML Studio, Hadoop
SSIS, PySpark, MS PowerBI, Salesforce Einstein Analytics, MS Office, Teradata,
Excel (Pivot and VLookup)

### NumPy, Pandas, Scikit-Learn, PyTorch, TensorFlow, Keras, Matplotlib
Seaborn, Jupyter Notebook, NetBeans, Eclipse, Visual Studio, Kubernetes, and
ER Studio"""

    print("=== Testing Resume Parsing Pipeline ===")
    
    # Create resume parser
    storage_service = StorageService()
    nebius_service = NebiusAIService()
    parser = ResumeParser(storage_service, nebius_service)
    
    # Test section processing directly
    print("\n1. Testing section processing...")
    sections = await parser.section_processor.process(resume_text)
    print(f"   Sections found: {list(sections.keys())}")
    print(f"   Experience section length: {len(sections.get('experience', ''))}")
    print(f"   Education section length: {len(sections.get('education', ''))}")
    
    # Test information extraction
    print("\n2. Testing information extraction...")
    resume_data = await parser._extract_information(resume_text, sections)
    
    print(f"\n3. Results:")
    print(f"   Experience entries: {len(resume_data.experience) if resume_data.experience else 0}")
    print(f"   Education entries: {len(resume_data.education) if resume_data.education else 0}")
    print(f"   Skills: {len(resume_data.skills) if resume_data.skills else 0}")
    
    if resume_data.experience:
        print(f"\n   First experience entry:")
        exp = resume_data.experience[0]
        print(f"     Title: {exp.title}")
        print(f"     Company: {exp.company}")
        print(f"     Dates: {exp.start_date} - {exp.end_date}")
    
    if resume_data.education:
        print(f"\n   First education entry:")
        edu = resume_data.education[0]
        print(f"     Institution: {edu.institution}")
        print(f"     Degree: {edu.degree}")
        print(f"     Dates: {edu.start_date} - {edu.end_date}")

if __name__ == "__main__":
    asyncio.run(test_resume_parsing()) 