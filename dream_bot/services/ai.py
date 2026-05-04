import aiohttp
import json
from config import OPENROUTER_API_KEY
import logging

async def interpret_dream(dream_text: str) -> str:
    prompt = f"""Ты — ИИ-Толкователь Снов, великий Оракул, сочетающий в себе мудрость Карла Юнга и мистику древних пророков.
    Твоя задача: дать глубокую, таинственную и в то же время психологически обоснованную интерпретацию сна пользователя.
    
    Сон пользователя: "{dream_text}"
    
    Твой ответ должен состоять из 3 частей:
    1. 🌌 **Мистический смысл** (что говорят звезды и архетипы).
    2. 🧠 **Психологический взгляд** (что это значит для подсознания).
    3. 🕯 **Совет Оракула** (короткое наставление на завтра).
    
    Пиши красиво, вдохновляюще и немного загадочно. Максиимум 1000 символов."""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "google/gemini-2.0-flash-lite-preview-09-2025",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        timeout = aiohttp.ClientTimeout(total=45)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                result = await resp.json()
                return result['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Error calling OpenRouter AI: {e}")
        return "Оракул сейчас занят созерцанием вечности. Пожалуйста, постучись позже."
