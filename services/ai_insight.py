import json
import logging
import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.models import User, UserSettings, Subscription
from config import settings

logger = logging.getLogger(__name__)

class AIInsightService:
    MODEL = "google/gemini-2.5-flash-lite-preview-09-2025"
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

    @classmethod
    async def get_user_context(cls, user_id: int, db: AsyncSession) -> str:
        """Fetch deep context about the user for the AI."""
        # 1. Basic Profile with preloaded subscription
        stmt = select(User).where(User.id == user_id).options(selectinload(User.subscription))
        user = (await db.execute(stmt)).scalar_one_or_none()
        
        if not user:
            logger.warning(f"User {user_id} not found for context")
            return ""

        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        user_settings = (await db.execute(settings_stmt)).scalar_one_or_none()
        
        # 2. Recent activity (last 24h)
        # (Simplified for now, can be expanded to summarize habits)
        
        context = []
        name = user.first_name or user.username or "friend"
        context.append(f"User's name is {name}.")
        
        if user_settings:
            gender_label = "Male" if user_settings.gender == "male" else "Female" if user_settings.gender == "female" else "Unknown"
            context.append(f"User is {user_settings.age or 'unknown'} years old, {gender_label}.")
            context.append(f"Goal: {user_settings.goal or 'healthy living'}. Target calories: {user_settings.calorie_goal}kcal.")
        
        # Subscriptions / Tier
        tier = "free"
        if user.subscription:
            tier = user.subscription.tier
        context.append(f"Subscription Tier: {tier.upper()}.")
        
        # Guide Preset
        personality = "soft"
        if user_settings and user_settings.guide_config:
            personality = user_settings.guide_config.get("personality", "soft")
        context.append(f"Guide Preset: {personality}.")
        
        return " ".join(context)

    @classmethod
    async def generate_insight_stream(cls, user_id: int, context: str, action_type: str, action_detail: str):
        """Streams AI commentary via a generator (SSE compatible)."""
        print(f"DEBUG: generate_insight_stream started for user {user_id}")
        
        # Adaptive Persona Prompt (Whisperer)
        personality = "soft"
        if "Guide Preset: hard" in context:
            personality = "hard"
        elif "Guide Preset: direct" in context:
            personality = "direct"

        system_prompt = (
            "Ты — внутренний микро-голос интерфейса (phantom whisper). "
            f"Твой характер: [{personality}] (soft=поддерживающий, hard=строгий, direct=сухой). "
            "Context: {context}. "
            "User just did: {action_type} ({action_detail}). "
            "Task: Прокомментируй это ДЕЙСТВИЕ ровно одним коротким предложением (максимум 15 слов) на русском языке. "
            "CRITICAL: Используй имя из контекста. Не придумывай имена. Без приветствий. Просто быстрая реакция."
        ).format(context=context, action_type=action_type, action_detail=action_detail)

        print(f"DEBUG: whisper system_prompt: {system_prompt}")

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.bot",
            "X-Title": "FoodFlow Phantom Insight"
        }

        payload = {
            "model": cls.MODEL,
            "messages": [
                {"role": "user", "content": system_prompt}
            ],
            "stream": True,
            "temperature": 0.8,
            "max_tokens": 500
        }

        print(f"DEBUG: Starting OpenRouter stream...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(cls.OPENROUTER_URL, headers=headers, json=payload) as response:
                    print(f"DEBUG: OpenRouter status: {response.status}")
                    if response.status != 200:
                        raw_err = await response.text()
                        logger.error(f"OpenRouter Insight Error: {response.status} - {raw_err}")
                        return

                    async for line in response.content:
                        if not line:
                            continue
                        
                        decoded_line = line.decode('utf-8').strip()
                        print(f"DEBUG: raw_line: {decoded_line}")
                        if decoded_line.startswith("data: "):
                            data_str = decoded_line[6:]
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    
                                    reasoning = delta.get("reasoning") or delta.get("thought")
                                    if reasoning:
                                        print(f"DEBUG: AI thinking: {reasoning}", flush=True)

                                    content = delta.get("content")
                                    if content:
                                        print(f"DEBUG: token_found: '{content}'", flush=True)
                                        yield content
                            except Exception as e:
                                print(f"DEBUG: Parse error: {e}, Data: {data_str}", flush=True)
                                continue
        except Exception as e:
            print(f"DEBUG: Stream Exception: {e}")
            logger.error(f"Insight Stream Exception: {e}")
            return
