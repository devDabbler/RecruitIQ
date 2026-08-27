"""
Create Sample Resumes Script
Creates simple text files with .pdf extension for testing the candidate matching example
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_sample_resumes(resume_dir: str) -> None:
    """
    Create sample resume files for testing
    
    Args:
        resume_dir: Path to the resume directory
    """
    resume_path = Path(resume_dir)
    
    # Create the directory if it doesn't exist
    if not resume_path.exists():
        logger.info(f"Creating resume directory: {resume_path}")
        resume_path.mkdir(parents=True, exist_ok=True)
    
    # Sample resume names
    sample_names = [
        "David_Garcia_Resume",
        "Emily_Johnson_Resume",
        "James_Wilson_Resume",
        "Jessica_Williams_Resume",
        "Michael_Chen_Resume",
        "Olivia_Brown_Resume",
        "Robert_Taylor_Resume",
        "Sophia_Martinez_Resume"
    ]
    
    # Create sample files
    for name in sample_names:
        file_path = resume_path / f"{name}.txt"
        
        # Create sample text
        sample_text = f"Sample resume for {name.replace('_', ' ')}\n\n"
        
        # Add some personalized content
        if "Garcia" in name:
            sample_text += "Skills: Python, Django, PostgreSQL, Docker\n"
            sample_text += "Experience: Senior Software Engineer at TechCorp (2018-Present)\n"
            sample_text += "Education: Master's in Computer Science, Stanford University"
        elif "Johnson" in name:
            sample_text += "Skills: JavaScript, React, Node.js, AWS\n"
            sample_text += "Experience: Frontend Developer at WebSolutions (2019-Present)\n"
            sample_text += "Education: Bachelor's in Web Development, UC Berkeley"
        elif "Wilson" in name:
            sample_text += "Skills: Java, Spring, Hibernate, MySQL\n"
            sample_text += "Experience: Backend Developer at DataSystems (2017-Present)\n"
            sample_text += "Education: Bachelor's in Software Engineering, MIT"
        elif "Williams" in name:
            sample_text += "Skills: C#, .NET, Azure, SQL Server\n"
            sample_text += "Experience: Full Stack Developer at CloudTech (2020-Present)\n"
            sample_text += "Education: Master's in Information Technology, Georgia Tech"
        elif "Chen" in name:
            sample_text += "Skills: Data Science, Python, R, TensorFlow, PyTorch\n"
            sample_text += "Experience: Data Scientist at AILabs (2019-Present)\n"
            sample_text += "Education: PhD in Machine Learning, Carnegie Mellon"
        elif "Brown" in name:
            sample_text += "Skills: UX/UI Design, Figma, Adobe XD, HTML/CSS\n"
            sample_text += "Experience: UX Designer at DesignHub (2018-Present)\n"
            sample_text += "Education: Bachelor's in Graphic Design, RISD"
        elif "Taylor" in name:
            sample_text += "Skills: DevOps, Kubernetes, Docker, Terraform, AWS\n"
            sample_text += "Experience: DevOps Engineer at CloudOps (2017-Present)\n"
            sample_text += "Education: Bachelor's in Computer Engineering, Caltech"
        elif "Martinez" in name:
            sample_text += "Skills: Product Management, Agile, JIRA, SQL\n"
            sample_text += "Experience: Product Manager at ProductCo (2016-Present)\n"
            sample_text += "Education: MBA, Harvard Business School"
        
        # Write the text file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(sample_text)
            logger.info(f"✅ Created sample resume: {file_path}")
        except Exception as e:
            logger.error(f"❌ Failed to create sample resume: {file_path} - {e}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create sample resume files for testing')
    parser.add_argument('--resume-dir', type=str, default="data/resumes", 
                        help='Path to the resume directory')
    
    args = parser.parse_args()
    
    create_sample_resumes(args.resume_dir)
    
    logger.info("Done!")

if __name__ == "__main__":
    main()
