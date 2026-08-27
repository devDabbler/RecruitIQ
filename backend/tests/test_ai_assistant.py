import pytest
from unittest.mock import AsyncMock, patch
from backend.services.ai_assistant import AIAssistant

@pytest.mark.asyncio
async def test_analyze_resume_for_job():
    # Mock the ResumeService
    with patch('backend.services.ai_assistant.ResumeService') as mock_resume_service_class:
        # Set up mock return values
        mock_resume_service = AsyncMock()
        mock_resume_service.parse_resume.return_value = {
            'experience': [{'title': 'Software Engineer', 'company': 'Tech Corp'}],
            'skills': ['Python', 'FastAPI']
        }
        mock_resume_service_class.return_value = mock_resume_service
        
        # Create assistant instance
        assistant = AIAssistant()
        
        # Test analysis
        result = await assistant.analyze_resume_for_job(
            "Sample resume text", 
            "Looking for Python developer with FastAPI experience"
        )
        
        # Assertions
        assert result is not None
        assert 'resume_data' in result
        assert 'job_analysis' in result
        assert 'match_score' in result
        
        # Verify the resume service was called
        mock_resume_service.parse_resume.assert_called_once_with("Sample resume text")
        
        # Verify the match score is a float
        assert isinstance(result['match_score'], float)
