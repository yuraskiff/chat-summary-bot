import httpx
import logging
from config.config import OPENROUTER_API_KEY

async def request_openrouter(endpoint, data):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"https://api.openrouter.ai/{endpoint}"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logging.error(f"Openrouter request error: {e}")
        return None
