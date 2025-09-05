import asyncio
import json
import os
import logging
from backend.services.recruitiq_travel_service import get_recruitiq_travel_service
from backend.utils.config import get_settings

logging.basicConfig(level=logging.INFO)

async def main():
    settings = get_settings()
    key = getattr(settings, 'openrouter_api_key', '')
    print('OPENROUTER_API_KEY present in settings:', bool(key))
    if key:
        masked = key[:4] + '...' + key[-4:]
        print('OPENROUTER_API_KEY (masked):', masked)

    service = get_recruitiq_travel_service()
    print('Service has openroute_api_key:', bool(getattr(service, 'openroute_api_key', None)))

    # Try to run a single directions call if settings present
    res = await service.get_transportation_options('Boston', 'New York City')
    print(json.dumps(res, indent=2))

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
