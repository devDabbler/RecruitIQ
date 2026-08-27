import asyncio
import re
import sys
sys.path.append('.')
from services.dynamic_intent_processor import DynamicIntentProcessor

async def debug_pattern_matching():
    query = 'If a candidate is considering a relocation from Kentucky to Seattle, what is the cost of living difference?'
    
    # Initialize the processor
    processor = DynamicIntentProcessor()
    
    print(f"Testing query: {query}")
    print("=" * 60)
    
    # Test pattern-based detection directly
    print("1. Testing pattern-based detection:")
    pattern_intents = await processor._pattern_based_detection(query)
    print(f"   Found {len(pattern_intents)} intents from pattern detection:")
    for intent in pattern_intents:
        print(f"   - {intent.name}: confidence={intent.confidence}, signals={intent.context_signals}")
    
    print("\n2. Testing individual patterns:")
    message_lower = query.lower()
    
    # Test travel_planning patterns
    travel_patterns = [
        r"\b(?:travel|commute|route|directions|transportation|how to get|best way to|distance|duration)\b",
        r"\b(?:relocation|relocate|moving|move)\b",
        r"\b(?:cost of living|living cost|expenses|housing cost)\b",
        r"\b(?:from|to|between)\s+\w+",
        r"\b(?:airport|station|downtown|uptown)\b"
    ]
    
    print("   Travel planning patterns:")
    for i, pattern in enumerate(travel_patterns):
        match = re.search(pattern, message_lower)
        if match:
            print(f"   - Pattern {i+1}: MATCHED '{match.group()}'")
        else:
            print(f"   - Pattern {i+1}: NO MATCH")
    
    print("\n3. Testing full detection pipeline:")
    full_intent = await processor.detect_intent(query, "test_user")
    print(f"   Final intent: {full_intent.name}")
    print(f"   Confidence: {full_intent.confidence}")
    print(f"   Context signals: {full_intent.context_signals}")
    print(f"   Metadata: {full_intent.metadata}")

if __name__ == "__main__":
    asyncio.run(debug_pattern_matching()) 