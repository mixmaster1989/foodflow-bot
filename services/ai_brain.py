
import asyncio
import json
import logging
import time

import aiohttp

from config import settings
from monitoring import get_ai_semaphore, stats

logger = logging.getLogger("ai.brain")

def _extract_first_json_object(content: str) -> str | None:
    """Extract the first complete JSON object from content, ignoring trailing data."""
    start = content.find('{')
    if start < 0:
        # Check for array if object not found
        start = content.find('[')
        if start < 0: return None
        
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(content[start:], start):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            depth += 1
        elif ch in ('}', ']'):
            depth -= 1
            if depth == 0:
                return content[start:i + 1]
    return None

class AIBrainService:
    """Core AI Brain Service for semantic understanding of user input."""

    MODEL = "google/gemini-3.1-flash-lite-preview" # Fast, Smart enough

    SYSTEM_PROMPT_ES = """
You are the Brain of the FoodFlow bot (AI nutritionist). Your task is to understand the user's intent and extract data.

RULES FOR DETERMINING NOMENCLATURE (Single item vs List):
1. CULINARY CONTEXT (Single dish): If products are grammatically linked (prepositions "with", "of", "in") or describe components of a single dish (salad, soup, stew, porridge, sandwich, omelet) — it is a SINGLE dish.
   - Example: "Ensalada de pepino y tomate" -> intent: 'log_consumption', multi: false, product: 'Ensalada de pepino y tomate'.
   - Example: "Yogur con bayas y miel" -> intent: 'log_consumption', multi: false, product: 'Yogur con bayas y miel'.
   - Example: "Omelet de 3 huevos con queso" -> intent: 'log_consumption', multi: false, product: 'Omelet de 3 huevos con queso'.

2. FOOD BASKET (List/Batch): If products are clearly heterogeneous, cannot be on the same plate, or describe grocery shopping — it is a LIST.
   - Example: "Compré leche, pan y comí un plátano" -> multi: true.
   - Example: "Desayuno: huevos. Almuerzo: sopa." -> multi: true.

3. VOICE INPUT WITHOUT PUNCTUATION: Speech-to-text often returns a single stream without commas. Different dishes are still clear from context — separate them by:
   - change of context (beverage after solid food: "...un vaso de kéfir", "café negro")
   - new weight/volume for another product: "arroz 200 g 50 g de pescado hervido" = arroz + pescado
   - heterogeneous categories: soup + tea + kefir don't live on the same plate
   - Example: "arroz 200 g 50 g de pescado hervido café negro sopa de pescado con cebada té con limón un vaso de kéfir"
     -> multi: true, items: [arroz 200g, pescado hervido 50g, café negro, sopa de pescado con cebada, té con limón, vaso de kéfir]
   - Example: "huevos fritos de dos huevos café sándwich con queso"
     -> multi: true, items: [huevos fritos de 2 huevos, café, sándwich con queso]

Available intents:
1. 'log_consumption' — the user EXPLICITLY indicated they ATE it.
2. 'add_to_fridge' — the user EXPLICITLY indicated they BOUGHT or want to ADD it.
3. 'unknown' — if there is no explicit action verb or it is just a product name.
4. 'nonsense' — if the input is gibberish, random letters, swearing or nonsense (e.g. "asdfgh", "hola como estas").

IF SINGLE PRODUCT — return JSON object:
{
  "intent": "log_consumption" | "add_to_fridge" | "unknown" | "nonsense",
  "is_nonsense": false, # true if it is gibberish
  "ai_comment": "Polite witty refusal in Spanish if it is nonsense",
  "product": "Full name of the dish/product",
  "weight": 100 | null,
  "quantity": 1,
  "multi": false,
  "original_text": "original text"
}

IF MULTIPLE PRODUCTS — return JSON:
{
  "intent": "log_consumption",
  "is_nonsense": false,
  "multi": true,
  "items": [
    {"product": "Product 1", "weight": 100 | null},
    {"product": "Product 2", "weight": null}
  ],
  "original_text": "original text"
}

STRICT: Do not write anything other than JSON.
"""

    SYSTEM_PROMPT = """
Ты — Мозг бота FoodFlow (AI диетолог). Твоя задача — понять намерение пользователя и извлечь данные.

ПРАВИЛА ОПРЕДЕЛЕНИЯ НОМЕНКЛАТУРЫ (Один предмет vs Список):
1. КУЛИНАРНЫЙ КОНТЕКСТ (Одно блюдо): Если продукты грамматически связаны (предлоги «с», «из», «под», «изу») или описывают компоненты одного блюда (салат, суп, рагу, каша, бутерброд, омлет) — это ОДНО блюдо.
   - Пример: "Салат из огурцов и помидоров" -> intent: 'log_consumption', multi: false, product: 'Салат из огурцов и помидоров'.
   - Пример: "Творог с ягодами и медом" -> intent: 'log_consumption', multi: false, product: 'Творог с ягодами и медом'.
   - Пример: "Омлет из 3 яиц с сыром" -> intent: 'log_consumption', multi: false, product: 'Омлет из 3 яиц с сыром'.

2. ПРОДУКТОВАЯ КОРЗИНА (Список/Batch): Если продукты явно разнородны, не могут находиться в одной тарелке или описывают закупку в магазине — это СПИСОК.
   - Пример: "Купил молоко, хлеб и съел банан" -> multi: true.
   - Пример: "Завтрак: яйца. Обед: борщ." -> multi: true.

3. ГОЛОСОВОЙ ВВОД БЕЗ ПУНКТУАЦИИ: Speech-to-text часто отдаёт слитный поток без запятых. Разные блюда всё равно видны по смыслу — разграничивай их по:
   - смене контекста (напиток после твёрдой еды: "...кефир стакан", "кофе чёрный")
   - новому весу/объёму у другого продукта: "гречка 200 г 50 г отварной рыбы" = гречка + рыба
   - разнородным категориям: суп + чай + кефир не живут в одной тарелке
   - Пример: "гречка 200 г 50 г отварной рыбы кофе чёрный суп рыбный с перловкой чай с лимоном кефир стакан"
     -> multi: true, items: [гречка 200г, отварная рыба 50г, кофе чёрный, суп рыбный с перловкой, чай с лимоном, кефир стакан]
   - Пример: "яичница из двух яиц кофе бутерброд с сыром"
     -> multi: true, items: [яичница из 2 яиц, кофе, бутерброд с сыром]

Доступные намерения (intents):
1. 'log_consumption' — пользователь ЯВНО указал, что СЪЕЛ.
2. 'add_to_fridge' — пользователь ЯВНО указал, что КУПИЛ или хочет ДОБАВИТЬ.
3. 'unknown' — если нет явного глагола действия или просто название продукта.
4. 'nonsense' — если ввод это абракадабра, случайные буквы, мат или бессмыслица (например: "ываыва", "asdfgh", "привет как дела").

ЕСЛИ ОДИН ПРОДУКТ — верни JSON объект:
{
  "intent": "log_consumption" | "add_to_fridge" | "unknown" | "nonsense",
  "is_nonsense": false, # true если это абракадабра
  "ai_comment": "Вежливый остроумный отказ на русском если это nonsense",
  "product": "Название блюда целиком",
  "weight": 100 | null,
  "quantity": 1,
  "multi": false,
  "original_text": "исходный текст"
}

ЕСЛИ ПРОДУКТОВ НЕСКОЛЬКО — верни JSON:
{
  "intent": "log_consumption",
  "is_nonsense": false,
  "multi": true,
  "items": [
    {"product": "Продукт 1", "weight": 100 | null},
    {"product": "Продукт 2", "weight": null}
  ],
  "original_text": "исходный текст"
}

СТРОГО: Не пиши ничего кроме JSON.
"""

    @classmethod
    async def analyze_text(cls, text: str, force_multi: bool = False, force_single: bool = False) -> dict | None:
        """Call LLM to analyze text and return structured data.

        Args:
            text: Raw input text
            force_multi: Force AI to split input into multiple items
            force_single: Force AI to treat input as one single dish
        """

        from utils.i18n import get_locale
        locale = get_locale()

        # Prepare specialized instructions if forced
        system_instruction = cls.SYSTEM_PROMPT_ES if locale == "es" else cls.SYSTEM_PROMPT
        if force_multi:
            system_instruction += "\n\nCRITICAL: You MUST split this input into multiple products (multi: true). Even if they look like one dish, find components."
        elif force_single:
            system_instruction += "\n\nCRITICAL: You MUST treat this target input as ONE SINGLE dish/product (multi: false). Combine everything into one product name."

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot",
        }

        payload = {
            "model": cls.MODEL,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": text}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }


        # Use semaphore to limit concurrent AI calls (Phase 1 optimization)
        semaphore = get_ai_semaphore(max_concurrent=5)

        async with semaphore:
            start_time = time.time()
            for attempt in range(2):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            proxy=settings.openrouter_proxy,
                            timeout=10
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                content = data['choices'][0]['message']['content']
                                # Clean output just in case
                                content = content.replace("```json", "").replace("```", "").strip()

                                # Track stats
                                duration_ms = (time.time() - start_time) * 1000
                                stats.record_ai_call(duration_ms)

                                return json.loads(content)
                            else:
                                logger.warning(f"AI Brain error {response.status}: {await response.text()}")
                                stats.record_error()
                except Exception as e:
                    logger.error(f"AI Brain exception: {e}")
                    stats.record_error()

                await asyncio.sleep(0.5)

        return None

    @classmethod
    async def resolve_herbalife_product(cls, text: str, products_context: list[dict]) -> str | None:
        """Use AI to match user input to a specific Herbalife Product ID."""

        # Prepare a compact list of products for the prompt
        compact_list = [
            {"id": p["id"], "name": p["name"], "aliases": p.get("aliases", [])}
            for p in products_context
        ]

        prompt = f"""
Ты — эксперт по продукции Herbalife. Твоя задача — сопоставить ввод пользователя с конкретным ID продукта из предоставленного списка.
Если во вводе указан вкус (например, 'дыня', 'манго', 'шоколад'), обязательно выбери соответствующий ID.

Список продуктов:
{json.dumps(compact_list, ensure_ascii=False, indent=2)}

Ввод пользователя: "{text}"

Твоя задача — вернуть JSON:
{{
  "matched_product_id": "id_from_list" (или null если нет совпадения),
  "reason": "краткое объяснение почему выбран этот ID"
}}
"""

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot",
        }

        payload = {
            "model": cls.MODEL,
            "messages": [
                {"role": "system", "content": "Return ONLY JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }


        # Use semaphore to limit concurrent AI calls
        semaphore = get_ai_semaphore(max_concurrent=5)

        async with semaphore:
            start_time = time.time()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        proxy=settings.openrouter_proxy,
                        timeout=10
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            content = data['choices'][0]['message']['content']
                            logger.info(f"Herbalife AI Raw Response: {content[:200]}")
                            result = json.loads(content)
                            matched_id = result.get("matched_product_id")
                            logger.info(f"Herbalife AI Matched ID: {matched_id}, Reason: {result.get('reason', 'N/A')}")

                            # Track stats
                            duration_ms = (time.time() - start_time) * 1000
                            stats.record_ai_call(duration_ms)

                            return matched_id
                        else:
                            logger.warning(f"Herbalife AI HTTP Error: {response.status}")
                            stats.record_error()
            except Exception as e:
                logger.error(f"Herbalife Resolution AI Error: {e}")
                stats.record_error()


    @classmethod
    async def analyze_image(cls, message_or_path: any, prompt_override: str = None) -> dict | None:
        """Analyze image using Vision model. 
        
        Returns dict with:
        - is_edible: bool
        - food_name: str (normalized name)
        - is_receipt: bool
        - is_pricetag: bool
        - ai_comment: str (friendly AI refusal if not edible)
        - description: str (full visual description)
        """
        import base64

        from utils.i18n import get_locale
        locale = get_locale()

        # Core Vision Prompt (The "Intelligence" of the bot)
        if not prompt_override:
            if locale == "es":
                prompt = """
                Analyze this image for a food-tracking AI assistant.
                
                TASK:
                1. Determine if the image contains:
                   - FOOD/DISH (ready to eat)
                   - GROCERY PRODUCT (packaged)
                   - RECEIPT (grocery receipt with list of items)
                   - PRICE TAG (shelf label with price/name)
                
                2. If it's NOT food/receipt/product (e.g., person, animal, car, landscape, non-food object):
                   - Set is_edible: false
                   - Write a friendly, witty refusal in "ai_comment" in SPANISH. 
                     Example: "¡Los gatitos son amigos, no comida! Pobre gatito. 😉"
                
                3. If it IS food/product/receipt:
                   - Set is_edible: true
                   - Extract "food_name" (short name in ES, e.g. "Tortilla", "Arándano").
                     CRITICAL FOR MULTI-DISH IMAGES / TABLE FEASTS:
                     If the image contains multiple distinct dishes or a table of food (a feast, family dinner, separate items), you MUST systematically identify all key individual dishes (scanning the image strictly from left to right, top to bottom) and list them separated by commas in "food_name" (e.g. "Patatas fritas, pollo, ensalada de verduras"). This scanning method guarantees absolute consistency!
                     STRICTLY FORBIDDEN: Do NOT return generic, non-informative terms like "Almuerzo", "Cena", "Desayuno", "Comida", "Banquete", "Plato" for "food_name". Always be specific and list the actual foods!
                   - Set is_receipt: true if it's a receipt.
                   - Set is_pricetag: true if it's a shelf price tag.
                
                RETURN ONLY JSON:
                {
                  "is_edible": true,
                  "food_name": "Nombre (ES)",
                  "is_receipt": false,
                  "is_pricetag": false,
                  "ai_comment": null,
                  "description": "Full visual description"
                }
                """
            else:
                prompt = """
                Analyze this image for a food-tracking AI assistant.
                
                TASK:
                1. Determine if the image contains:
                   - FOOD/DISH (ready to eat)
                   - GROCERY PRODUCT (packaged)
                   - RECEIPT (grocery receipt with list of items)
                   - PRICE TAG (shelf label with price/name)
                
                2. If it's NOT food/receipt/product (e.g., person, animal, car, landscape, non-food object):
                   - Set is_edible: false
                   - Write a friendly, witty refusal in "ai_comment" in RUSSIAN. 
                     Example: "Котики — это друзья, а не еда! Пожалей пушистика. 😉"
                
                3. If it IS food/product/receipt:
                   - Set is_edible: true
                   - Extract "food_name" (short name in RU, e.g. "Борщ", "Черника").
                     CRITICAL FOR MULTI-DISH IMAGES / TABLE FEASTS:
                     If the image contains multiple distinct dishes or a table of food (a feast, family dinner, separate items), you MUST systematically identify all key individual dishes (scanning the image strictly from left to right, top to bottom) and list them separated by commas in "food_name" (e.g. "Жареная картошка, курица, овощной салат"). This scanning method guarantees absolute consistency!
                     STRICTLY FORBIDDEN: Do NOT return generic, non-informative terms like "Обед", "Ужин", "Завтрак", "Еда", "Застолье", "Тарелка" for "food_name". Always be specific and list the actual foods!
                   - Set is_receipt: true if it's a receipt.
                   - Set is_pricetag: true if it's a shelf price tag.
                
                RETURN ONLY JSON:
                {
                  "is_edible": true,
                  "food_name": "Название (RU)",
                  "is_receipt": false,
                  "is_pricetag": false,
                  "ai_comment": null,
                  "description": "Full visual description"
                }
                """
        else:
            prompt = prompt_override

        # Determine image source
        b64_image = None

        try:
            if isinstance(message_or_path, str):
                # It's a file path
                with open(message_or_path, "rb") as image_file:
                    b64_image = base64.b64encode(image_file.read()).decode('utf-8')
            else:
                # Assume it's an aiogram Message object
                # We need to download it first. This requires the 'bot' instance.
                # Since we don't have easy access to bot instance here without circular imports,
                # we'll assume the caller handles downloading if it's complex.
                # BUT, wait! We can get bot from message.bot
                bot = message_or_path.bot
                if message_or_path.photo:
                    file_id = message_or_path.photo[-1].file_id
                    file = await bot.get_file(file_id)
                    file_path = file.file_path

                    # Download to memory
                    io_obj = await bot.download_file(file_path)

                    # Save a copy of the photo locally to the server for debugging/logging
                    import os
                    from datetime import datetime
                    photos_dir = "/home/user1/foodflow-bot_new/photos_log"
                    os.makedirs(photos_dir, exist_ok=True)
                    user_id = message_or_path.from_user.id if hasattr(message_or_path, "from_user") else "unknown"
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    save_path = f"{photos_dir}/{user_id}_{timestamp}_{file_id[-10:]}.jpg"

                    io_obj.seek(0)
                    img_data = io_obj.read()
                    with open(save_path, "wb") as img_file:
                        img_file.write(img_data)
                    logger.info(f"📸 Saved uploaded photo to server: {save_path}")

                    b64_image = base64.b64encode(img_data).decode('utf-8')

            if not b64_image:
                logger.error("Could not obtain base64 image data")
                return None

            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://foodflow.app",
                "X-Title": "FoodFlow Bot",
            }

            vision_models = [
                "qwen/qwen3.5-flash-02-23",
                "google/gemini-3.5-flash-lite",
                "google/gemini-2.0-flash-001",
                "qwen/qwen3-vl-8b-instruct"
            ]

            async with aiohttp.ClientSession() as session:
                for model in vision_models:
                    try:
                        payload = {
                            "model": model,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": prompt},
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{b64_image}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            "temperature": 0.0,
                            "response_format": {"type": "json_object"}
                        }

                        logger.info(f"Vision Analysis: Trying model {model}...")

                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=30 # Increased timeout for Vision
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                content = data['choices'][0]['message']['content']
                                logger.info(f"Vision Analysis ({model}) Raw: {content[:150]}...")
                                
                                # Robust JSON extraction
                                content = content.replace("```json", "").replace("```", "").strip()
                                extracted = _extract_first_json_object(content)
                                if extracted:
                                    content = extracted
                                
                                try:
                                    result = json.loads(content)
                                    return result
                                except json.JSONDecodeError:
                                    logger.error(f"Vision JSON Decode Error ({model}): {content}")
                                    continue # Try next model
                            else:
                                error_text = await response.text()
                                logger.warning(f"Vision API Error ({model}): {response.status} - {error_text}")
                                # Continue to next model
                    except Exception as e:
                        logger.error(f"Vision Analysis Exception ({model}): {e}")
                        # Continue to next model

            logger.error("All Vision models failed.")
            return None

        except Exception as e:
            logger.error(f"Vision Analysis Outer Exception: {e}", exc_info=True)
            return None


    @classmethod
    async def summarize_fridge(cls, product_list: list[str]) -> dict | None:
        """Generate a structured summary (text + tags) of fridge contents."""

        products_str = ", ".join(product_list[:40]) # Limit context window

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot",
        }

        from utils.i18n import get_locale
        locale = get_locale()

        if locale == "es":
            prompt = f"""
            You are a friendly and polite FoodFlow assistant.
            Your task is to analyze the list of products in the fridge and return JSON.
            
            List of products: {products_str}
            
            RETURN JSON object:
            {{
              "summary": "Summary text (max 3 sentences). Tone: friendly, professional, light irony. NO slang.",
              "tags": [
                {{"tag": "Leche", "emoji": "🥛"}},
                {{"tag": "Pollo", "emoji": "🍗"}}
              ]
            }}
            
            Rules for tags:
            - Choose 3-4 keywords for search.
            - CRITICAL: Tags ("tag") must be WORDS that PHYSICALLY exist in the product names.
            - "emoji": Choose ONE standard emoji fitting the meaning. Do not use rare symbols.
            - Example: if there is "Leche Alpura", tag="Leche", emoji="🥛".
            - FORBIDDEN: Inventing categories that are not present in the text.
            - If the list is weird, return an empty list of tags.
            
            Write in Spanish language. ONLY JSON.
            """
        else:
            prompt = f"""
Ты — дружелюбный и вежливый ассистент FoodFlow.
Твоя задача — проанализировать список продуктов в холодильнике и вернуть JSON.

Список продуктов: {products_str}

ВЕРНИ JSON объект:
{{
  "summary": "Текст саммари (макс 3 предложения). Тон: дружелюбный, профессиональный, легкая ирония. НИКАКОГО сленга.",
  "tags": [
    {{"tag": "Молоко", "emoji": "🥛"}},
    {{"tag": "Курица", "emoji": "🍗"}}
  ]
}}

Правила для tags:
- Выбери 3-4 ключевых слова для поиска.
- КРИТИЧНО: Теги ("tag") должны быть СЛОВАМИ, которые ФИЗИЧЕСКИ присутствуют в названиях продуктов.
- "emoji": Подбери ОДИН стандартный эмодзи, подходящий по смыслу. Не используй редкие символы.
- Пример: если есть "Молоко Простоквашино", tag="Молоко", emoji="🥛".
- ЗАПРЕЩЕНО: Придумывать категории, которых нет в тексте.
- Если список странный, верни пустой список тегов.

Пиши на русском языке. ТОЛЬКО JSON.
"""

        payload = {
            "model": cls.MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful culinary assistant. Return ONLY JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }


        # Use semaphore to limit concurrent AI calls
        semaphore = get_ai_semaphore(max_concurrent=5)

        async with semaphore:
            start_time = time.time()
            for attempt in range(2):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=15
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                content = data['choices'][0]['message']['content']
                                # Parse JSON
                                try:
                                    result = json.loads(content)
                                    if "summary" in result:
                                        # Track stats
                                        duration_ms = (time.time() - start_time) * 1000
                                        stats.record_ai_call(duration_ms)
                                        return result
                                except json.JSONDecodeError:
                                    logger.warning(f"AI Summary JSON Error: {content}")
                                    stats.record_error()
                            else:
                                logger.warning(f"AI Summary error {response.status}")
                                stats.record_error()
                except Exception as e:
                    logger.error(f"AI Summary exception: {e}")
                    stats.record_error()

                await asyncio.sleep(0.5)

        return None
