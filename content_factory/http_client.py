"""
Централизованный aiohttp-клиент для content_factory.
aiohttp автоматически читает HTTP_PROXY/HTTPS_PROXY из системного окружения —
именно так работает основной foodflow-bot (services/normalization.py и др.)
"""
from __future__ import annotations

import json
import aiohttp


async def openrouter_post(
    *,
    url: str = "https://openrouter.ai/api/v1/chat/completions",
    headers: dict,
    payload: dict,
    timeout: float = 35.0,
) -> dict:
    """
    POST к OpenRouter через aiohttp (с автоматическим прокси из env).
    Возвращает распарсенный JSON-ответ или бросает исключение.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
