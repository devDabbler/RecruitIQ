import pytest
from unittest.mock import AsyncMock, patch
from backend.services.resume_service_new import ResumeService

@pytest.mark.asyncio
async def test_parse_resume_success():
    # Create mock instances
    mock_nebius_instance = AsyncMock()
    mock_nebius_instance.parse_resume.return_value = {
        'experience': [{'title': 'Software Engineer', 'company': 'Tech Corp'}],
        'skills': ['Python', 'FastAPI']
    }
    
    mock_nlp_instance = AsyncMock()
    
    # Mock the NebiusAIParser and NLPExtractor constructors
    with patch('backend.services.resume_service_new.NebiusAIParser') as mock_nebius_parser, \
         patch('backend.services.resume_service_new.NLPExtractor') as mock_nlp_extractor:
        
        # Set up mock return values
        mock_nebius_parser.return_value = mock_nebius_instance
        mock_nlp_extractor.return_value = mock_nlp_instance
        
        # Create service instance
        service = ResumeService()
        
        # Test parsing
        result = await service.parse_resume("Sample resume text")
        
        # Assertions
        assert result is not None
        assert 'experience' in result
        assert 'skills' in result
        
        # Verify Nebius AI parser was called
        mock_nebius_instance.parse_resume.assert_called_once_with("Sample resume text", "")

@pytest.mark.asyncio
async def test_parse_resume_fallback_to_nlp_on_exception():
    # Create mock instances
    mock_nebius_instance = AsyncMock()
    mock_nebius_instance.parse_resume.side_effect = Exception("Nebius AI failed")
    
    mock_nlp_instance = AsyncMock()
    mock_nlp_instance.extract.return_value = {
        'experience': [{'title': 'Data Analyst', 'company': 'Data Corp'}],
        'skills': ['SQL', 'Excel']
    }
    
    # Mock the NebiusAIParser and NLPExtractor constructors
    with patch('backend.services.resume_service_new.NebiusAIParser') as mock_nebius_parser, \
         patch('backend.services.resume_service_new.NLPExtractor') as mock_nlp_extractor:
        
        # Set up mock return values
        mock_nebius_parser.return_value = mock_nebius_instance
        mock_nlp_extractor.return_value = mock_nlp_instance
        
        # Create service instance
        service = ResumeService()
        
        # Test parsing
        result = await service.parse_resume("Sample resume text")
        
        # Assertions
        assert result is not None
        assert 'experience' in result
        assert 'skills' in result
        
        # Verify Nebius AI parser was called and failed
        mock_nebius_instance.parse_resume.assert_called_once_with("Sample resume text", "")
        # Verify NLP extractor was called as fallback
        mock_nlp_instance.extract.assert_called_once_with("Sample resume text", "")

@pytest.mark.asyncio
async def test_parse_resume_fallback_to_nlp_on_empty_result():
    # Create mock instances
    mock_nebius_instance = AsyncMock()
    mock_nebius_instance.parse_resume.return_value = {}
    
    mock_nlp_instance = AsyncMock()
    mock_nlp_instance.extract.return_value = {
        'experience': [{'title': 'Data Analyst', 'company': 'Data Corp'}],
        'skills': ['SQL', 'Excel']
    }
    
    # Mock the NebiusAIParser and NLPExtractor constructors
    with patch('backend.services.resume_service_new.NebiusAIParser') as mock_nebius_parser, \
         patch('backend.services.resume_service_new.NLPExtractor') as mock_nlp_extractor:
        
        # Set up mock return values
        mock_nebius_parser.return_value = mock_nebius_instance
        mock_nlp_extractor.return_value = mock_nlp_instance
        
        # Create service instance
        service = ResumeService()
        
        # Test parsing
        result = await service.parse_resume("Sample resume text")
        
        # Assertions
        assert result is not None
        assert 'experience' in result
        assert 'skills' in result
        
        # Verify Nebius AI parser was called
        mock_nebius_instance.parse_resume.assert_called_once_with("Sample resume text", "")
        # Verify NLP extractor was called as fallback
        mock_nlp_instance.extract.assert_called_once_with("Sample resume text", "")
