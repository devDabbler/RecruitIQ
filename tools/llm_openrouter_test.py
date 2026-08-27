import asyncio
import logging
from backend.services.llm_service import get_llm_service
from backend.utils.config import get_settings

logging.basicConfig(level=logging.INFO)

async def run_test():
    settings = get_settings()
    service = get_llm_service(settings)
    prompt = "Say hello and identify the model used in two words."
    model = settings.openrouter_default_model
    logging.info(f"Testing generate_text_async with model override: {model}")
    resp = await service.generate_text_async(prompt=prompt, model=model)
    logging.info(f"Response (len={len(resp) if resp else 0}): {resp}")

if __name__ == '__main__':
    asyncio.run(run_test())
