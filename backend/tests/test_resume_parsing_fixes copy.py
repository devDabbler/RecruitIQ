#!/usr/bin/env python3
"""
Test script to verify resume parsing fixes
"""

import asyncio
import json
import logging
from pathlib import Path
import sys

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from utils.resume_parsing.resume_parser import ResumeParser
from services.nebius_ai_service import NebiusAIService
from utils.resume_parsing.models.resume_schema import ResumeData

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_resume_parsing():
    """Test the resume parsing with the fixes"""
    
    # Sample resume text (Clint Forest's resume from the log)
    sample_resume_text = """### Clint Forest
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

    try:
        # Test the resume parser with proper dependencies
        from services.minio_storage_service import MinioStorageService
        from services.nebius_ai_service import NebiusAIService
        
        storage_service = MinioStorageService()
        nebius_service = NebiusAIService()
        
        parser = ResumeParser(storage_service=storage_service, nebius_ai_service=nebius_service)
        result = await parser.parse_resume(sample_resume_text)
        
        print("=== Resume Parsing Test Results ===")
        print(f"Personal Info: {result.personal_info}")
        print(f"Education entries: {len(result.education)}")
        for i, edu in enumerate(result.education):
            print(f"  Education {i+1}: {edu.institution} - {edu.degree}")
        print(f"Experience entries: {len(result.experience)}")
        for i, exp in enumerate(result.experience):
            print(f"  Experience {i+1}: {exp.title} at {exp.company}")
        print(f"Skills: {len(result.skills)}")
        for i, skill in enumerate(result.skills[:10]):  # Show first 10 skills
            print(f"  Skill {i+1}: {skill.name}")
        
        # Test the Nebius AI service
        print("\n=== Testing Nebius AI Service ===")
        nebius_service = NebiusAIService()
        
        # Create a simple schema prompt
        schema_prompt = "Extract resume information and return as JSON"
        
        ai_result = await nebius_service.parse_resume(sample_resume_text, schema_prompt)
        
        print(f"AI Personal Info: {ai_result.personal_info}")
        print(f"AI Education entries: {len(ai_result.education)}")
        print(f"AI Experience entries: {len(ai_result.experience)}")
        print(f"AI Skills: {len(ai_result.skills)}")
        
        print("\n=== Test Completed Successfully ===")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        logger.exception("Test error details:")

if __name__ == "__main__":
    asyncio.run(test_resume_parsing()) 