#!/usr/bin/env python3
"""
Debug script to test section extraction patterns
"""

import sys
import os
import asyncio
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import re
from backend.utils.resume_parsing.processors.section_processor import SectionProcessor

async def test_section_processor():
    """Test the section processor with the actual resume text"""
    
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

    print("=== Testing Section Processor ===")
    
    # Create section processor
    section_processor = SectionProcessor()
    
    # Process the resume text
    sections = await section_processor.process(resume_text)
    
    print(f"Section processor found {len(sections)} sections:")
    for section_name, content in sections.items():
        print(f"  {section_name}: {len(content)} characters")
        if section_name in ['experience', 'education']:
            print(f"    Preview: {content[:200]}...")
    
    # Check if experience and education sections are present
    if 'experience' in sections:
        print(f"\n✅ Experience section found with {len(sections['experience'])} characters")
    else:
        print("\n❌ Experience section NOT found")
    
    if 'education' in sections:
        print(f"✅ Education section found with {len(sections['education'])} characters")
    else:
        print("❌ Education section NOT found")

if __name__ == "__main__":
    asyncio.run(test_section_processor()) 