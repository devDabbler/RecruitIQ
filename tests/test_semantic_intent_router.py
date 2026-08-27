"""Tests for the semantic intent router."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
import json

from backend.services.semantic_intent_router import SemanticIntentRouter
from backend.services.intent_schema import get_intent_registry
from backend.services.llm_service import LLMService


class TestSemanticIntentRouter:
    """Test cases for the SemanticIntentRouter class."""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service."""
        mock = Mock(spec=LLMService)
        mock.generate_text_async = AsyncMock()
        return mock
    
    @pytest.fixture
    def router(self, mock_llm_service):
        """Create a SemanticIntentRouter instance."""
        return SemanticIntentRouter(mock_llm_service)
    
    def test_initialization(self, router):
        """Test router initialization."""
        assert router.llm_service is not None
        assert router.intent_registry is not None
        assert router.high_threshold == 0.8
        assert router.mid_threshold == 0.6
        assert router.low_threshold == 0.4
    
    @pytest.mark.asyncio
    async def test_rule_quick_pass_high_confidence(self, router):
        """Test rule-based quick pass for high-confidence patterns."""
        message = "generate recruiter outreach email to candidates for software engineer"
        result = await router.route_intent(message)
        
        assert result["intent"] == "recruiter_outreach_email"
        assert result["confidence"] >= 0.8
        assert result["method"] == "rule_based"
        assert "role" in result["entities"]
    
    @pytest.mark.asyncio
    async def test_travel_time_pattern(self, router):
        """Test travel time pattern recognition."""
        message = "how long does it take to travel from Boston to New York"
        result = await router.route_intent(message)
        
        assert result["intent"] == "travel_time"
        assert result["confidence"] >= 0.8
        assert "origin" in result["entities"] or "destination" in result["entities"]
    
    @pytest.mark.asyncio
    async def test_llm_classification(self, router, mock_llm_service):
        """Test LLM-based classification."""
        # Mock LLM response
        mock_response = json.dumps({
            "intent": "search_candidates",
            "entities": {"skills": "Python", "role": "developer"},
            "confidence": 0.85,
            "rationale": "User is looking for candidates with Python skills"
        })
        mock_llm_service.generate_text_async.return_value = mock_response
        
        message = "find developers with Python experience"
        result = await router.route_intent(message)
        
        assert result["intent"] == "search_candidates"
        assert result["confidence"] >= 0.8
        assert result["entities"]["skills"] == "Python"
        assert result["method"] == "llm_semantic"
    
    @pytest.mark.asyncio
    async def test_confidence_adjustment_negative_keywords(self, router):
        """Test confidence adjustment with negative keywords."""
        # This should match recruiter_outreach_email but get penalized for "application"
        message = "generate recruiter outreach email about job application"
        result = await router.route_intent(message)
        
        # Should still match but with reduced confidence due to negative keyword
        assert result["intent"] == "recruiter_outreach_email"
        # Confidence should be reduced due to negative keyword "application"
        assert result["confidence"] < 0.9
    
    @pytest.mark.asyncio
    async def test_missing_slots_detection(self, router):
        """Test detection of missing required slots."""
        message = "generate recruiter outreach email"  # Missing role
        result = await router.route_intent(message)
        
        assert result["intent"] == "recruiter_outreach_email"
        assert "role" in result["missing_slots"]
        # Confidence should be reduced due to missing required slot
        assert result["confidence"] < 0.9
    
    def test_generate_clarifying_question(self, router):
        """Test clarifying question generation."""
        intent_name = "recruiter_outreach_email"
        missing_slots = ["role"]
        entities = {}
        
        question = router.generate_clarifying_question(intent_name, missing_slots, entities)
        
        assert question is not None
        assert question["slot_name"] == "role"
        assert "role" in question["question"].lower()
    
    @pytest.mark.asyncio
    async def test_entity_extraction(self, router):
        """Test entity extraction from patterns."""
        message = "find candidates with React and Node.js skills in San Francisco"
        result = await router.route_intent(message)
        
        assert result["intent"] == "search_candidates"
        entities = result["entities"]
        
        # Should extract skills and location
        assert "skills" in entities or "location" in entities
    
    @pytest.mark.asyncio
    async def test_fallback_to_general_question(self, router, mock_llm_service):
        """Test fallback to general question for unclear intents."""
        # Mock LLM to return low confidence
        mock_response = json.dumps({
            "intent": "general_question",
            "entities": {"query": "unclear message"},
            "confidence": 0.2,
            "rationale": "Intent is unclear"
        })
        mock_llm_service.generate_text_async.return_value = mock_response
        
        message = "unclear message that doesn't match any pattern"
        result = await router.route_intent(message)
        
        assert result["intent"] == "general_question"
        assert result["confidence"] <= 0.5


class TestIntentSchema:
    """Test cases for the intent schema."""
    
    def test_intent_registry_initialization(self):
        """Test that intent registry initializes properly."""
        registry = get_intent_registry()
        
        assert registry is not None
        intents = registry.get_all_intents()
        
        # Check that key intents are present
        expected_intents = [
            "recruiter_outreach_email",
            "candidate_pitch_email", 
            "search_candidates",
            "market_research",
            "travel_time",
            "general_question"
        ]
        
        for intent_name in expected_intents:
            assert intent_name in intents
            intent_def = intents[intent_name]
            assert intent_def.name == intent_name
            assert len(intent_def.synonyms) > 0
    
    def test_intent_definition_structure(self):
        """Test that intent definitions have proper structure."""
        registry = get_intent_registry()
        intent_def = registry.get_intent("recruiter_outreach_email")
        
        assert intent_def is not None
        assert intent_def.description
        assert len(intent_def.synonyms) > 0
        assert len(intent_def.required_slots) > 0
        assert intent_def.priority > 0
        assert 0 <= intent_def.confidence_threshold <= 1
    
    def test_slot_definitions(self):
        """Test slot definitions in intents."""
        registry = get_intent_registry()
        intent_def = registry.get_intent("recruiter_outreach_email")
        
        # Should have role as required slot
        role_slot = None
        for slot in intent_def.required_slots:
            if slot.name == "role":
                role_slot = slot
                break
        
        assert role_slot is not None
        assert role_slot.required is True
        assert role_slot.description
    
    def test_clarifying_questions(self):
        """Test clarifying questions in intent definitions."""
        registry = get_intent_registry()
        intent_def = registry.get_intent("recruiter_outreach_email")
        
        assert len(intent_def.clarifying_questions) > 0
        
        role_question = None
        for question in intent_def.clarifying_questions:
            if question.slot_name == "role":
                role_question = question
                break
        
        assert role_question is not None
        assert role_question.question
        assert role_question.slot_name == "role"


class TestIntentDetectionIntegration:
    """Integration tests for the complete intent detection system."""
    
    @pytest.fixture
    def mock_intent_processor(self):
        """Create a mock intent processor with semantic router."""
        from backend.services.intent_processor import IntentProcessor
        
        mock_llm = Mock(spec=LLMService)
        mock_llm.generate_text_async = AsyncMock()
        
        processor = IntentProcessor(mock_llm)
        processor.semantic_router = SemanticIntentRouter(mock_llm)
        
        return processor, mock_llm
    
    @pytest.mark.asyncio
    async def test_confidence_gating_high_confidence(self, mock_intent_processor):
        """Test high confidence path - should execute directly."""
        processor, mock_llm = mock_intent_processor
        
        # Mock high confidence LLM response
        mock_response = json.dumps({
            "intent": "search_candidates",
            "entities": {"skills": "Python"},
            "confidence": 0.9,
            "rationale": "Clear candidate search request"
        })
        mock_llm.generate_text_async.return_value = mock_response
        
        message = "find Python developers"
        result = await processor._apply_confidence_gating(
            {"intent": "search_candidates", "entities": {"skills": "Python"}, "confidence": 0.9, "missing_slots": []},
            message,
            {}
        )
        
        assert result["intent"] == "search_candidates"
        assert not result.get("requires_clarification", False)
    
    @pytest.mark.asyncio
    async def test_confidence_gating_medium_confidence(self, mock_intent_processor):
        """Test medium confidence path - should execute with soft confirmation."""
        processor, mock_llm = mock_intent_processor
        
        message = "find developers"
        result = await processor._apply_confidence_gating(
            {"intent": "search_candidates", "entities": {}, "confidence": 0.7, "missing_slots": []},
            message,
            {}
        )
        
        assert result["intent"] == "search_candidates"
        assert result.get("soft_confirmation", False)
        assert "confirmation_prompt" in result
    
    @pytest.mark.asyncio
    async def test_confidence_gating_low_confidence(self, mock_intent_processor):
        """Test low confidence path - should ask for clarification."""
        processor, mock_llm = mock_intent_processor
        
        message = "unclear request"
        result = await processor._apply_confidence_gating(
            {"intent": "general_question", "entities": {}, "confidence": 0.3, "missing_slots": []},
            message,
            {}
        )
        
        assert result.get("requires_clarification", False) or result["intent"] == "clarification_needed"
    
    @pytest.mark.asyncio
    async def test_missing_slots_clarification(self, mock_intent_processor):
        """Test clarification for missing required slots."""
        processor, mock_llm = mock_intent_processor
        
        message = "generate recruiter email"
        result = await processor._apply_confidence_gating(
            {"intent": "recruiter_outreach_email", "entities": {}, "confidence": 0.8, "missing_slots": ["role"]},
            message,
            {}
        )
        
        assert result["intent"] == "clarification_needed"
        assert result.get("requires_clarification", False)
        assert "clarification_question" in result
        assert "role" in result["clarification_question"].lower()


if __name__ == "__main__":
    pytest.main([__file__])
