"""Semantic intent router with LLM-based classification and confidence scoring."""

import re
import json
import logging
from typing import Dict, List, Optional, Any
import asyncio

from .intent_schema import get_intent_registry, IntentDefinition, SlotDefinition
from .llm_service import LLMService
from .nlp_entity_extractor import get_nlp_extractor
from ..utils.config import Settings

logger = logging.getLogger(__name__)

class SemanticIntentRouter:
    """LLM-powered intent router with confidence scoring and slot filling."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.intent_registry = get_intent_registry()
        self.settings = Settings()
        
        # Confidence thresholds
        self.high_threshold = 0.8
        self.mid_threshold = 0.6
        self.low_threshold = 0.4
        
    async def route_intent(
        self, 
        message: str, 
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Route user message to appropriate intent with confidence scoring.
        
        Args:
            message: Preprocessed user message
            conversation_context: Previous conversation context
            
        Returns:
            Dict containing intent, entities, confidence, and routing decision
        """
        if conversation_context is None:
            conversation_context = {}
            
        # Step 1: Quick rule-based pass for high-confidence patterns
        rule_result = self._apply_rule_quick_pass(message)
        if rule_result["confidence"] >= self.high_threshold:
            logger.info(f"Rule-based quick pass matched: {rule_result['intent']} (confidence: {rule_result['confidence']})")
            return rule_result
            
        # Step 2: LLM-based semantic classification
        semantic_result = await self._classify_with_llm(message, conversation_context)
        
        # Step 3: Merge rule and semantic results
        final_result = self._merge_results(rule_result, semantic_result, message)
        
        # Step 4: Apply confidence adjustments
        final_result = self._adjust_confidence(final_result, message)
        
        # Step 5: Check for missing required slots
        final_result = self._check_required_slots(final_result)
        
        logger.info(f"Final intent routing: {final_result['intent']} (confidence: {final_result['confidence']})")
        
        return final_result
    
    def _apply_rule_quick_pass(self, message: str) -> Dict[str, Any]:
        """Apply deterministic rules for high-precision cases."""
        message_lower = message.lower()
        
        # High-confidence patterns for specific intents
        high_confidence_patterns = {
            "recruiter_outreach_email": [
                r"(generate|create|write|draft).*(recruiter|recruitment).*(outreach|email).*(candidate|professional)",
                r"(recruiter|hiring).*(outreach|cold|email).*(to|for).*(candidate|professional)",
            ],
            "candidate_pitch_email": [
                r"(generate|create|write|draft).*(candidate|job seeker).*(pitch|application|email)",
                r"(application|pitch|cover letter).*(email|letter).*(to|for).*(company|employer)",
            ],
            "search_candidates": [
                r"(find|search|show|get).*(candidates|professionals).*(with|who have).*(skills?|experience)",
                r"(candidates|professionals).*(with|skilled in|experienced in)",
            ],
            "market_research": [
                r"(assess|analyze|evaluate).*(viability|market).*(for|of).*(role|position).*(in|at)",
                r"(market analysis|market research).*(for|on).*(role|position)",
            ]
        }
        
        for intent_name, patterns in high_confidence_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    # Use advanced NLP entity extraction
                    entities = self._extract_entities_advanced(message, intent_name)
                    return {
                        "intent": intent_name,
                        "entities": entities,
                        "confidence": 0.9,
                        "method": "rule_based",
                        "missing_slots": []
                    }
        
        # Medium-confidence fallback patterns
        medium_confidence_patterns = {
            "web_search": [r"(search|look up|find information|research)"],
            "general_question": [r"(what|how|why|when|where|who|help|hello|hi)"]
        }
        
        for intent_name, patterns in medium_confidence_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return {
                        "intent": intent_name,
                        "entities": {"query": message},
                        "confidence": 0.5,
                        "method": "rule_based",
                        "missing_slots": []
                    }
        
        # No rule match
        return {
            "intent": "general_question",
            "entities": {"query": message},
            "confidence": 0.2,
            "method": "rule_based",
            "missing_slots": []
        }
    
    async def _classify_with_llm(
        self, 
        message: str, 
        conversation_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use LLM to classify intent and extract entities."""
        
        # Build intent list for the prompt
        all_intents = self.intent_registry.get_all_intents()
        intent_descriptions = []
        
        for intent_name, intent_def in all_intents.items():
            synonyms_str = ", ".join(intent_def.synonyms[:3])  # Limit to first 3 synonyms
            intent_descriptions.append(f"- {intent_name}: {intent_def.description} (synonyms: {synonyms_str})")
        
        intent_list = "\n".join(intent_descriptions)
        
        # Include conversation context hints
        context_hint = ""
        if conversation_context.get("last_intent"):
            context_hint = f"\nPrevious intent: {conversation_context['last_intent']}"
        if conversation_context.get("last_role_discussed"):
            context_hint += f"\nPrevious role discussed: {conversation_context['last_role_discussed']}"
        
        prompt = f"""
Classify the user's intent and extract relevant entities from their message.

User message: "{message}"
{context_hint}

Available intents:
{intent_list}

Instructions:
1. Choose the most appropriate intent from the list above
2. Extract relevant entities (role, skills, location, company, etc.)
3. IMPORTANT: Preserve role names EXACTLY as written. Do NOT expand abbreviations like "Gen AI" to "Generative Artificial Intelligence" or "AI" to "Artificial Intelligence"
4. Provide a confidence score from 0.0 to 1.0
5. Give a brief rationale for your choice

Respond with ONLY valid JSON in this exact format:
{{
    "intent": "intent_name",
    "entities": {{
        "role": "extracted role if any",
        "skills": "extracted skills if any", 
        "location": "extracted location if any",
        "company": "extracted company if any",
        "query": "general query if applicable"
    }},
    "confidence": 0.8,
    "rationale": "Brief explanation of why this intent was chosen"
}}

Remove any entities that are null or empty strings. Only include entities that are actually present in the message.
"""

        try:
            # Use Meta Llama for intent classification when available
            model_override = None
            try:
                from backend.utils.config import Settings
                settings = Settings()
                if getattr(settings, 'openrouter_enabled', False):
                    model_override = getattr(settings, 'openrouter_default_model', None)
            except Exception:
                pass
            
            response = await self.llm_service.generate_text_async(
                prompt=prompt,
                task_type="classification",
                model=model_override,
                system_message="You are an expert intent classifier. Always respond with valid JSON only."
            )
            
            # Clean and parse the response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            result = json.loads(response)
            
            # Validate the result
            if "intent" not in result or "confidence" not in result:
                raise ValueError("Missing required fields in LLM response")
                
            # Clean entities - remove empty values
            entities = result.get("entities", {})
            cleaned_entities = {k: v for k, v in entities.items() if v and str(v).strip()}
            
            # Enhance with advanced NLP extraction
            nlp_entities = self._extract_entities_advanced(message, result["intent"])
            
            # Merge LLM and NLP entities (NLP takes priority for better accuracy)
            final_entities = {**cleaned_entities, **nlp_entities}
            
            result["entities"] = final_entities
            result["method"] = "llm_semantic"
            result["missing_slots"] = []
            
            return result
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse LLM intent classification response: {e}")
            logger.error(f"Raw response: {response}")
            
            # Fallback to general question
            return {
                "intent": "general_question",
                "entities": {"query": message},
                "confidence": 0.3,
                "method": "llm_fallback",
                "rationale": f"LLM parsing failed: {str(e)}",
                "missing_slots": []
            }
    
    def _merge_results(
        self, 
        rule_result: Dict[str, Any], 
        semantic_result: Dict[str, Any], 
        message: str
    ) -> Dict[str, Any]:
        """Merge rule-based and semantic results intelligently."""
        
        # If rule-based has high confidence, prefer it
        if rule_result["confidence"] >= self.high_threshold:
            return rule_result
            
        # If semantic has much higher confidence, prefer it
        if semantic_result["confidence"] > rule_result["confidence"] + 0.2:
            return semantic_result
            
        # If both have similar confidence, prefer the one with more entities
        rule_entity_count = len([v for v in rule_result["entities"].values() if v])
        semantic_entity_count = len([v for v in semantic_result["entities"].values() if v])
        
        if semantic_entity_count > rule_entity_count:
            return semantic_result
        else:
            # Merge entities from both results
            merged_entities = rule_result["entities"].copy()
            for key, value in semantic_result["entities"].items():
                if value and not merged_entities.get(key):
                    merged_entities[key] = value
                    
            return {
                "intent": rule_result["intent"],
                "entities": merged_entities,
                "confidence": max(rule_result["confidence"], semantic_result["confidence"]),
                "method": "hybrid",
                "missing_slots": []
            }
    
    def _adjust_confidence(self, result: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Apply confidence adjustments based on negative keywords and other factors."""
        
        intent_name = result["intent"]
        intent_def = self.intent_registry.get_intent(intent_name)
        
        if not intent_def:
            return result
            
        confidence = result["confidence"]
        message_lower = message.lower()
        
        # Penalize if negative keywords are present
        for negative_keyword in intent_def.negative_keywords:
            if negative_keyword.lower() in message_lower:
                confidence -= 0.2
                logger.debug(f"Penalized confidence for negative keyword '{negative_keyword}'")
        
        # Boost if synonyms match well
        synonym_matches = sum(1 for synonym in intent_def.synonyms if synonym.lower() in message_lower)
        if synonym_matches > 0:
            confidence += min(0.1 * synonym_matches, 0.3)
            logger.debug(f"Boosted confidence for {synonym_matches} synonym matches")
        
        # Ensure confidence stays within bounds
        confidence = max(0.0, min(1.0, confidence))
        result["confidence"] = confidence
        
        return result
    
    def _check_required_slots(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Check for missing required slots and add to missing_slots list."""
        
        intent_name = result["intent"]
        intent_def = self.intent_registry.get_intent(intent_name)
        
        if not intent_def:
            return result
            
        entities = result["entities"]
        missing_slots = []
        
        for slot_def in intent_def.required_slots:
            slot_value = entities.get(slot_def.name)
            if not slot_value or (isinstance(slot_value, str) and not slot_value.strip()):
                missing_slots.append(slot_def.name)
        
        result["missing_slots"] = missing_slots
        
        # Lower confidence if required slots are missing
        if missing_slots:
            penalty = min(0.1 * len(missing_slots), 0.4)
            result["confidence"] = max(0.1, result["confidence"] - penalty)
            logger.debug(f"Reduced confidence by {penalty} for {len(missing_slots)} missing required slots")
        
        return result
    
    def _extract_entities_from_pattern(
        self, 
        message: str, 
        pattern: str, 
        intent_name: str
    ) -> Dict[str, Any]:
        """Extract entities using regex pattern matching."""
        
        entities = {}
        
        # Common entity extraction patterns
        entity_patterns = {
            "role": [
                r"(?:for|regarding|about|concerning)\s+(?:a\s+|an\s+)?([a-zA-Z\s]+?)(?:\s+(?:role|position|job|candidate|professional))",
                r"(?:role|position|job)\s+(?:of\s+|as\s+)?([a-zA-Z\s]+)",
                r"([a-zA-Z\s]+?)\s+(?:engineer|developer|scientist|analyst|manager|specialist|role|position)",
                r"(?:data|software|machine learning|ai|ml|backend|frontend|full stack|devops|cloud)\s+(?:engineer|engineering|developer|scientist|analyst)",
                r"(?:senior|junior|lead|principal|staff)\s+([a-zA-Z\s]+?)(?:\s+(?:engineer|developer|scientist|analyst|manager))",
                r"(?:generate|create|write).*(?:email|outreach).*(?:for|to)\s+([a-zA-Z\s]+?)(?:\s|$|role|position)"
            ],
            "skills": [
                r"(?:with|who have|knowing|skilled in|experienced in)\s+([a-zA-Z0-9\s,]+?)(?:\s|$|\.|\?)",
                r"(?:skills?|experience|expertise)\s+(?:in\s+|with\s+)?([a-zA-Z0-9\s,]+?)(?:\s|$|\.|\?)"
            ],
            "location": [
                r"(?:in|at|from|to)\s+([A-Z][a-zA-Z\s]+?)(?:\s|$|,|\?)",
                r"([A-Z][a-zA-Z\s]+?)\s+(?:area|city|region|market)"
            ],
            "company": [
                r"(?:at|for|with|from)\s+([A-Z][a-zA-Z\s&]+?)(?:\s|$|,|\?)",
                r"company\s+([A-Z][a-zA-Z\s&]+?)(?:\s|$|,|\?)"
            ]
        }
        
        for entity_type, patterns in entity_patterns.items():
            for entity_pattern in patterns:
                match = re.search(entity_pattern, message, re.IGNORECASE)
                if match:
                    extracted_value = match.group(1).strip()
                    # Clean up common extraction issues
                    if entity_type == "role":
                        # Handle compound roles like "data engineering" -> "data engineer"
                        if extracted_value.endswith("engineering"):
                            extracted_value = extracted_value.replace("engineering", "engineer")
                        # Remove common filler words
                        extracted_value = re.sub(r'\b(a|an|the)\b', '', extracted_value).strip()
                        # Normalize whitespace
                        extracted_value = ' '.join(extracted_value.split())
                    entities[entity_type] = extracted_value
                    break
        
        # If no specific entities found, add the whole message as query for general intents
        if not entities and intent_name in ["web_search", "general_question"]:
            entities["query"] = message
            
        return entities
    
    def _extract_entities_advanced(self, message: str, intent_name: str) -> Dict[str, Any]:
        """Extract entities using advanced NLP techniques."""
        try:
            nlp_extractor = get_nlp_extractor()
            nlp_entities = nlp_extractor.extract_entities(message)
            
            # Also use the legacy regex extraction as fallback
            regex_entities = self._extract_entities_from_pattern(message, "", intent_name)
            
            # Merge results, prioritizing NLP extraction
            final_entities = {**regex_entities, **nlp_entities}
            
            logger.debug(f"Advanced entity extraction for '{message}': {final_entities}")
            return final_entities
            
        except Exception as e:
            logger.warning(f"Advanced NLP extraction failed: {e}, falling back to regex")
            return self._extract_entities_from_pattern(message, "", intent_name)

    def generate_clarifying_question(
        self, 
        intent_name: str, 
        missing_slots: List[str],
        entities: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate a clarifying question for missing required slots."""
        
        intent_def = self.intent_registry.get_intent(intent_name)
        if not intent_def or not missing_slots:
            return None
            
        # Find the first missing slot that has a clarifying question
        for missing_slot in missing_slots:
            for question in intent_def.clarifying_questions:
                if question.slot_name == missing_slot:
                    return {
                        "question": question.question,
                        "slot_name": question.slot_name,
                        "options": question.options,
                        "context_hint": question.context_hint
                    }
        
        # Generate a generic clarifying question for the first missing slot
        missing_slot = missing_slots[0]
        slot_def = None
        
        for slot in intent_def.required_slots + intent_def.optional_slots:
            if slot.name == missing_slot:
                slot_def = slot
                break
                
        if slot_def:
            question_text = f"What {slot_def.description.lower() if slot_def.description else missing_slot} would you like me to use?"
            
            return {
                "question": question_text,
                "slot_name": missing_slot,
                "options": slot_def.options,
                "context_hint": slot_def.description
            }
        
        return None
