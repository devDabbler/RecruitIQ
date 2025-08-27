"""
Document Preview Utility for RecruitIQ

This module provides functions to preview PDF and DOCX files in Streamlit.
It supports different rendering options based on file type and size.
"""

import streamlit as st
import base64
import tempfile
from pathlib import Path
import logging
import requests
from typing import Optional, Union, BinaryIO, Dict, Any

# Import required packages for document handling
try:
    import mammoth  # For DOCX to HTML conversion
    import docx  # For plain text extraction from DOCX
    from streamlit_pdf_viewer import pdf_viewer  # For PDF viewing
except ImportError as e:
    st.error(f"Missing required package: {e}. Please install with pip.")

# Configure logging
logger = logging.getLogger(__name__)

def preview_file(file_content: Union[bytes, BinaryIO], file_name: str = None, height: int = 900) -> None:
    """
    Preview a document file (PDF or DOCX) in Streamlit.
    
    Args:
        file_content: The binary content of the file as bytes or a file-like object
        file_name: The name of the file (used to determine file type)
        height: The height of the preview component in pixels
    
    Returns:
        None: The function renders the preview directly in the Streamlit app
    """
    if not file_content:
        st.info("👈 No file content provided.")
        return
    
    # Convert file-like object to bytes if needed
    if hasattr(file_content, 'read'):
        file_content = file_content.read()
    
    # Determine file type from name or try to detect from content
    file_type = None
    if file_name:
        file_type = Path(file_name).suffix.lower()
    
    if not file_type:
        # Try to detect file type from content
        if file_content.startswith(b'%PDF'):
            file_type = '.pdf'
        elif file_content.startswith(b'PK\x03\x04'):  # DOCX files are ZIP archives
            file_type = '.docx'
        else:
            st.error("Could not determine file type. Please provide a file with a valid extension.")
            return
    
    # Handle PDF files
    if file_type == '.pdf':
        try:
            # Use streamlit-pdf-viewer for robust PDF viewing
            pdf_viewer(file_content, width="100%", height=height)
        except Exception as e:
            logger.error(f"Error using pdf_viewer: {e}")
            
            # Fallback to base64 embedding for small PDFs
            try:
                file_size = len(file_content)
                if file_size <= 2 * 1024 * 1024:  # 2MB limit
                    base64_pdf = base64.b64encode(file_content).decode()
                    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="{height}px" type="application/pdf">'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                else:
                    st.error("PDF is too large for inline display. Please download the file to view it.")
            except Exception as e2:
                logger.error(f"Error using base64 fallback: {e2}")
                st.error(f"Could not display PDF: {e2}")
    
    # Handle DOCX files
    elif file_type == '.docx':
        try:
            # Save to temporary file (mammoth requires a file path)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name
            
            try:
                # Convert DOCX to HTML
                html = mammoth.convert_to_html(Path(tmp_path)).value
                
                # Display in an iframe with sandboxing for security
                st.components.v1.html(
                    f"""
                    <iframe sandbox="allow-scripts" style="width: 100%; height: {height}px; border: 1px solid #ccc; border-radius: 5px; padding: 0;">
                        <html>
                            <head>
                                <style>
                                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                                    h1, h2, h3 {{ color: #333; }}
                                    table {{ border-collapse: collapse; width: 100%; }}
                                    th, td {{ border: 1px solid #ddd; padding: 8px; }}
                                    th {{ background-color: #f2f2f2; }}
                                </style>
                            </head>
                            <body>{html}</body>
                        </html>
                    </iframe>
                    """, 
                    height=height,
                    scrolling=True
                )
            except Exception as e:
                logger.error(f"Error converting DOCX to HTML: {e}")
                
                # Fallback to plain text extraction
                try:
                    doc = docx.Document(tmp_path)
                    text = "\n".join(p.text for p in doc.paragraphs)
                    st.text_area("Document text", text, height=height//2)
                except Exception as e2:
                    logger.error(f"Error extracting text from DOCX: {e2}")
                    st.error(f"Could not display DOCX: {e2}")
            finally:
                # Clean up temporary file
                Path(tmp_path).unlink(missing_ok=True)
        
        except Exception as e:
            logger.error(f"Error processing DOCX file: {e}")
            st.error(f"Could not process DOCX file: {e}")
    
    else:
        st.error(f"Unsupported file type: {file_type}. Only PDF and DOCX are supported.")

def fetch_and_preview_resume(resume_id: str, api_url: str, height: int = 900) -> bool:
    """
    Fetch a resume from the API and preview it.
    
    Args:
        resume_id: The ID of the resume to fetch
        api_url: The base URL of the API
        height: The height of the preview component in pixels
    
    Returns:
        bool: True if the resume was successfully fetched and previewed, False otherwise
    """
    if not resume_id:
        st.info("No resume ID provided.")
        return False
    
    try:
        # Prepare the API URL
        if not api_url.rstrip('/').endswith('/api'):
            api_url = api_url.rstrip('/') + '/api'
        
        # First check if the resume exists
        check_url = f"{api_url.rstrip('/')}/resume/{resume_id}/view"
        check_resp = requests.head(check_url)
        
        if check_resp.status_code == 404:
            error_msg = "The resume file could not be found in storage."
            try:
                # Try to get a more specific error message from the response
                error_detail = check_resp.json().get("detail", "")
                if error_detail:
                    error_msg = error_detail
            except:
                pass
            st.error(f"⚠️ {error_msg}")
            st.info("This usually happens when a resume is referenced in the database but the actual file is missing. Please upload a new resume for this candidate.")
            return False
        
        # Raise for other types of errors
        check_resp.raise_for_status()
        
        # Get file info to determine file name and type
        preview_resp = requests.get(f"{api_url.rstrip('/')}/resume/{resume_id}/preview")
        preview_resp.raise_for_status()
        file_info = preview_resp.json()
        
        # Fetch the actual file content
        with st.spinner("Loading resume..."):
            content_resp = requests.get(check_url, stream=True)
            content_resp.raise_for_status()
            
            # Preview the file
            preview_file(
                file_content=content_resp.content,
                file_name=file_info.get("file_name", f"resume_{resume_id}.pdf"),
                height=height
            )
        
        return True
    
    except requests.exceptions.HTTPError as e:
        if hasattr(e, 'response') and e.response.status_code == 404:
            st.error(f"The resume file could not be found in storage.")
            st.info("This usually happens when a resume is referenced in the database but the actual file is missing.")
        else:
            st.error(f"Error fetching resume: HTTP {e.response.status_code if hasattr(e, 'response') else 'Unknown'}")
    except Exception as e:
        st.error(f"Error fetching resume: {e}")
    
    return False
