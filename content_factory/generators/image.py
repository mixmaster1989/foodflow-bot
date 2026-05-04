import logging
from content_factory.http_client import openrouter_post
import json
from config import settings

logger = logging.getLogger(__name__)

import asyncio
import re

IMAGE_MODELS = [
    "google/gemini-2.5-flash-image",
    "openai/gpt-5-image-mini"  # Фолбэк от пользователя
]

async def generate_image(prompt: str) -> str:
    """
    Генерирует изображение через OpenRouter с поддержкой Fallback и Retries.
    """
    logger.info(f"🎨 ЗАПУСК ГЕНЕРАЦИИ КАРТИНКИ. Промпт: {prompt[:50]}...")
    
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "FoodFlow Content Factory",
    }
    
    for model_name in IMAGE_MODELS:
        for attempt in range(1, 4):
            logger.info(f"🎨 [Attempt {attempt}] Генерация через {model_name}...")
            
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user", 
                        "content": f"Generate a high-quality photorealistic image for a health/tech blog. Prompt: {prompt}. Return ONLY the direct URL to the image if possible."
                    }
                ]
            }
            
            try:
                # ТАЙМАУТ 45 секунд для картинок (они дольше генерируются)
                data = await openrouter_post(headers=headers, payload=payload, timeout=45.0)
                
                message = data['choices'][0]['message']
                
                # 1. Поле images
                images = message.get('images')
                if images and isinstance(images, list) and len(images) > 0:
                    item = images[0]
                    if isinstance(item, str):
                        url = item
                    elif isinstance(item, dict):
                        # Бывает {'type': 'image_url', 'image_url': {'url': '...'}}
                        image_url_obj = item.get('image_url')
                        if isinstance(image_url_obj, dict):
                            url = image_url_obj.get('url')
                        else:
                            url = item.get('url')
                    else:
                        url = None
                        
                    if url:
                        logger.info(f"✅ Картинка получена (поле images): {url[:50]}...")
                        return url
                
                # 2. Поле media
                media = message.get('media')
                if media and isinstance(media, list) and len(media) > 0:
                    for item in media:
                        url = None
                        if isinstance(item, dict):
                            if item.get('type') == 'image':
                                url = item.get('url')
                            # Иногда бывает без type: image
                            if not url:
                                url = item.get('url')
                        
                        if url:
                            logger.info(f"✅ Картинка получена (поле media): {url[:50]}...")
                            return url
                
                # 3. Поиск URL в контенте
                content = message.get('content')
                if content:
                    url_match = re.search(r'https?://[^\s<>"]+|(?<=\[)https?://[^\s<>\']+', content)
                    if url_match:
                        url = url_match.group(0)
                        logger.info(f"✅ Картинка найдена в тексте: {url[:50]}...")
                        return url
                        
                logger.warning(f"⚠️ Не удалось извлечь URL из ответа: {message}")
                raise ValueError("URL изображения не найден в ответе")
                        
            except Exception as e:
                logger.warning(f"⚠️ Сбой генерации {model_name} (Attempt {attempt}): {e}")
                await asyncio.sleep(2)  # Пауза перед ретраем
                continue
                
        logger.error(f"❌ Модель {model_name} не справилась. Переход к следующей...")

    return "error_no_url"

