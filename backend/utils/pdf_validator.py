"""
PDF Validator and Repair Utility
Provides tools to validate, repair, and extract text from potentially corrupted PDF files
"""

import os
import logging
from pathlib import Path
import io
import re
from typing import List, Tuple, Optional

# PDF processing
from PyPDF2 import PdfReader
import PyPDF2.errors

logger = logging.getLogger(__name__)

class PDFValidator:
    """Utility class to validate and repair PDF files"""
    
    @staticmethod
    def validate_pdf(file_path: str) -> Tuple[bool, str]:
        """
        Validate if a PDF file is properly formatted and readable
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not os.path.exists(file_path):
            return False, f"File does not exist: {file_path}"
            
        try:
            with open(file_path, 'rb') as file:
                # Check if file starts with PDF signature
                file_start = file.read(5)
                if file_start != b'%PDF-':
                    return False, "Not a valid PDF file (missing PDF signature)"
                
                # Reset file pointer
                file.seek(0)
                
                # Try to read with PyPDF2
                try:
                    reader = PdfReader(file)
                    num_pages = len(reader.pages)
                    return True, f"Valid PDF with {num_pages} pages"
                except PyPDF2.errors.PdfReadError as e:
                    return False, f"PDF read error: {str(e)}"
                except Exception as e:
                    return False, f"Error validating PDF: {str(e)}"
        except Exception as e:
            return False, f"Error opening file: {str(e)}"
    
    @staticmethod
    def extract_text_safe(file_path: str) -> Tuple[bool, str]:
        """
        Safely extract text from a PDF file with multiple fallback methods
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Tuple of (success, text_or_error_message)
        """
        try:
            # Method 1: Standard PyPDF2 extraction
            try:
                with open(file_path, 'rb') as file:
                    reader = PdfReader(file, strict=False)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n\n"
                    
                    if text.strip():
                        return True, text.strip()
                    else:
                        logger.warning(f"No text extracted from {file_path} using standard method")
            except Exception as e:
                logger.warning(f"Standard extraction failed: {str(e)}")
            
            # Method 2: Binary read and decode
            try:
                with open(file_path, 'rb') as file:
                    data = file.read()
                    text = data.decode('utf-8', errors='ignore')
                    # Clean up the text
                    text = re.sub(r'[^\x20-\x7E\n\r\t]', '', text)  # Keep only printable ASCII
                    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
                    
                    if len(text.strip()) > 100:  # Only return if we got meaningful content
                        return True, text.strip()
                    else:
                        logger.warning(f"No meaningful text extracted from {file_path} using binary method")
            except Exception as e:
                logger.warning(f"Binary extraction failed: {str(e)}")
            
            # If we got here, all methods failed
            return False, "All extraction methods failed"
            
        except Exception as e:
            return False, f"Error extracting text: {str(e)}"
    
    @staticmethod
    def validate_pdf_directory(directory_path: str) -> List[Tuple[str, bool, str]]:
        """
        Validate all PDF files in a directory
        
        Args:
            directory_path: Path to directory containing PDF files
            
        Returns:
            List of tuples (file_path, is_valid, message)
        """
        results = []
        
        if not os.path.isdir(directory_path):
            logger.error(f"Directory does not exist: {directory_path}")
            return results
            
        pdf_files = list(Path(directory_path).glob("*.pdf"))
        
        for pdf_file in pdf_files:
            is_valid, message = PDFValidator.validate_pdf(str(pdf_file))
            results.append((str(pdf_file), is_valid, message))
            
        return results
    
    @staticmethod
    def create_sample_pdf(output_path: str, text: str = "This is a sample PDF file.") -> bool:
        """
        Create a simple valid PDF file for testing
        
        Args:
            output_path: Path where to save the PDF
            text: Text to include in the PDF
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            c = canvas.Canvas(output_path, pagesize=letter)
            width, height = letter
            
            # Add some text
            c.drawString(100, height - 100, text)
            c.drawString(100, height - 120, "Created by PDFValidator utility")
            c.drawString(100, height - 140, f"Path: {output_path}")
            
            # Save the PDF
            c.save()
            
            return True
        except Exception as e:
            logger.error(f"Error creating sample PDF: {str(e)}")
            return False

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_validator.py <pdf_file_or_directory>")
        sys.exit(1)
    
    path = sys.argv[1]
    
    if os.path.isdir(path):
        print(f"Validating all PDFs in directory: {path}")
        results = PDFValidator.validate_pdf_directory(path)
        
        valid_count = sum(1 for _, is_valid, _ in results if is_valid)
        invalid_count = len(results) - valid_count
        
        print(f"\nResults: {valid_count} valid, {invalid_count} invalid PDFs")
        
        if invalid_count > 0:
            print("\nInvalid PDFs:")
            for file_path, _, message in results:
                if not _:
                    print(f"  - {os.path.basename(file_path)}: {message}")
    else:
        is_valid, message = PDFValidator.validate_pdf(path)
        print(f"File: {path}")
        print(f"Valid: {is_valid}")
        print(f"Message: {message}")
        
        if is_valid:
            success, text = PDFValidator.extract_text_safe(path)
            if success:
                print(f"\nExtracted text (first 200 chars):\n{text[:200]}...")
            else:
                print(f"\nText extraction failed: {text}")
