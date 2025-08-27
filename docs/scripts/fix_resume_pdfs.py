"""
Fix Resume PDFs Script
Validates and repairs PDF files in the resume directory
Creates sample PDFs if needed to ensure the candidate matching example works
"""

import os
import sys
import logging
from pathlib import Path
import shutil
import argparse

# Add parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our PDF validator
from backend.utils.pdf_validator import PDFValidator

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_resume_pdfs(resume_dir: str, create_samples: bool = True, backup: bool = True) -> None:
    """
    Fix PDF files in the resume directory
    
    Args:
        resume_dir: Path to the resume directory
        create_samples: Whether to create sample PDFs if none exist
        backup: Whether to backup existing PDFs before replacing them
    """
    resume_path = Path(resume_dir)
    
    # Create the directory if it doesn't exist
    if not resume_path.exists():
        logger.info(f"Creating resume directory: {resume_path}")
        resume_path.mkdir(parents=True, exist_ok=True)
    
    # Validate existing PDFs
    pdf_files = list(resume_path.glob("*.pdf"))
    
    if pdf_files:
        logger.info(f"Found {len(pdf_files)} PDF files in {resume_path}")
        
        # Create backup directory if needed
        if backup:
            backup_dir = resume_path / "backup"
            backup_dir.mkdir(exist_ok=True)
        
        # Validate each PDF
        valid_pdfs = []
        invalid_pdfs = []
        
        for pdf_file in pdf_files:
            is_valid, message = PDFValidator.validate_pdf(str(pdf_file))
            
            if is_valid:
                logger.info(f"✅ {pdf_file.name}: {message}")
                valid_pdfs.append(pdf_file)
            else:
                logger.warning(f"❌ {pdf_file.name}: {message}")
                invalid_pdfs.append(pdf_file)
                
                # Backup invalid PDF
                if backup:
                    backup_file = backup_dir / pdf_file.name
                    logger.info(f"Backing up invalid PDF to {backup_file}")
                    shutil.copy2(pdf_file, backup_file)
        
        # Fix invalid PDFs
        for pdf_file in invalid_pdfs:
            logger.info(f"Replacing invalid PDF: {pdf_file.name}")
            
            # Create a valid sample PDF with the same name
            sample_text = f"Sample resume for {pdf_file.stem.replace('_', ' ')}\n\n"
            sample_text += "Skills: Python, JavaScript, SQL, Data Analysis\n"
            sample_text += "Experience: Software Engineer, Data Scientist\n"
            sample_text += "Education: Bachelor's in Computer Science"
            
            success = PDFValidator.create_sample_pdf(str(pdf_file), sample_text)
            
            if success:
                logger.info(f"✅ Created sample PDF: {pdf_file.name}")
            else:
                logger.error(f"❌ Failed to create sample PDF: {pdf_file.name}")
    
    elif create_samples:
        # No PDFs found, create sample PDFs
        logger.info(f"No PDF files found in {resume_path}, creating samples")
        
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
        
        # Create sample PDFs
        for name in sample_names:
            pdf_file = resume_path / f"{name}.pdf"
            
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
            
            # Create the PDF
            success = PDFValidator.create_sample_pdf(str(pdf_file), sample_text)
            
            if success:
                logger.info(f"✅ Created sample PDF: {pdf_file.name}")
            else:
                logger.error(f"❌ Failed to create sample PDF: {pdf_file.name}")

def main():
    """Main function to parse arguments and run the script"""
    parser = argparse.ArgumentParser(description='Fix PDF files in the resume directory')
    parser.add_argument('--resume-dir', type=str, default="data/resumes", 
                        help='Path to the resume directory')
    parser.add_argument('--no-samples', action='store_true', 
                        help='Do not create sample PDFs if none exist')
    parser.add_argument('--no-backup', action='store_true', 
                        help='Do not backup existing PDFs before replacing them')
    
    args = parser.parse_args()
    
    fix_resume_pdfs(
        resume_dir=args.resume_dir,
        create_samples=not args.no_samples,
        backup=not args.no_backup
    )
    
    logger.info("Done!")

if __name__ == "__main__":
    main()
