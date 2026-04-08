import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import json

from sqlalchemy import select, func, desc
from database.base import async_session
from database.models import UserSettings, UserActivity, ConsumptionLog, Product, GuideHistory
from services.ai_brain import AIBrainService
from services.ai import AIService

logger = logging.getLogger(__name__)

class AIGuideService:
    """Core intelligence for the AI Personal Guide."""

    @classmethod
    async def is_active(cls, user_id: int, session) -> bool:
        """Check if Guide is paid and enabled for user."""
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        
        if not settings or not settings.guide_active_until:
             return False
             
        return settings.guide_active_until > datetime.now()

    @classmethod
    async def track_activity(cls, user_id: int, feature: str, session):
        """Log that user used a specific feature."""
        # Check if already logged today for this feature to avoid spamming
        stmt = select(UserActivity).where(
            UserActivity.user_id == user_id, 
            UserActivity.feature_name == feature
        ).order_by(desc(UserActivity.last_used_at)).limit(1)
        
        last_activity = (await session.execute(stmt)).scalar_one_or_none()
        
        if last_activity and (datetime.now() - last_activity.last_used_at).total_seconds() < 3600:
             return # Already logged in the last hour
             
        new_activity = UserActivity(user_id=user_id, feature_name=feature)
        session.add(new_activity)
        await session.commit()

    @classmethod
    async def get_contextual_advice(cls, user_id: int, current_meal: dict, session, stream: bool = False):
        """Generate AI comment for the current meal based on history/fridge."""
        
        # 1. Fetch User Settings & Context
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        if not settings or not settings.guide_active_until or settings.guide_active_until < datetime.now():
            return None

        # 2. Fetch Daily Context (Today's totals)
        from database.models import WaterLog
        today = datetime.now().date()
        
        # Today's food
        today_food_stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == today
        )
        today_items = (await session.execute(today_food_stmt)).scalars().all()
        today_kcal = sum(i.calories for i in today_items)
        today_p = sum(i.protein for i in today_items)
        today_f = sum(i.fat for i in today_items)
        today_c = sum(i.carbs for i in today_items)
        
        # Today's water
        today_water_stmt = select(func.sum(WaterLog.amount_ml)).where(
            WaterLog.user_id == user_id,
            func.date(WaterLog.date) == today
        )
        today_water = (await session.execute(today_water_stmt)).scalar() or 0
        
        # Last 5 items with dates
        hist_stmt = select(ConsumptionLog).where(ConsumptionLog.user_id == user_id).order_by(desc(ConsumptionLog.date)).limit(5)
        history = (await session.execute(hist_stmt)).scalars().all()
        history_desc = "\n".join([f"- {h.date.strftime('%d.%m %H:%M')}: {h.product_name} ({h.calories} ккал)" for h in history])
        
        # 3. Fetch Conversation History (Memory)
        memory_context = await cls.get_history_context(user_id, session)
        
        # 4. Fetch Unused Features (Missions)
        # 1. Fetch used features
        activity_stmt = select(UserActivity.feature_name).where(UserActivity.user_id == user_id).distinct()
        used_features = (await session.execute(activity_stmt)).scalars().all()
        all_feature_list = ["fridge", "recipes", "weight", "water", "shopping_list"]
        unused_features = [f for f in all_feature_list if f not in used_features]
        
        # 5. Fetch Fridge Summary (Optional context)
        fridge_stmt = select(Product).where(Product.user_id == user_id).limit(10)
        fridge_items = (await session.execute(fridge_stmt)).scalars().all()
        fridge_desc = ", ".join([p.name for p in fridge_items]) if fridge_items else "Холодильник пока пуст."
        
        # 6. Build Prompt for AI Brain
        config = settings.guide_config or {}
        personality = config.get("personality", "soft")
        onboarding_answers = config.get("answers", {})

        bot_knowledge = """
ДОСТУПНЫЕ ФУНКЦИИ В БОТЕ:
1. Холодильник (fridge) — хранение продуктов, списание при логировании. Использовать: «📦 Мой холодильник».
2. Рецепты (recipes) — генерация ПП-рецептов из еды в холодильнике. Использовать: «🍳 Рецепты».
3. Вес (weight) — трекинг веса, графики, ИМТ. Использовать: «📈 Вес».
4. Вода (water) — трекер воды. Использовать: «💧 Вода».
5. Списки покупок (shopping_list) — планирование покупок. Использовать: «🛒 Списки».
6. Марафоны (marathons) — групповые активности, баллы (Снежинки), куратор.
"""

        guide_prompt = f"""
Ты — персональный ИИ-гид по питанию и ЭКСПЕРТ по боту FoodFlow. 
Твоя цель: помогать пользователю достигать целей, мотивировать и давать умные советы.

ПЕРСОНАЖ: {personality} (soft=поддерживающий, hard=строгий, direct=аналитический)
ОТВЕТЫ ПОЛЬЗОВАТЕЛЯ ПРИ ОНБОРДИНГЕ: {json.dumps(onboarding_answers, ensure_ascii=False)}

{bot_knowledge}

ПАМЯТЬ ПРЕДЫДУЩИХ ОБЩЕНИЙ (КРАТКО):
{memory_context}

КОНТЕКСТ:
- Текущее время (системное): {datetime.now().strftime('%H:%M')}
- Время приема пищи: {current_meal.get('time', 'не указано')}
- Текущий прием пищи: {current_meal['name']} ({current_meal['calories']} ккал, Б:{current_meal['protein']} Ж:{current_meal['fat']} У:{current_meal['carbs']})

ИТОГИ ЗА СЕГОДНЯ:
- Калории: {today_kcal} / {settings.calorie_goal} ккал
- БЖУ сегодня: Б:{today_p} Ж:{today_f} У:{today_c}
- Выпито воды: {today_water} мл (норма обычно ~2000 мл)

ИСТОРИЯ ПОСЛЕДНИХ ЗАПИСЕЙ:
{history_desc}

- В ХОЛОДИЛЬНИКЕ СЕЙЧАС: {fridge_desc}
- НЕИСПОЛЬЗОВАННЫЕ МОДУЛИ БОТА: {", ".join(unused_features) if unused_features else "Пользователь — эксперт!"}

ЗАДАЧА:
Дай ОЧЕНЬ КРАТКИЙ (1-2 предложения) комментарий к текущему приему пищи.

ИНСТРУКЦИЯ ПО ХАРАКТЕРУ (ПРЕСЕТ: {personality}):
АБСОЛЮТНО ВСЕ СЛОВА ДОЛЖНЫ СООТВЕТСТВОВАТЬ ТВОЕМУ ПРЕСЕТУ:
1. КБЖУ и Состав еды:
   - [hard]: ругай за перебор калорий или "мусорную" еду жестко, язвительно и прямо.
   - [soft]: хвали за любые успехи, а при переборе мягко поддерживай ("ничего страшного, завтра будет лучше").
   - [direct]: давай сухую аналитику без эмоций (например, "перебор дневной нормы жиров на 15%").
2. Обучение функциям бота (перебои в истории, вода, {unused_features}):
   - [hard]: требуй дисциплины в приказном тоне ("иди пей воду", "почему не используешь модуль fridge?").
   - [soft]: ласково напоминай об инструментах ("пожалуйста, не забывай пить воду", "попробуй заглянуть в холодильник").
   - [direct]: констатируй факты системно ("Рекомендуется использовать модуль water для фиксации жидкости").
3. Поздний прием пищи (если время от 23:00 до 05:00):
   - [hard]: высмеивай и стыди за ночные набеги на кухню.
   - [soft]: заботливо советуй ложиться спать, чтобы ЖКТ мог отдохнуть.
   - [direct]: констатируй вред поздних приемов пищи для циркадных ритмов и метаболизма.
"""
        logger.info(f"--- AI GUIDE PROMPT (User: {user_id}) ---\n{guide_prompt[:300]}...\n-----------------------------------")
        try:
             if not stream:
                 response = await AIService.get_completion(guide_prompt)
                 logger.info(f"--- AI GUIDE RESPONSE (User: {user_id}) ---\n{response}\n-------------------------------------")
                 if response:
                     # Save interaction to history
                     user_msg = f"Лог еды: {current_meal['name']} ({current_meal['calories']} ккал)"
                     await cls.save_to_history(user_id, "user", user_msg, session)
                     await cls.save_to_history(user_id, "assistant", response, session)
                     
                     # Check for compression trigger (50k tokens)
                     await cls.check_and_compress(user_id, session)
                     
                 return response
             else:
                 async def stream_generator():
                     from database.base import get_db
                     full_res = ""
                     async for token in AIService.get_completion_stream(guide_prompt):
                         full_res += token
                         yield token
                         
                     if full_res:
                         try:
                             # Use fresh session for delayed DB save
                             async for new_session in get_db():
                                 user_msg = f"Лог еды: {current_meal['name']} ({current_meal['calories']} ккал)"
                                 await cls.save_to_history(user_id, "user", user_msg, new_session)
                                 await cls.save_to_history(user_id, "assistant", full_res, new_session)
                                 await cls.check_and_compress(user_id, new_session)
                                 break
                         except Exception as e:
                             logger.error(f"Failed saving streamed Guide history: {e}")
                 return stream_generator()
        except Exception as e:
             logger.error(f"Failed to get AI Guide advice: {e}")
             return None

    @classmethod
    async def get_water_advice(cls, user_id: int, amount_ml: int, session, stream: bool = False):
        """Generate AI comment for water tracking based on personality and context."""
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        if not settings or not settings.guide_active_until or settings.guide_active_until < datetime.now():
            return None

        from database.models import WaterLog
        today = datetime.now().date()
        
        # Today's water total
        w_stmt = select(func.sum(WaterLog.amount_ml)).where(
            WaterLog.user_id == user_id, 
            func.date(WaterLog.date) == today
        )
        today_water = (await session.execute(w_stmt)).scalar() or 0

        # Last food
        f_stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == today
        ).order_by(desc(ConsumptionLog.date)).limit(1)
        last_food = (await session.execute(f_stmt)).scalar_one_or_none()
        
        last_food_desc = f"{last_food.product_name} ({last_food.calories} ккал)" if last_food else "Сегодня еще не ел"

        config = settings.guide_config or {}
        personality = config.get("personality", "soft")
        onboarding_answers = config.get("answers", {})

        guide_prompt = f"""
Ты — персональный ИИ-гид по питанию. Твоя цель: прокомментировать добавление воды пользователем.
ПЕРСОНАЖ: {personality} (soft=поддерживающий, hard=строгий/токсичный, direct=аналитический/нейтральный)
ВОТ ЧТО МЫ ЗНАЕМ О НЕМ: {json.dumps(onboarding_answers, ensure_ascii=False)}

СИТУАЦИЯ:
- Выпито только что: {amount_ml} мл воды.
- Всего за сегодня (включая это): {today_water} мл (норма ~2000 мл).
- Последняя еда: {last_food_desc}
- Текущее время: {datetime.now().strftime('%H:%M')}

ИНСТРУКЦИЯ (ОЧЕНЬ ВАЖНО: АБСОЛЮТНОЕ СООТВЕТСТВИЕ ПЕРСОНАЖУ):
Твой ответ должен быть ровно 1-2 предложения.
Реагируй на объем, время и последнюю еду, НО ТОЛЬКО В РАМКАХ СВОЕГО ХАРАКТЕРА ({personality}):
1. Если объем ЗАЛПОМ больше 600мл: 
   - [hard]: жестко отругай, скажи, что почки не мусорный бак.
   - [soft]: ласково и с заботой посоветуй пить меньшими порциями.
   - [direct]: сухо констатируй, что разовые порции более 600мл снижают усвоение жидкости и перегружают почки.
2. Если последняя еда тяжелая/соленая/сладкая: 
   - [hard]: "Правильно, смывай тот мусор, что ты съел."
   - [soft]: "Умничка! Вода отлично поможет организму справиться с недавней едой."
   - [direct]: "Грамотное решение. Жидкость необходима для восстановления водно-солевого баланса после последней еды."
3. Время суток (ночь после 22:00):
   - [hard]: "Пьешь на ночь? Готовься к лицу-подушке завтра."
   - [soft]: "Постарайся не пить много на ночь, чтобы проснуться свеженьким без отеков 💙"
   - [direct]: "Потребление жидкости перед сном повышает риск утренних отеков. Рекомендую снизить объем."
4. Хвали за достижение нормы 2000мл (в своем стиле, [direct] - просто фиксирует выполнение плана).
"""
        logger.info(f"--- AI GUIDE WATER PROMPT (User: {user_id}) ---\n{guide_prompt[:250]}...\n-----------------------------------")
        try:
             if not stream:
                 response = await AIService.get_completion(guide_prompt)
                 if response:
                     user_msg = f"Выпил воды: {amount_ml} мл (Итого за день: {today_water} мл)"
                     await cls.save_to_history(user_id, "user", user_msg, session)
                     await cls.save_to_history(user_id, "assistant", response, session)
                     await cls.check_and_compress(user_id, session)
                 return response
             else:
                 async def stream_generator():
                     from database.base import get_db
                     full_res = ""
                     async for token in AIService.get_completion_stream(guide_prompt):
                         full_res += token
                         yield token
                         
                     if full_res:
                         try:
                             # Use fresh session for delayed DB save
                             async for new_session in get_db():
                                 user_msg = f"Выпил воды: {amount_ml} мл (Итого за день: {today_water} мл)"
                                 await cls.save_to_history(user_id, "user", user_msg, new_session)
                                 await cls.save_to_history(user_id, "assistant", full_res, new_session)
                                 await cls.check_and_compress(user_id, new_session)
                                 break
                         except Exception as e:
                             logger.error(f"Failed saving streamed Guide Water history: {e}")
                 return stream_generator()
        except Exception as e:
             logger.error(f"Failed to get AI Water advice: {e}")
             return None

    @classmethod
    def _calculate_tokens(cls, text: str) -> int:
        """Rough estimation of tokens (4 characters = 1 token)."""
        return len(text) // 4

    @classmethod
    async def save_to_history(cls, user_id: int, role: str, content: str, session, is_summary: bool = False):
        """Save a message to guide history."""
        tokens = cls._calculate_tokens(content)
        new_entry = GuideHistory(
            user_id=user_id,
            role=role,
            content=content,
            tokens=tokens,
            is_summary=is_summary
        )
        session.add(new_entry)
        await session.commit()

    @classmethod
    async def get_history_context(cls, user_id: int, session) -> str:
        """Fetch history context for the prompt."""
        stmt = select(GuideHistory).where(GuideHistory.user_id == user_id).order_by(GuideHistory.created_at.asc())
        history = (await session.execute(stmt)).scalars().all()
        
        if not history:
            return "История пуста."
            
        lines = []
        for h in history:
            prefix = "🔔 ИТОГ:" if h.is_summary else f"{h.role.upper()}:"
            lines.append(f"{prefix} {h.content}")
            
        return "\n".join(lines)

    @classmethod
    async def check_and_compress(cls, user_id: int, session):
        """Check token count and trigger compression if > 50k."""
        token_sum_stmt = select(func.sum(GuideHistory.tokens)).where(GuideHistory.user_id == user_id)
        total_tokens = (await session.execute(token_sum_stmt)).scalar() or 0
        
        if total_tokens > 50000:
            logger.info(f"Triggering history compression for user {user_id} ({total_tokens} tokens)")
            await cls.compress_history(user_id, session)

    @classmethod
    async def compress_history(cls, user_id: int, session):
        """Summarize history and replace with a summary entry."""
        context = await cls.get_history_context(user_id, session)
        
        compress_prompt = f"""
Ты — архивариус системы питания FoodFlow. Тебе нужно СЖАТЬ историю общения Гида с пользователем.
Вся эта история будет заменена на твой краткий пересказ.

ЦЕЛЬ: Сохранить ключевые факты (какие продукты любит/не любит, какие ошибки часто совершает, какие советы давал Гид), но убрать лишние детали и повторы.

ИСТОРИЯ ОБЩЕНИЯ:
{context}

ИТОГОВОЕ САММАРИ (максимум 500 токенов):
"""
        summary = await AIService.get_completion(compress_prompt)
        
        if summary:
            # Delete old history
            from sqlalchemy import delete
            del_stmt = delete(GuideHistory).where(GuideHistory.user_id == user_id)
            await session.execute(del_stmt)
            
            # Save new summary
            await cls.save_to_history(user_id, "summary", summary, session, is_summary=True)
            logger.info(f"History compressed for user {user_id}")

    @classmethod
    async def get_mission_for_user(cls, user_id: int, session) -> Optional[str]:
        """Suggest a feature the user hasn't tried yet."""
        # 1. Fetch used features
        stmt = select(UserActivity.feature_name).where(UserActivity.user_id == user_id).distinct()
        used_features = (await session.execute(stmt)).scalars().all()
        
        all_features = ["fridge", "recipes", "weight", "water", "shopping_list"]
        unused = [f for f in all_features if f not in used_features]
        
        if not unused:
             return None # User is a pro!
             
        target = unused[0]
        missions = {
            "fridge": "Я заметил, ты еще не заглядывал в «Холодильник». Попробуй добавить туда продукты, и я помогу тебе не дать им пропасть!",
            "recipes": "Хочешь что-то новенькое? Попробуй сгенерировать ПП-рецепт в разделе «Рецепты».",
            "weight": "Регулярное взвешивание помогает мне точнее давать советы. Запиши свой вес в профиле!",
            "water": "Водный баланс так же важен, как и еда. Отметь стакан воды сегодня!",
            "shopping_list": "Чтобы не покупать лишнего, используй «Список покупок»."
        }
        
        return missions.get(target)
