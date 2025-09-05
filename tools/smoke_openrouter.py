"""
One-shot smoke test to exercise the OpenRouter path when enabled.
This script is intentionally minimal and safe:
- It uses the project Settings singleton (which reads .env)
- It only runs if OPENROUTER_ENABLED and OPENROUTER_API_KEY are present
- It prints only the model response (no API key)

Usage:
    python tools/smoke_openrouter.py

Run this from the project root. It will not run tests and it will not modify the repo.
"""
import asyncio
import os
import logging

from backend.utils.config import get_settings
from backend.services.llm_service import get_llm_service

logging.basicConfig(level=logging.INFO)

PROMPT = "Provide a concise travel time estimate between San Francisco and New York City by air, including approximate flight time and one travel tip."


def mask_key(k: str) -> str:
    if not k:
        return '<empty>'
    if len(k) <= 8:
        return '****'
    return f"{k[:4]}...{k[-4:]}"


async def main():
    settings = get_settings()
    openrouter_key = getattr(settings, 'openrouter_api_key', '') or os.environ.get('OPENROUTER_API_KEY', '')
    openrouter_enabled = getattr(settings, 'openrouter_enabled', False)

    if not (openrouter_key and openrouter_enabled):
        print("OpenRouter not enabled or API key missing. Set OPENROUTER_API_KEY and OPENROUTER_ENABLED=true to run this smoke test.")
        return

    print(f"OpenRouter enabled. Key: {mask_key(openrouter_key)} Model: {getattr(settings, 'openrouter_default_model', '<none>')}")

    service = get_llm_service(settings)

    try:
        resp = await service.generate_text_async(prompt=PROMPT, model=getattr(settings, 'openrouter_default_model', None), task_type='travel')
        print('\n--- Model response ---\n')
        print(resp)
    except Exception as e:
        print('Error calling OpenRouter:', str(e))


if __name__ == '__main__':
    asyncio.run(main())
