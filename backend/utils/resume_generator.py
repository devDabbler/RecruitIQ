"""
Utility to generate PDF resumes from text content.
For this POC, we'll use a simple approach to create PDFs from resume text.
"""
import os
from pathlib import Path
from fpdf import FPDF

def generate_pdf_resume(resume_text, output_path):
    """
    Generate a simple PDF resume from text content.
    
    Args:
        resume_text: The text content of the resume
        output_path: Path where the PDF should be saved
    
    Returns:
        Path to the generated PDF file
    """
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Create PDF object
    pdf = FPDF()
    pdf.add_page()
    
    # Set font and size
    pdf.set_font("Arial", size=12)
    
    # Add content - split by lines and add each line
    for line in resume_text.split('\n'):
        # Detect section headers (all caps lines) and make them bold
        if line.strip() and line.strip().isupper():
            pdf.set_font("Arial", 'B', size=14)
            pdf.cell(200, 10, txt=line, ln=True)
            pdf.set_font("Arial", size=12)
        else:
            # Check if line is part of contact info (at the top)
            if '|' in line and pdf.page_no() == 1 and pdf.get_y() < 30:
                pdf.set_font("Arial", size=10)
                pdf.cell(200, 5, txt=line, ln=True)
                pdf.set_font("Arial", size=12)
            else:
                pdf.cell(200, 5, txt=line, ln=True)
    
    # Save the pdf file
    pdf.output(output_path)
    
    return output_path
