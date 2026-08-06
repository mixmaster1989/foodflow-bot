import os
import re
import random
import asyncio
import logging
import requests
import base64
import sys
import aiohttp
from datetime import datetime, timedelta
from typing import Optional

# Убедимся, что можем импортировать config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import settings

from .brain import call_llm
from .memory import get_config, set_config

logger = logging.getLogger(__name__)

GROUP_ID = "237459623" # FoodFlow
VK_TOKEN = os.getenv("VK_PUBLISHER_TOKEN") or os.getenv("VK_TOKEN")

REF_IMAGES = [
    "/home/user1/foodflow-bot_new/content_factory/image_refs/anna_selfie_ref.png"
]

def get_base64_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def clean_llm_response(text: str) -> str:
    """Очищает ответ LLM от списков вариантов, кавычек и вводных слов."""
    text = text.strip()
    if text.startswith('"') and text.endswith('"'): text = text[1:-1].strip()
    if text.startswith("'") and text.endswith("'"): text = text[1:-1].strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines: return text
    cleaned_options = []
    for line in lines:
        if any(intro in line.lower() for intro in ['вариант', 'на выбор', 'репост', 'короткий комментарий', 'вот:', 'напишу']) and (line.endswith(':') or len(line) < 45):
            continue
        match = re.match(r'^(?:\d+[\.)]|-|\*)\s*(.*)', line)
        if match:
            cleaned_options.append(match.group(1).strip())
        else:
            cleaned_options.append(line)
    if cleaned_options:
        first_option = cleaned_options[0]
        if first_option.startswith('"') and first_option.endswith('"'): first_option = first_option[1:-1].strip()
        if first_option.startswith("'") and first_option.endswith("'"): first_option = first_option[1:-1].strip()
        return first_option
    return text


def clean_post_text(text: str) -> str:
    """Очищает полноценный текст поста от кавычек и вводных слов, сохраняя абзацы."""
    text = text.strip()
    if text.startswith('"') and text.endswith('"'): 
        text = text[1:-1].strip()
    elif text.startswith("'") and text.endswith("'"): 
        text = text[1:-1].strip()
        
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            cleaned_lines.append("")
            continue
        if any(intro in line_strip.lower() for intro in ['вариант', 'на выбор', 'короткий комментарий', 'напишу', 'вот ваш пост', 'готовый вариант']) and (line_strip.endswith(':') or len(line_strip) < 50):
            continue
        cleaned_lines.append(line_strip)
    return "\n".join(cleaned_lines).strip()


class VKInfluencer:
    def __init__(self):
        self.token = VK_TOKEN
        self.version = "5.131"
        self.base_url = "https://api.vk.com/method/"
        
        proxy_url = os.getenv("GROK_PROXY")
        if proxy_url:
            self.proxies = {
                "http": proxy_url,
                "https": proxy_url
            }
            logger.info(f"🔒 [VK Influencer] Инициализировано с прокси: {proxy_url}")
        else:
            self.proxies = None

    def _call(self, method: str, params: dict, max_retries: int = 3):
        params["access_token"] = self.token
        params["v"] = self.version
        
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(self.base_url + method, data=params, proxies=self.proxies, timeout=15)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.warning(f"⚠️ [VK API] Попытка #{attempt} вызова {method} завершилась ошибкой: {e}")
                if attempt == max_retries:
                    logger.error(f"❌ [VK API] Все {max_retries} попыток вызова {method} провалились.")
                    raise
                import time
                time.sleep(2)

    async def generate_anna_selfie(self, topic: str) -> Optional[str]:
        """Генерирует селфи Анны на основе темы поста с использованием 3 референсов и Gemini 2.5."""
        try:
            logger.info(f"🤳 Запуск генератора селфи для темы: '{topic}'...")
            
            # Придумываем сюжет селфи под тему поста
            prompt_query = (
                f"Based on the lifestyle post topic: '{topic}', write a single sentence in English "
                f"describing a candid lifestyle photo of the exact same young woman (our main character). "
                f"She should be doing something natural that matches the topic (e.g. holding an apple, working, jogging, eating healthy food). "
                f"Describe her action, outfit, background, and natural friendly smile. "
                f"Keep it very simple and casual. Avoid trigger words like 'girl', 'cozy oversized'. "
                f"Output ONLY the description sentence, no quotes, no extra text."
            )
            selfie_prompt_raw = await call_llm([{"role": "user", "content": prompt_query}])
            selfie_prompt = clean_llm_response(selfie_prompt_raw)
            logger.info(f"📝 Сгенерирован сюжет для селфи: '{selfie_prompt}'")
            
            # Собираем промпт с требованиями по сходству
            full_prompt = (
                f"Using these 3 reference images of the exact same young woman, generate a new candid lifestyle smartphone photo of her. "
                f"{selfie_prompt} "
                f"Keep the face shape, light brown hair, eyes, and overall features identical to the reference photos. "
                f"Amateur photography style, natural lighting. High consistency. Output only the generated image."
            )
            
            # Кодируем референсы
            base64_refs = []
            for img_path in REF_IMAGES:
                if os.path.exists(img_path):
                    base64_refs.append(get_base64_image(img_path))
                else:
                    logger.error(f"❌ Референсный файл не найден: {img_path}")
            
            if not base64_refs:
                logger.error("❌ Нет доступных референсных изображений для генерации селфи.")
                return None
                
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://foodflow.ai",
                "X-Title": "FoodFlow Guerrilla Agent",
                "Content-Type": "application/json"
            }
            
            # Вспомогательная функция для запроса к OpenRouter
            async def make_api_call(prompt_text):
                content = [{"type": "text", "text": prompt_text}]
                for b64 in base64_refs:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64}"
                        }
                    })
                payload = {
                    "model": "google/gemini-2.5-flash-image",
                    "messages": [{"role": "user", "content": content}],
                    "modalities": ["image"]
                }
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90) as resp:
                            if resp.status != 200:
                                err_text = await resp.text()
                                logger.error(f"❌ Ошибка OpenRouter ({resp.status}): {err_text}")
                                return None
                            return await resp.json()
                except Exception as call_err:
                    logger.error(f"❌ Исключение при запросе к OpenRouter: {call_err}")
                    return None

            # Парсинг base64 изображения из ответа OpenRouter
            def parse_response(response_data):
                if not response_data:
                    return None
                choices = response_data.get("choices", [])
                if not choices:
                    return None
                message = choices[0].get("message", {})
                img_b64 = None
                content_val = message.get("content")
                if content_val and isinstance(content_val, str) and "base64," in content_val:
                    img_b64 = content_val.split("base64,")[1].strip()
                elif message.get("images"):
                    img_item = message["images"][0]
                    if isinstance(img_item, dict):
                        url = img_item.get("image_url", {}).get("url", "")
                        if "base64," in url:
                            img_b64 = url.split("base64,")[1].strip()
                        else:
                            img_b64 = url
                    else:
                        img_b64 = img_item
                elif isinstance(content_val, list):
                    for part in content_val:
                        if isinstance(part, dict) and part.get("type") == "image_url":
                            url = part.get("image_url", {}).get("url", "")
                            if "base64," in url:
                                img_b64 = url.split("base64,")[1].strip()
                                break
                return img_b64

            # Попытка #1: Динамически сгенерированный сюжет
            data = await make_api_call(full_prompt)
            img_b64 = parse_response(data)
            
            if not img_b64:
                # Попытка #2: Безопасный запасной сюжет без триггерных слов
                logger.warning("⚠️ Попытка #1 не вернула изображение (возможно, фильтр безопасности Gemini). Пробуем безопасный запасной сюжет...")
                fallback_prompt = (
                    "Using these 3 reference images of the exact same young woman, generate a new candid lifestyle smartphone photo of her. "
                    "She is sitting at a bright kitchen table with a fresh healthy breakfast, smiling happily at the camera. "
                    "Keep the face shape, light brown hair, eyes, and overall features identical to the reference photos. "
                    "Amateur photography style, natural lighting. High consistency. Output only the generated image."
                )
                data = await make_api_call(fallback_prompt)
                img_b64 = parse_response(data)
                
            if not img_b64:
                logger.error(f"❌ Обе попытки генерации селфи завершились неудачно. Ответ API: {data}")
                return None
                
            temp_selfie_path = "content_factory/runs/temp_selfie.png"
            os.makedirs("content_factory/runs", exist_ok=True)
            with open(temp_selfie_path, "wb") as output_file:
                output_file.write(base64.b64decode(img_b64))
            logger.info(f"✅ Селфи успешно сгенерировано и сохранено во временный файл: {temp_selfie_path}")
            return temp_selfie_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка в generate_anna_selfie: {e}")
            return None

    async def generate_lifestyle_topic(self) -> str:
        """Придумывает тему для поста от лица Анны."""
        prompt = (
            "Придумай одну короткую и интересную тему для поста в ВК от лица Анны Третьяковой. "
            "Она — создательница и руководитель проекта FoodFlow, увлекается нутрициологией. "
            "Темы могут быть: осознанное питание, лайфхаки по готовке, психология переедания, польза конкретных продуктов. "
            "Ответь ОДНИМ коротким предложением-темой."
        )
        return await call_llm([{"role": "user", "content": prompt}])

    async def create_post(self, text: str, image_path: Optional[str] = None, video_path: Optional[str] = None):
        """Публикует пост на стену."""
        params = {"message": text}
        
        if video_path and os.path.exists(video_path):
            try:
                logger.info(f"📹 Запуск загрузки личного видео: {video_path}")
                srv = self._call("video.save", {
                    "name": "Личное видео",
                    "description": text[:200],
                    "wallpost": 0
                })
                if srv and "response" in srv:
                    upload_url = srv["response"]["upload_url"]
                    video_id = srv["response"]["video_id"]
                    owner_id = srv["response"]["owner_id"]
                    
                    # 3 попытки загрузки видео на сервер VK
                    res_up = None
                    for attempt in range(1, 4):
                        try:
                            with open(video_path, "rb") as f:
                                files = {"video_file": (os.path.basename(video_path), f, "video/mp4")}
                                resp = requests.post(upload_url, files=files, proxies=self.proxies, timeout=120)
                                resp.raise_for_status()
                                res_up = resp.json()
                                break
                        except Exception as up_err:
                            logger.warning(f"⚠️ [VK Video Upload] Попытка #{attempt} загрузки видео не удалась: {up_err}")
                            if attempt < 3:
                                await asyncio.sleep(2)
                                
                    if res_up:
                        params["attachments"] = f"video{owner_id}_{video_id}"
                        logger.info(f"✅ Видео успешно загружено на сервер VK: video{owner_id}_{video_id}")
                    else:
                        logger.error("❌ [VK Video Upload] Все попытки загрузки видео на сервер VK завершились неудачно.")
            except Exception as srv_err:
                logger.error(f"❌ [VK Video Save] Ошибка при обработке видео: {srv_err}.")
                
        elif image_path:
            # Загрузка фото на стену (упрощенная схема)
            try:
                # Конвертируем и сжимаем в JPEG перед загрузкой в VK
                upload_path = image_path
                temp_jpg_path = None
                if not image_path.lower().endswith(".jpg") and not image_path.lower().endswith(".jpeg"):
                    try:
                        from PIL import Image
                        temp_jpg_path = "content_factory/runs/upload_temp.jpg"
                        with Image.open(image_path) as img:
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            img.save(temp_jpg_path, "JPEG", quality=85, optimize=True)
                        upload_path = temp_jpg_path
                        logger.info(f"💾 Изображение сконвертировано в JPG перед загрузкой: {upload_path} ({os.path.getsize(upload_path)/1024:.1f} KB)")
                    except Exception as compress_err:
                        logger.error(f"⚠️ Ошибка при конвертации перед загрузкой: {compress_err}")
                
                srv = self._call("photos.getWallUploadServer", {})
                if srv and "response" in srv:
                    upload_url = srv["response"]["upload_url"]
                    res_up = None
                    
                    # 3 попытки загрузки фото на сервер VK
                    for attempt in range(1, 4):
                        try:
                            with open(upload_path, "rb") as f:
                                resp = requests.post(upload_url, files={"photo": f}, proxies=self.proxies, timeout=60)
                                resp.raise_for_status()
                                res_up = resp.json()
                                break
                        except Exception as up_err:
                            logger.warning(f"⚠️ [VK Upload] Попытка #{attempt} загрузки фото не удалась: {up_err}")
                            if attempt < 3:
                                await asyncio.sleep(2)
                                
                    if res_up and "server" in res_up:
                        res_save = self._call("photos.saveWallPhoto", {
                            "server": res_up["server"], "photo": res_up["photo"], "hash": res_up["hash"]
                        })
                        if res_save and "response" in res_save:
                            photo = res_save["response"][0]
                            params["attachments"] = f"photo{photo['owner_id']}_{photo['id']}"
                        else:
                            logger.error(f"❌ [VK Save] Не удалось сохранить фото на стене: {res_save}")
                    else:
                        logger.error("❌ [VK Upload] Все попытки загрузки фото на сервер VK завершились неудачно.")
                        
                # Чистим временный JPG
                if temp_jpg_path and os.path.exists(temp_jpg_path):
                    try:
                        os.remove(temp_jpg_path)
                    except Exception as rm_err:
                        logger.error(f"⚠️ Не удалось удалить временный JPG: {rm_err}")
            except Exception as srv_err:
                logger.error(f"❌ [VK Wall Photo] Ошибка при обработке картинки: {srv_err}. Постим только текст.")
                
        return self._call("wall.post", params)

    async def get_new_group_post(self) -> Optional[dict]:
        """Проверяет наличие нового поста в группе и возвращает его, если он новый."""
        try:
            res = self._call("wall.get", {"owner_id": f"-{GROUP_ID}", "count": 2})
            items = res.get("response", {}).get("items", [])
            if not items:
                return None
            
            # Пропускаем закреп, берем свежий
            target_post = items[0] if not items[0].get("is_pinned") else items[1]
            post_id = target_post["id"]
            
            # Проверяем, не репостили ли мы его уже
            last_synced = await get_config("vk_last_synced_post_id")
            if last_synced == str(post_id):
                logger.info("⏭️ Последний пост из группы уже был репостнут.")
                return None
                
            return target_post
        except Exception as e:
            logger.error(f"❌ Ошибка при получении постов группы: {e}")
            return None

    async def publish_repost(self, post_id: int, post_text: str) -> bool:
        """Выполняет репост с генерацией комментария от лица Анны."""
        try:
            # Генерируем живой комментарий от лица Анны
            prompt = (
                f"Вот текст поста из нашего сообщества: '{post_text[:200]}...'\n"
                f"Напиши один короткий (1-2 предложения), живой комментарий от лица Анны Третьяковой для репоста этого поста на её личную стену. "
                f"Анна — создательница проекта и группы FoodFlow. "
                f"Комментарий должен быть в стиле: 'Наш новый полезный пост!', 'Мы с командой старались!' или 'Свежие советы из нашей группы'. "
                f"Будь дружелюбной, используй 1-2 эмодзи. Пиши со строчной буквы. "
                f"ВАЖНО: Выведи только один готовый финальный вариант комментария. Без вариантов на выбор, без списков, без вводных слов и кавычек."
            )
            comment_raw = await call_llm([{"role": "user", "content": prompt}])
            comment = clean_llm_response(comment_raw)
            
            # Делаем репост
            repost_res = self._call("wall.repost", {
                "object": f"wall-{GROUP_ID}_{post_id}",
                "message": comment
            })
            
            if "response" in repost_res:
                logger.info(f"✅ [VK Repost] Репост выполнен! ID поста: {post_id}")
                return True
            else:
                logger.error(f"❌ [VK Repost] Ошибка репоста: {repost_res}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка в publish_repost: {e}")
            return False

    async def run_lifestyle_cycle(self):
        """Полный цикл создания 'живого' поста."""
        try:
            topic = await self.generate_lifestyle_topic()
            logger.info(f"🎨 Сгенерирована тема лайфстайла: {topic}")
            
            # Генерируем текст поста
            prompt = (
                f"Напиши один короткий, нативный пост для ВК на тему: '{topic}'. "
                f"Ты — Анна Третьякова, создательница и идейный вдохновитель проекта FoodFlow, нутрициолог-любитель. Пиши просто, как для друзей. "
                f"Упомяни мимоходом FoodFlow (ведь ты его создала, чтобы облегчить людям подсчет калорий и контроль питания). "
                f"Используй 1-2 эмодзи. Не используй хэштеги. Пиши со строчной буквы. "
                f"ВАЖНО: Выведи только один готовый финальный вариант поста. Без вариантов на выбор, без списков, без вводных слов и кавычек."
            )
            post_text_raw = await call_llm([{"role": "user", "content": prompt}])
            post_text = clean_post_text(post_text_raw)
            
            # Прикрепляем ссылки на все ресурсы проекта к лайфстайл-посту
            footer = (
                "\n\n"
                "Подписывайтесь на наши ресурсы:\n"
                "🤖 Попробовать ИИ-бота: t.me/FoodFlow2026bot?start=vk_anna\n"
                "📢 Telegram-канал: t.me/FoodFlow2026\n"
                "🌐 Наш сайт: фудфлоу.рф\n"
                "🎥 YouTube: youtube.com/@Foodflow2026\n"
                "👥 Наша VK-группа: vk.com/foodflow_kbzhu"
            )
            post_text += footer
            
            # Выбор 50/50: селфи или обычная эстетика
            is_selfie = random.choice([True, False])
            temp_img_path = None
            
            if is_selfie:
                # Генерируем селфи Анны через Gemini 2.5
                temp_img_path = await self.generate_anna_selfie(topic)
                
            if not temp_img_path:
                # Фоллбек на обычную эстетичную картинку (или если выбрано не селфи)
                img_prompt_query = (
                    f"Based on the lifestyle post topic '{topic}', write a single sentence in English "
                    f"for generating a photorealistic image. The image should depict aesthetic food (like healthy breakfast, "
                    f"avocado toast, coffee cup, salad, cooking process) or a bright aesthetic lifestyle scene. "
                    f"Style: photorealistic, bright natural lighting, lifestyle, aesthetic, 4k, no text, no logos. "
                    f"Return ONLY the prompt string, no quotes."
                )
                img_prompt_raw = await call_llm([{"role": "user", "content": img_prompt_query}])
                img_prompt = clean_llm_response(img_prompt_raw)
                
                # Подключаем генератор картинок
                import sys
                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                from content_factory.generators.image import generate_image
                
                logger.info(f"🎨 Генерируем эстетичную картинку с промптом: {img_prompt}")
                img_url = await generate_image(img_prompt)
                
                if img_url and not img_url.startswith("error"):
                    try:
                        temp_img_path = "content_factory/runs/temp_lifestyle.png"
                        os.makedirs("content_factory/runs", exist_ok=True)
                        if img_url.startswith("data:image"):
                            import base64
                            header, b64 = img_url.split(";base64,", 1)
                            image_bytes = base64.b64decode(b64)
                            with open(temp_img_path, "wb") as f:
                                f.write(image_bytes)
                            logger.info(f"💾 Картинка успешно декодирована во временный файл: {temp_img_path}")
                        else:
                            resp = requests.get(img_url, proxies=self.proxies, timeout=20)
                            if resp.status_code == 200:
                                with open(temp_img_path, "wb") as f:
                                    f.write(resp.content)
                                logger.info(f"💾 Картинка успешно загружена во временный файл: {temp_img_path}")
                            else:
                                temp_img_path = None
                                logger.warning(f"⚠️ Не удалось скачать картинку по ссылке: status {resp.status_code}")
                    except Exception as dl_err:
                        temp_img_path = None
                        logger.error(f"❌ Ошибка при скачивании сгенерированной картинки: {dl_err}")
            
            # Публикуем пост с картинкой (или без, если не сгенерировалась)
            res = await self.create_post(post_text, image_path=temp_img_path)
            
            # Чистим временные файлы
            if temp_img_path and os.path.exists(temp_img_path):
                try:
                    os.remove(temp_img_path)
                    logger.info("🗑️ Временный файл картинки удален.")
                except Exception as rm_err:
                    logger.error(f"⚠️ Не удалось удалить временный файл картинки: {rm_err}")
                    
            if "response" in res:
                logger.info(f"✨ Опубликован лайфстайл пост: {topic} (Визуал: {'Селфи Анны' if is_selfie and temp_img_path else 'Эстетика' if temp_img_path else 'Нет'})")
            else:
                logger.error(f"❌ Ошибка лайфстайл поста: {res}")
        except Exception as e:
            logger.error(f"❌ Ошибка в run_lifestyle_cycle: {e}")


async def influencer_task():
    """Фоновая задача для поддержания жизни аккаунта Анны Третьяковой (VK)."""
    influencer = VKInfluencer()
    logger.info("🎭 Задача VK Influencer запущена (Московское время, персистентное планирование).")
    
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            
            # 1. ПЛАНИРОВАНИЕ И ВЫПОЛНЕНИЕ РЕПОСТОВ
            if now.hour >= 16 and (now.hour > 16 or now.minute >= 5):
                last_check_date = await get_config("vk_last_check_date")
                if last_check_date != today_str:
                    logger.info(f"⏰ Время >= 16:05 MSK. Проверяем наличие свежего поста в группе...")
                    post_to_repost = await influencer.get_new_group_post()
                    if post_to_repost:
                        # Рассчитываем случайную задержку
                        now_seconds = now.hour * 3600 + now.minute * 60 + now.second
                        end_seconds = 23 * 3600
                        delay = random.randint(60, max(60, end_seconds - now_seconds))
                        target_time = now + timedelta(seconds=delay)
                        target_time_str = target_time.strftime("%Y-%m-%d %H:%M:%S")
                        
                        await set_config("vk_repost_target_time", target_time_str)
                        await set_config("vk_repost_post_id", str(post_to_repost["id"]))
                        await set_config("vk_repost_post_text", post_to_repost.get("text", ""))
                        await set_config("vk_last_check_date", today_str)
                        logger.info(f"🎯 [VK Repost] Новый пост найден! Репост запланирован на {target_time_str} MSK.")
                    else:
                        # Если поста нет, просто отмечаем проверку, чтобы не долбить API группы
                        await set_config("vk_last_check_date", today_str)
                        logger.info(f"🍃 [VK Repost] Свежих постов в группе для репоста сегодня нет.")
            
            # Проверяем, пришло ли время делать репост
            vk_repost_target = await get_config("vk_repost_target_time")
            if vk_repost_target and now_str >= vk_repost_target:
                post_id = await get_config("vk_repost_post_id")
                post_text = await get_config("vk_repost_post_text")
                if post_id:
                    logger.info(f"🚀 [VK Repost] Наступило время репоста ({vk_repost_target}). Публикуем...")
                    success = await influencer.publish_repost(int(post_id), post_text or "")
                    if success:
                        await set_config("vk_last_synced_post_id", post_id)
                    # Сбрасываем таргет в любом случае, чтобы не спамить в цикле при критической ошибке
                    await set_config("vk_repost_target_time", "")
                    await set_config("vk_repost_post_id", "")
                    await set_config("vk_repost_post_text", "")

            # 2. ПЛАНИРОВАНИЕ И ВЫПОЛНЕНИЕ ЛАЙФСТАЙЛ ПОСТА
            if now.hour >= 10:
                last_lifestyle_date = await get_config("vk_last_lifestyle_date")
                if last_lifestyle_date != today_str:
                    target_time_str = await get_config("vk_lifestyle_target_time")
                    # Если таргет-тайм еще не задан или устарел (принадлежит вчерашнему дню)
                    if not target_time_str or not target_time_str.startswith(today_str):
                        now_seconds = now.hour * 3600 + now.minute * 60 + now.second
                        end_seconds = 22 * 3600
                        delay = random.randint(60, max(60, end_seconds - now_seconds))
                        target_time = now + timedelta(seconds=delay)
                        target_time_str = target_time.strftime("%Y-%m-%d %H:%M:%S")
                        await set_config("vk_lifestyle_target_time", target_time_str)
                        logger.info(f"🌸 [VK Lifestyle] Запланировали новый пост на {target_time_str} MSK.")

            # Проверяем, пришло ли время делать лайфстайл пост
            vk_lifestyle_target = await get_config("vk_lifestyle_target_time")
            if vk_lifestyle_target and vk_lifestyle_target.startswith(today_str) and now_str >= vk_lifestyle_target:
                logger.info(f"🚀 [VK Lifestyle] Наступило время лайфстайл поста ({vk_lifestyle_target}). Публикуем...")
                # Сбрасываем таргет сразу, чтобы избежать повторных вызовов во время долгой работы генерации ИИ
                await set_config("vk_lifestyle_target_time", "")
                
                try:
                    await influencer.run_lifestyle_cycle()
                    await set_config("vk_last_lifestyle_date", today_str)
                    logger.info("✅ [VK Lifestyle] Пост успешно опубликован, дата зафиксирована.")
                except Exception as cycle_err:
                    logger.error(f"❌ [VK Lifestyle] Ошибка публикации цикла: {cycle_err}")
            
            # Проверяем состояние раз в 60 секунд
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в VK Influencer Task: {e}")
            await asyncio.sleep(60)
