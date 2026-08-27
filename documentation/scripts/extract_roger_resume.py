"""
Extracts and prints the text from Roger Waters' resume PDF for analysis.
"""
import sys
from PyPDF2 import PdfReader

PDF_PATH = "../Roger Waters Resume.pdf"

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

if __name__ == "__main__":
    text = extract_text_from_pdf(PDF_PATH)
    print(text)
