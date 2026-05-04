import aiohttp
from config import OPENROUTER_API_KEY
import os
import logging

async def speech_to_text(file_path: str) -> str:
    url = "https://openrouter.ai/api/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}"
    }
    
    try:
        data = aiohttp.FormData()
        data.add_field('file', open(file_path, 'rb'))
        data.add_field('model', 'openai/whisper-large-v3')

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, data=data) as resp:
                if resp.status != 200:
                    logging.error(f"OpenRouter STT failed: {await resp.text()}")
                    return ""
                result = await resp.json()
                return result.get('text', '')
    except Exception as e:
        logging.error(f"STT Error: {e}")
        return ""
