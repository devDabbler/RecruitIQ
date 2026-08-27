import asyncio
import logging
from backend.services.llm_service import get_llm_service
from backend.utils.config import get_settings

logging.basicConfig(level=logging.INFO)

async def main():
    settings = get_settings()
    print('Configured OpenRouter model:', settings.openrouter_default_model)

    llm = get_llm_service()
    # Use a small prompt
    prompt = "Say hello in two words."
    try:
        # Use the async generate_text_async method provided by LLMService
        resp = await llm.generate_text_async(prompt)
        print('LLM response:', resp)
    except Exception as e:
        print('LLM call failed:', e)

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
