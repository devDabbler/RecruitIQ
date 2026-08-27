import pytest
from unittest.mock import MagicMock
from backend.utils.resume_parsing.processors.document_processor import DocumentProcessor
from backend.utils.resume_parsing.processors.ocr_processor import OCRProcessor
from backend.utils.resume_parsing.processors.section_processor import SectionProcessor
from backend.utils.resume_parsing.processors.base_processor import BaseProcessor
import os

@pytest.fixture
def resume_pdf_path():
    # Adjust the path as needed if test is run from a different directory
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../Clint_Forest_Resume.pdf'))

class TestDocumentProcessor:
    @pytest.mark.asyncio
    async def test_process(self, resume_pdf_path):
        """Test DocumentProcessor.process extracts non-empty text from a real PDF resume."""
        if not os.path.exists(resume_pdf_path):
            import pytest
            pytest.skip('Test PDF file not found, skipping test.')
        processor = DocumentProcessor()
        text = await processor.process(resume_pdf_path)
        assert isinstance(text, str)
        assert len(text.strip()) > 50  # Should extract a reasonable amount of text

class TestOCRProcessor:
    @pytest.mark.skip(reason="No image resume provided for OCR test.")
    def test_process(self):
        """Test OCRProcessor.process with an image resume (skipped)."""
        processor = OCRProcessor()
        # Would test with an image file if available
        pass

class TestSectionProcessor:
    @pytest.mark.asyncio
    async def test_process(self):
        """Test SectionProcessor.process extracts sections from sample resume text."""
        processor = SectionProcessor()
        sample_text = """
        EXPERIENCE\nSoftware Engineer at Acme Corp\n2018-2022\nEDUCATION\nB.S. Computer Science, University of Example\n2014-2018\n"""
        sections = await processor.process(sample_text)
        # Accept either upper or lower case keys
        keys = [k.lower() for k in sections.keys()]
        assert 'experience' in keys
        assert 'education' in keys

class TestBaseProcessor:
    @pytest.mark.skip(reason="BaseProcessor is abstract and should not be instantiated.")
    def test_process_not_implemented(self):
        pass 