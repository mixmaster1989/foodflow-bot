"""Module for product name normalization and categorization.

Contains:
- NormalizationService: Normalizes OCR-extracted product names using AI models
"""
import json
import logging
import re
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


class NormalizationService:
    """Normalize and categorize product names from OCR results.

    Uses multiple AI models to correct OCR errors, identify real product names,
    preserve brand names and weights, categorize products, and estimate calories.

    Attributes:
        MODELS: List of fallback models ordered by quality (best first)

    Example:
        >>> service = NormalizationService()
        >>> raw = [{'name': 'СЕЛЬКИ насло', 'price': 100.0, 'quantity': 1.0}]
        >>> normalized = await service.normalize_products(raw)
        >>> print(normalized[0]['name'])
        'Масло подсолнечное'

    """

    MODELS: list[str] = [
        "perplexity/sonar",                                    # Free 1: Best quality with web search
        "mistralai/mistral-small-3.2-24b-instruct:free",      # Free 2: Fast & Smart
        "qwen/qwen2.5-vl-32b-instruct:free",                 # Free 3: Working Fallback
        "google/gemini-2.5-flash-lite-preview-09-2025",       # Paid 1: Cheapest ($0.00016)
        "openai/gpt-4.1-mini",                                 # Paid 2: Fastest (471ms)
    ]

    @classmethod
    async def normalize_products(cls, raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize product names and add category/calories information.

        Args:
            raw_items: List of raw items from OCR with 'name', 'price', 'quantity' keys

        Returns:
            List of normalized items with 'name', 'price', 'quantity', 'category', 'calories'
            Falls back to raw items if all models fail

        Note:
            - Preserves brand names (e.g., 'МИЛКА' -> 'Милка')
            - Preserves weight/volume (e.g., '450г', '1л')
            - All names and categories in Russian
            - Tries models in order: Perplexity → Mistral → Qwen

        """
        if not raw_items:
            return []

        # Prepare the list for the prompt
        items_str = "\n".join([f"- {item.get('name', 'Unknown')}" for item in raw_items])

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }

        prompt = (
            "You are a smart receipt assistant. I have a list of raw product names from a Russian grocery receipt. "
            "Many names are abbreviated or contain OCR errors (e.g., 'СЕЛЬКИ насло' -> 'Масло подсолнечное', 'Шинка ВЕЛОСИПЕД' -> 'Ветчина'). "
            "Your task:\n"
            "1. Identify the real product name using web search if needed.\n"
            "2. PRESERVE brand names if recognizable (e.g., 'МИЛКА' -> 'Милка', 'Lays' -> 'Lays').\n"
            "3. PRESERVE weight/volume if present (e.g., '450г', '1л', '200мл').\n"
            "4. Categorize it (e.g., Молочные продукты, Мясо, Овощи, Снеки, Бакалея).\n"
            "5. Estimate calories per 100g.\n"
            "6. Return a JSON object with a list of normalized items. Keep the original order.\n"
            "IMPORTANT: All names and categories MUST be in RUSSIAN language.\n\n"
            "Input List:\n"
            f"{items_str}\n\n"
            "CRITICAL OUTPUT REQUIREMENTS:\n"
            "- Return ONLY the JSON object. Nothing before it, nothing after it.\n"
            "- Do NOT include markdown formatting (no ```json or ```).\n"
            "- Do NOT add explanations, comments, or any text after the JSON.\n"
            "- Your response must start with { and end with }.\n"
            "- Example of CORRECT response: {\"normalized\": [{\"original\": \"...\", \"name\": \"...\", \"category\": \"...\", \"calories\": 123}]}\n"
            "- Example of WRONG response: {\"normalized\": [...]}\n**Пояснения:** ...\n\n"
            "Output Format (JSON ONLY, NO TEXT BEFORE OR AFTER):\n"
            "{\"normalized\": [{\"original\": \"...\", \"name\": \"Название с брендом и весом (RU)\", \"category\": \"Категория (RU)\", \"calories\": 123}]}"
        )

        import asyncio

        for model in cls.MODELS:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            # Retry logic: 3 attempts with 0.5s delay
            for attempt in range(3):
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=60
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                content = result['choices'][0]['message']['content']
                                
                                # Robust JSON extraction - handle all edge cases
                                # Step 1: Try to find JSON in markdown code blocks
                                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                                if json_match:
                                    content = json_match.group(1)
                                else:
                                    # Step 2: Find JSON object that contains "normalized" key
                                    # Use non-greedy match to get the first complete JSON object
                                    json_match = re.search(r'\{[^{}]*"normalized"[^{}]*\}(?:\s*\{[^{}]*\})*', content, re.DOTALL)
                                    if json_match:
                                        # Try to find the complete JSON object by matching braces
                                        start_pos = json_match.start()
                                        brace_count = 0
                                        end_pos = start_pos
                                        for i, char in enumerate(content[start_pos:], start_pos):
                                            if char == '{':
                                                brace_count += 1
                                            elif char == '}':
                                                brace_count -= 1
                                                if brace_count == 0:
                                                    end_pos = i + 1
                                                    break
                                        content = content[start_pos:end_pos]
                                    else:
                                        # Step 3: Fallback - clean markdown and extract first JSON object
                                        content = content.replace("```json", "").replace("```", "").strip()
                                        # Find first { and last } to extract JSON
                                        first_brace = content.find('{')
                                        if first_brace >= 0:
                                            # Count braces to find matching closing brace
                                            brace_count = 0
                                            for i in range(first_brace, len(content)):
                                                if content[i] == '{':
                                                    brace_count += 1
                                                elif content[i] == '}':
                                                    brace_count -= 1
                                                    if brace_count == 0:
                                                        content = content[first_brace:i + 1]
                                                        break

                                try:
                                    parsed = json.loads(content)
                                    normalized_map = {item['original']: item for item in parsed.get('normalized', [])}

                                    # Merge back with original data (price, quantity)
                                    final_items = []
                                    for item in raw_items:
                                        raw_name = item.get('name', 'Unknown')
                                        norm_data = normalized_map.get(raw_name, {})

                                        final_items.append({
                                            "name": norm_data.get('name', raw_name), # Fallback to raw
                                            "price": item.get('price', 0.0),
                                            "quantity": item.get('quantity', 1.0),
                                            "category": norm_data.get('category', 'Uncategorized'),
                                            "calories": norm_data.get('calories', 0)
                                        })
                                    return final_items

                                except json.JSONDecodeError:
                                    logger.error(f"Failed to parse Normalization JSON ({model}): {content}")
                                    # Don't return here, try next model if parsing fails?
                                    # Actually if parsing fails, it might be model specific. Let's continue to next model.
                                    break
                            else:
                                logger.warning(f"Normalization API ({model}) attempt {attempt+1}/3 failed: {response.status}")
                                if attempt < 2:
                                    await asyncio.sleep(0.5)
                                    continue
                    except Exception as e:
                        logger.error(f"Exception in Normalization Service ({model}) attempt {attempt+1}/3: {e}")
                        if attempt < 2:
                            await asyncio.sleep(0.5)
                            continue

            # If we get here, this model failed (network or parsing), try next
            logger.warning(f"Model {model} failed, switching to next...")

        return raw_items
