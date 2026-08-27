import pytest
from unittest.mock import patch
import logging
from backend.utils.logging import log_parsing_errors

def test_log_parsing_errors():
    # Test logging with error and metadata
    with patch('backend.utils.logging.logger') as mock_logger:
        # Create a sample error
        sample_error = Exception("Test parsing error")
        sample_text = "Sample resume text for testing"
        sample_metadata = {"file_name": "test_resume.pdf", "user_id": "123"}
        
        # Call the function
        log_parsing_errors(sample_error, sample_text, sample_metadata)
        
        # Verify logger.error was called with expected message
        mock_logger.error.assert_called_once()
        
        # Get the call arguments
        call_args = mock_logger.error.call_args[0][0]
        
        # Verify key components are in the log message
        assert "Resume parsing failed" in call_args
        assert "Test parsing error" in call_args
        assert "Sample resume text for testing" in call_args
        assert "test_resume.pdf" in call_args

def test_log_parsing_errors_no_metadata():
    # Test logging with error but no metadata
    with patch('backend.utils.logging.logger') as mock_logger:
        # Create a sample error
        sample_error = Exception("Test parsing error")
        sample_text = "Sample resume text for testing"
        
        # Call the function
        log_parsing_errors(sample_error, sample_text)
        
        # Verify logger.error was called with expected message
        mock_logger.error.assert_called_once()
        
        # Get the call arguments
        call_args = mock_logger.error.call_args[0][0]
        
        # Verify key components are in the log message
        assert "Resume parsing failed" in call_args
        assert "Test parsing error" in call_args
        assert "Sample resume text for testing" in call_args
        assert "metadata" in call_args
