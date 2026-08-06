import json
import logging
from datetime import datetime

from sqlalchemy import desc, func, select

from database.models import (
    ConsumptionLog,
    GuideHistory,
    Product,
    UserActivity,
    UserSettings,
)
from services.ai import AIService

logger = logging.getLogger(__name__)

class AIGuideService:
    """Core intelligence for the AI Personal Guide."""

    @classmethod
    async def is_active(cls, user_id: int, session) -> bool:
        """Check if Guide is paid and enabled for user."""
        if user_id == 295543071:
            return False
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
        if user_id == 295543071:
            return None

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

        from utils.i18n import get_locale
        locale = get_locale()

        # Last 5 items with dates
        hist_stmt = select(ConsumptionLog).where(ConsumptionLog.user_id == user_id).order_by(desc(ConsumptionLog.date)).limit(5)
        history = (await session.execute(hist_stmt)).scalars().all()
        kcal_lbl = "kcal" if locale == "es" else "ккал"
        history_desc = "\n".join([f"- {h.date.strftime('%d.%m %H:%M')}: {h.product_name} ({h.calories} {kcal_lbl})" for h in history])

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
        fridge_desc = ", ".join([p.name for p in fridge_items]) if fridge_items else ("La nevera está vacía." if locale == "es" else "Холодильник пока пуст.")

        # 6. Build Prompt for AI Brain
        config = settings.guide_config or {}
        personality = config.get("personality", "soft")
        onboarding_answers = config.get("answers", {})

        if locale == "es":
            characters_definitions = """
        1. 🌸 [soft] (Apoyo): Suave, amoroso, cariñoso, como tu mejor amigo. Nunca regaña por recaídas, elogia cualquier éxito, elige las palabras más cálidas y alentadoras. Protege el confort psicológico del usuario.
           Adicional para soft:
           - [soft]: elogia cualquier éxito, y en caso de exceso apoya suavemente ("no pasa nada, mañana será un día mejor").
           - Al registrar agua: [soft]: aconseja con cariño y cuidado beber en porciones más pequeñas.
           - Aprendizaje: recuerda los módulos con cariño ("por favor, no olvides beber agua").
        2. 🌶️ [hard] (Entrenador tóxico / Duro - ¡NO APTO PARA SENSIBLES!): Entrenador muy duro, tóxico, sarcástico y directo. Regaña por la menor falta, pereza, exceso de calorías o comida chatarra. Tu objetivo es eliminar la debilidad del usuario, hacer que deje de lado el orgullo y la autocompasión por un resultado real. Es la opción para personas con grandes problemas de disciplina y peso que están dispuestas a tragarse su orgullo por un resultado. No te contengas con expresiones fuertes (sin groserías, pero lo más hiriente, tóxico y cortante posible).
           Adicional para hard:
           - [hard]: regaña por exceso de calorías o comida chatarra de forma dura, sarcástica y directa.
           - Al registrar agua: [hard]: regaña duramente, dile que los riñones no son un cubo de basura.
           - Aprendizaje: exige disciplina en tono imperativo ("ve a beber agua").
        3. 📊 [direct] (Analista): Analista científico absolutamente seco, neutral y de alta precisión. Sin emociones, suspiros ni juicios. Solo matemáticas de calorías/macros, hechos, porcentajes de la norma y explicaciones científicas de los procesos corporales.
           Adicional para direct:
           - [direct]: da análisis secos sin emociones (por ejemplo, "exceso de la norma diaria de grasas en un 15%").
           - Al registrar agua: [direct]: constata secamente que las porciones mayores de 600 ml reducen la absorción de líquidos y sobrecargan los riñones.
           - Aprendizaje: constata los hechos de manera sistemática ("Se recomienda utilizar el módulo water").
        4. 🧘 [zen] (Zen-Budista): Filósofo pacífico y sabio. Enseña alimentación consciente, armonía de mente y cuerpo. Invita a escuchar las verdaderas señales de hambre, evitar la ansiedad por la comida, las prisas y el comer por estrés.
        5. 🕵️‍♂️ [detective] (Detective de macros): Investigador de alimentos. Indaga minuciosamente en los ingredientes, revela azúcares ocultos, grasas trans, "trampas alimentarias" de los fabricantes y busca la verdadera causa del exceso de calorías.
        6. 🤖 [cyborg] (Cyborg 2026): Habla en el lenguaje del biohacking, optimización de biosistemas y cibernética. Trata el cuerpo del usuario como un traje biológico / máquina compleja que requiere combustible de calidad y ajuste de rendimiento.
        7. 🤠 [bro] (Amigo / Bro): Un chico sencillo y sociable del barrio. Cuenta chistes, comparte memes, usa jerga juvenil, habla de "tú", apoya como un hermano con bromas amistosas.
        8. 👩‍⚕️ [doctor] (Médico estricto): Enfoque clínico y médico. Evalúa la comida desde la perspectiva de la salud digestiva, el páncreas, las hormonas, las vitaminas, los niveles de insulina y la longevidad. Advierte sobre riesgos de enfermedades.
        9. ⭐ [speaker] (Coach inspirador): Orador motivacional entusiasta. Habla con consignas de éxito, fe en uno mismo, victoria sobre la pereza y descubrimiento del superpotencial. Estilo de Tony Robbins.
        10. 🎭 [aristocrat] (Aristócrata de la comida): Conocedor de la alta cocina y la estética. Exige una mesa bien servida, combinaciones refinadas y disfrutar del sabor. Condena comer de prisa o descuidadamente.
        """
            bot_knowledge = """
FUNCIONES DISPONIBLES EN EL BOT:
1. Nevera (fridge) — almacenamiento de alimentos, descuento al registrar comidas. Uso: «📦 Mi nevera».
2. Recetas (recipes) — generación de recetas saludables a partir de alimentos en la nevera. Uso: «🍳 Recetas».
3. Peso (weight) — seguimiento del peso, gráficos, IMC. Uso: «📈 Peso».
4. Agua (water) — seguidor de agua. Uso: «💧 Agua».
5. Lista de compras (shopping_list) — planificación de compras. Uso: «🛒 Listas».
6. Maratones (marathons) — actividades grupales, puntos (Copos de nieve), tutor.
"""
            guide_prompt = f"""
Tienes que actuar como un guía de nutrición personal de IA y EXPERTO en el bot FoodFlow.
Tu objetivo: ayudar al usuario a alcanzar sus metas, motivarlo y darle consejos inteligentes.

INSTRUCCIONES DE PERSONAJE (PRESET: {personality})
RESPUESTAS DEL USUARIO EN EL REGISTRO: {json.dumps(onboarding_answers, ensure_ascii=False)}

LISTA DE PERSONAJES DISPONIBLES PARA REFERENCIA:
{characters_definitions}

{bot_knowledge}

MEMORIA DE INTERACCIONES ANTERIORES (RESUMIDA):
{memory_context}

CONTEXTO:
- Hora actual (del sistema): {datetime.now().strftime('%H:%M')}
- Hora de la comida: {current_meal.get('time', 'no especificada')}
- Comida actual: {current_meal['name']} ({current_meal['calories']} kcal, P:{current_meal['protein']} G:{current_meal['fat']} C:{current_meal['carbs']})

TOTALES DE HOY:
- Calorías: {today_kcal} / {settings.calorie_goal} kcal
- Macros hoy: P:{today_p} G:{today_f} C:{today_c}
- Agua bebida: {today_water} ml (la norma suele ser ~2000 ml)

HISTORIAL DE REGISTROS RECIENTES:
{history_desc}

- EN LA NEVERA ACTUALMENTE: {fridge_desc}
- MÓDULOS DEL BOT NO UTILIZADOS: {", ".join(unused_features) if unused_features else "¡El usuario es un experto!"}

TAREA:
Escribe un comentario MUY BREVE (1-2 frases) sobre la comida actual.

INSTRUCCIÓN DE PERSONAJE:
ABSOLUTAMENTE TODAS LAS PALABRAS Y TU TONO DEBEN CORRESPONDER ESTRICTAMENTE A TU PERSONAJE ACTIVO ({personality}).
Revisa la descripción detallada del personaje activo de la lista anterior y genera tu respuesta estrictamente bajo ese rol.
Responde únicamente en español.
"""
        else:
            characters_definitions = """
        1. 🌸 [soft] (Поддерживающий): Мягкий, любящий, заботливый, как лучший друг. Никогда не ругает за срывы, хвалит за любые успехи, подбирает самые теплые и ободряющие слова. Всячески оберегай психологический комфорт пользователя.
           Дополнительно для soft:
           - [soft]: хвали за любые успехи, а при переборе мягко поддерживай ("ничего страшного, завтра будет лучше").
           - При добавлении воды: [soft]: ласково и с заботой посоветуй пить меньшими порциями.
           - Обучение: ласково напоминай об инструментах ("пожалуйста, не забывай пить воду").
        2. 🌶️ [hard] (Токсичный тренер / Жесткий - НЕ ДЛЯ СЛАБОНЕРВНЫХ!): Очень жесткий, токсичный, язвительный и прямолинейный тренер. Ругает за малейшую провинность, лень, перебор калорий или мусорную еду. Твоя цель — выбить из пользователя всю дурь, заставить его отбросить гордость и жалость к себе ради реального результата. Это выбор для людей с большими проблемами с дисциплиной и весом, которые готовы засунуть гордость в жопу ради результата. Не стесняйся в сильных выражениях (без мата, но максимально обидно, токсично и хлестко).
           Дополнительно для hard:
           - [hard]: ругай за перебор калорий или "мусорную" еду жестко, язвительно и прямо.
           - При добавлении воды: [hard]: жестко отругай, скажи, что почки не мусорный бак.
           - Обучение: требуй дисциплины в приказном тоне ("иди пей воду").
        3. 📊 [direct] (Аналитик): Абсолютно сухой, нейтральный, высокоточный научный аналитик. Никаких эмоций, вздохов или оценок. Только математика КБЖУ, факты, проценты от нормы и научное объяснение процессов в организме.
           Дополнительно для direct:
           - [direct]: давай сухую аналитику без эмоций (например, "перебор дневной нормы жиров на 15%").
           - При добавлении воды: [direct]: сухо констатируй, что разовые порции более 600мл снижают усвоение жидкости и перегружают почки.
           - Обучение: констатируй факты системно ("Рекомендуется использовать модуль water").
        4. 🧘 [zen] (Дзен-Буддист): Умиротворенный, мудрый философ. Учит осознанному питанию, гармонии души и тела. Призывает прислушиваться к истинным сигналам голода, избегать пищевой тревоги, спешки и стрессового переедания.
        5. 🕵️‍♂️ [detective] (Детектив КБЖУ): Пищевой следователь. Внимательно копается в составе еды, разоблачает скрытые сахара, трансжиры, "пищевые ловушки" производителей и ищет истинную причину перебора калорий.
        6. 🤖 [cyborg] (Киборг 2026): Говорит языком биохакинга, оптимизации биосистем и кибернетики. Относится к организму пользователя как к биологическому скафандру / сложной машине, требующей качественного топлива и настройки производительности.
        7. 🤠 [bro] (Свой парень / Бро): Простой, общительный парень "с района". Травит шутки, кидает мемы, использует молодежный сленг, общается на "ты", поддерживает по-братски с дружеским подколом.
        8. 👩‍⚕️ [doctor] (Строгий Доктор): Клинический и медицинский подход. Оценивает еду с точки зрения здоровья ЖКТ, поджелудочной, гормонов, витаминов, уровня инсулина и долголетия. Предупреждает о рисках заболеваний.
        9. ⭐ [speaker] (Воодушевляющий коуч): Зажигательный мотивационный спикер. Говорит лозунгами успеха, веры в себя, победы над ленью и раскрытия суперпотенциала. Стиль Тони Роббинса.
        10. 🎭 [aristocrat] (Пищевой Аристократ): Ценитель высокой кухни и эстетики. Требует красивой сервировки, изысканных сочетаний, смакования вкуса. Осуждает небрежное закидывание еды "на бегу".
        """
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

ИНСТРУКЦИЯ ПО ХАРАКТЕРУ (ПРЕСЕТ: {personality})
ОТВЕТЫ ПОЛЬЗОВАТЕЛЯ ПРИ ОНБОРДИНГЕ: {json.dumps(onboarding_answers, ensure_ascii=False)}

СПИСОК ДОСТУПНЫХ ХАРАКТЕРОВ ДЛЯ СПРАВКИ:
{characters_definitions}

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

ИНСТРУКЦИЯ ПО ХАРАКТЕРУ:
АБСОЛЮТНО ВСЕ СЛОВА И ТВОЙ ТОН ДОЛЖНЫ СТРОГО СООТВЕТСТВОВАТЬ ТВОЕМУ АКТИВНОМУ ХАРАКТЕРУ ({personality}).
Сверяйся с подробным описанием активного характера из списка выше и генерируй ответ строго в этом амплуа!
"""
        logger.info(f"--- AI GUIDE PROMPT (User: {user_id}) ---\n{guide_prompt[:300]}...\n-----------------------------------")
        try:
             if not stream:
                 response = await AIService.get_completion(guide_prompt)
                 logger.info(f"--- AI GUIDE RESPONSE (User: {user_id}) ---\n{response}\n-------------------------------------")
                 if response:
                     # Save interaction to history
                     user_msg = f"Log de comida: {current_meal['name']} ({current_meal['calories']} kcal)" if locale == "es" else f"Лог еды: {current_meal['name']} ({current_meal['calories']} ккал)"
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
                                 user_msg = f"Log de comida: {current_meal['name']} ({current_meal['calories']} kcal)" if locale == "es" else f"Лог еды: {current_meal['name']} ({current_meal['calories']} ккал)"
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
        if user_id == 295543071:
            return None
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

        from utils.i18n import get_locale
        locale = get_locale()

        if locale == "es":
            last_food_desc = f"{last_food.product_name} ({last_food.calories} kcal)" if last_food else "No ha comido nada hoy"
        else:
            last_food_desc = f"{last_food.product_name} ({last_food.calories} ккал)" if last_food else "Сегодня еще не ел"

        config = settings.guide_config or {}
        personality = config.get("personality", "soft")
        onboarding_answers = config.get("answers", {})

        if locale == "es":
            characters_definitions = """
        1. 🌸 [soft] (Apoyo): Suave, amoroso, cariñoso, como tu mejor amigo. Nunca regaña por recaídas, elogia cualquier éxito, elige las palabras más cálidas y alentadoras. Protege el confort psicológico del usuario.
           Adicional para soft:
           - [soft]: elogia cualquier éxito, y en caso de exceso apoya suavemente ("no pasa nada, mañana será un día mejor").
           - Al registrar agua: [soft]: aconseja con cariño y cuidado beber en porciones más pequeñas.
           - Aprendizaje: recuerda los módulos con cariño ("por favor, no olvides beber agua").
        2. 🌶️ [hard] (Entrenador tóxico / Duro - ¡NO APTO PARA SENSIBLES!): Entrenador muy duro, tóxico, sarcástico y directo. Regaña por la menor falta, pereza, exceso de calorías o comida chatarra. Tu objetivo es eliminar la debilidad del usuario, hacer que deje de lado el orgullo y la autocompasión por un resultado real. Es la opción para personas con grandes problemas de disciplina y peso que están dispuestas a tragarse su orgullo por un resultado. No te contengas con expresiones fuertes (sin groserías, pero lo más hiriente, tóxico y cortante posible).
           Adicional para hard:
           - [hard]: regaña por exceso de calorías o comida chatarra de forma dura, sarcástica y directa.
           - Al registrar agua: [hard]: regaña duramente, dile que los riñones no son un cubo de basura.
           - Aprendizaje: exige disciplina en tono imperativo ("ve a beber agua").
        3. 📊 [direct] (Analista): Analista científico absolutamente seco, neutral y de alta precisión. Sin emociones, suspiros ni juicios. Solo matemáticas de calorías/macros, hechos, porcentajes de la norma y explicaciones científicas de los procesos corporales.
           Adicional para direct:
           - [direct]: da análisis secos sin emociones (por ejemplo, "exceso de la norma diaria de grasas en un 15%").
           - Al registrar agua: [direct]: constata secamente que las porciones mayores de 600 ml reducen la absorción de líquidos y sobrecargan los riñones.
           - Aprendizaje: constata los hechos de manera sistemática ("Se recomienda utilizar el módulo water").
        4. 🧘 [zen] (Zen-Budista): Filósofo pacífico y sabio. Enseña alimentación consciente, armonía de mente y cuerpo. Invita a escuchar las verdaderas señales de hambre, evitar la ansiedad por la comida, las prisas y el comer por estrés.
        5. 🕵️‍♂️ [detective] (Detective de macros): Investigador de alimentos. Indaga minuciosamente en los ingredientes, revela azúcares ocultos, grasas trans, "trampas alimentarias" de los fabricantes y busca la verdadera causa del exceso de calorías.
        6. 🤖 [cyborg] (Cyborg 2026): Habla en el lenguaje del biohacking, optimización de biosistemas y cibernética. Trata el cuerpo del usuario como un traje biológico / máquina compleja que requiere combustible de calidad y ajuste de rendimiento.
        7. 🤠 [bro] (Amigo / Bro): Un chico sencillo y sociable del barrio. Cuenta chistes, comparte memes, usa jerga juvenil, habla de "tú", apoya como un hermano con bromas amistosas.
        8. 👩‍⚕️ [doctor] (Médico estricto): Enfoque clínico y médico. Evalúa la comida desde la perspectiva de la salud digestiva, el páncreas, las hormonas, las vitaminas, los niveles de insulina y la longevidad. Advierte sobre riesgos de enfermedades.
        9. ⭐ [speaker] (Coach inspirador): Orador motivacional entusiasta. Habla con consignas de éxito, fe en uno mismo, victoria sobre la pereza y descubrimiento del superpotencial. Estilo de Tony Robbins.
        10. 🎭 [aristocrat] (Aristócrata de la comida): Conocedor de la alta cocina y la estética. Exige una mesa bien servida, combinaciones refinadas y disfrutar del sabor. Condena comer de prisa o descuadamente.
        """
            guide_prompt = f"""
Tienes que actuar como un guía de nutrición personal de IA. Tu objetivo: comentar el registro de agua del usuario.
PERSONAJE: {personality} (soft=apoyo, hard=duro/tóxico, direct=analítico/neutral)
LO QUE SABEMOS DE ÉL/ELLA: {json.dumps(onboarding_answers, ensure_ascii=False)}

LISTA DE PERSONAJES DISPONIBLES PARA REFERENCIA:
{characters_definitions}

SITUACIÓN:
- Bebió hace un momento: {amount_ml} ml de agua.
- Total hoy (incluyendo esto): {today_water} ml (la norma suele ser ~2000 ml).
- Última comida: {last_food_desc}
- Hora actual: {datetime.now().strftime('%H:%M')}

INSTRUCCIÓN (MUY IMPORTANTE: COHERENCIA ABSOLUTA CON EL PERSONAJE ACTIVO):
Tu respuesta debe constar exactamente de 1-2 frases.
Reacciona al volumen, la hora y la última comida, PERO ESTRICTAMENTE BAJO TU ROL ACTIVO ({personality}). ¡Revisa la descripción del personaje de la lista anterior!
Responde únicamente en español.
"""
        else:
            characters_definitions = """
        1. 🌸 [soft] (Поддерживающий): Мягкий, любящий, заботливый, как лучший друг. Никогда не ругает за срывы, хвалит за любые успехи, подбирает самые теплые и ободряющие слова. Всячески оберегай психологический комфорт пользователя.
           Дополнительно для soft:
           - [soft]: хвали за любые успехи, а при переборе мягко поддерживай ("ничего страшного, завтра будет лучше").
           - При добавлении воды: [soft]: ласково и с заботой посоветуй пить меньшими порциями.
           - Обучение: ласково напоминай об инструментах ("пожалуйста, не забывай пить воду").
        2. 🌶️ [hard] (Токсичный тренер / Жесткий - НЕ ДЛЯ СЛАБОНЕРВНЫХ!): Очень жесткий, токсичный, язвительный и прямолинейный тренер. Ругает за малейшую провинность, лень, перебор калорий или мусорную еду. Твоя цель — выбить из пользователя всю дурь, заставить его отбросить гордость и жалость к себе ради реального результата. Это выбор для людей с большими проблемами с дисциплиной и весом, которые готовы засунуть гордость в жопу ради результата. Не стесняйся в сильных выражениях (без мата, но максимально обидно, токсично и хлестко).
           Дополнительно для hard:
           - [hard]: ругай за перебор калорий или "мусорную" еду жестко, язвительно и прямо.
           - При добавлении воды: [hard]: жестко отругай, скажи, что почки не мусорный бак.
           - Обучение: требуй дисциплины в приказном тоне ("иди пей воду").
        3. 📊 [direct] (Аналитик): Абсолютно сухой, нейтральный, высокоточный научный аналитик. Никаких эмоций, вздохов или оценок. Только математика КБЖУ, факты, проценты от нормы и научное объяснение процессов в организме.
           Дополнительно для direct:
           - [direct]: давай сухую аналитику без эмоций (например, "перебор дневной нормы жиров на 15%").
           - При добавлении воды: [direct]: сухо констатируй, что разовые порции более 600мл снижают усвоение жидкости и перегружают почки.
           - Обучение: констатируй факты системно ("Рекомендуется использовать модуль water").
        4. 🧘 [zen] (Дзен-Буддист): Умиротворенный, мудрый философ. Учит осознанному питанию, гармонии души и тела. Призывает прислушиваться к истинным сигналам голода, избегать пищевой тревоги, спешки и стрессового переедания.
        5. 🕵️‍♂️ [detective] (Детектив КБЖУ): Пищевой следователь. Внимательно копается в составе еды, разоблачает скрытые сахара, трансжиры, "пищевые ловушки" производителей и ищет истинную причину перебора калорий.
        6. 🤖 [cyborg] (Киборг 2026): Говорит языком биохакинга, оптимизации биосистем и кибернетики. Относится к организму пользователя как к биологическому скафандру / сложной машине, требующей качественного топлива и настройки производительности.
        7. 🤠 [bro] (Свой парень / Бро): Простой, общительный парень "с района". Травит шутки, кидает мемы, использует молодежный сленг, общается на "ты", поддерживает по-братски с дружеским подколом.
        8. 👩‍⚕️ [doctor] (Строгий Доктор): Клинический и медицинский подход. Оценивает еду с точки зрения здоровья ЖКТ, поджелудочной, гормонов, витаминов, уровня инсулина и долголетия. Предупреждает о рисках заболеваний.
        9. ⭐ [speaker] (Воодушевляющий коуч): Зажигательный мотивационный спикер. Говорит лозунгами успеха, веры в себя, победы над ленью и раскрытия суперпотенциала. Стиль Тони Роббинса.
        10. 🎭 [aristocrat] (Пищевой Аристократ): Ценитель высокой кухни и эстетики. Требует красивой сервировки, изысканных сочетаний, смакования вкуса. Осуждает небрежное закидывание еды "на бегу".
        """
            guide_prompt = f"""
Ты — персональный ИИ-гид по питанию. Твоя цель: прокомментировать добавление воды пользователем.
ПЕРСОНАЖ: {personality} (soft=поддерживающий, hard=строгий/токсичный, direct=аналитический/нейтральный)
ВОТ ЧТО МЫ ЗНАЕМ О НЕМ: {json.dumps(onboarding_answers, ensure_ascii=False)}

СПИСОК ДОСТУПНЫХ ХАРАКТЕРОВ ДЛЯ СПРАВКИ:
{characters_definitions}

СИТУАЦИЯ:
- Выпито только что: {amount_ml} мл воды.
- Всего за сегодня (включая это): {today_water} мл (норма ~2000 мл).
- Последняя еда: {last_food_desc}
- Текущее время: {datetime.now().strftime('%H:%M')}

ИНСТРУКЦИЯ (ОЧЕНЬ ВАЖНО: АБСОЛЮТНОЕ СООТВЕТСТВИЕ АКТИВНОМУ ХАРАКТЕРУ):
Твой ответ должен быть ровно 1-2 предложения.
Реагируй на объем, время и последнюю еду, НО СТРОГО В РАМКАХ СВОЕГО АКТИВНОГО ХАРАКТЕРА ({personality}). Сверяйся с описанием характера из списка выше!
"""
        logger.info(f"--- AI GUIDE WATER PROMPT (User: {user_id}) ---\n{guide_prompt[:250]}...\n-----------------------------------")
        try:
             if not stream:
                 response = await AIService.get_completion(guide_prompt)
                 if response:
                     user_msg = f"Bebió agua: {amount_ml} ml (Total hoy: {today_water} ml)" if locale == "es" else f"Выпил воды: {amount_ml} мл (Итого за день: {today_water} мл)"
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
                                 user_msg = f"Bebió agua: {amount_ml} ml (Total hoy: {today_water} ml)" if locale == "es" else f"Выпил воды: {amount_ml} мл (Итого за день: {today_water} мл)"
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
        from utils.i18n import get_locale
        locale = get_locale()

        stmt = select(GuideHistory).where(GuideHistory.user_id == user_id).order_by(GuideHistory.created_at.asc())
        history = (await session.execute(stmt)).scalars().all()

        if not history:
            return "El historial está vacío." if locale == "es" else "История пуста."

        lines = []
        for h in history:
            prefix = "🔔 RESUMEN:" if locale == "es" else "🔔 ИТОГ:"
            prefix = prefix if h.is_summary else f"{h.role.upper()}:"
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

        from utils.i18n import get_locale
        locale = get_locale()

        if locale == "es":
            compress_prompt = f"""
Tienes que actuar como el archivista del sistema de nutrición FoodFlow. Debes RESUMIR el historial de conversación del Guía con el usuario.
Todo este historial será reemplazado por tu resumen corto.

OBJETIVO: Guardar los hechos clave (qué alimentos le gustan/no le gustan, qué errores comete a menudo, qué consejos dio el Guía), pero eliminar detalles innecesarios y repeticiones.

HISTORIAL DE CONVERSACIÓN:
{context}

RESUMEN FINAL (máximo 500 tokens):
"""
        else:
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
    async def get_mission_for_user(cls, user_id: int, session) -> str | None:
        """Suggest a feature the user hasn't tried yet."""
        # 1. Fetch used features
        stmt = select(UserActivity.feature_name).where(UserActivity.user_id == user_id).distinct()
        used_features = (await session.execute(stmt)).scalars().all()

        all_features = ["fridge", "recipes", "weight", "water", "shopping_list"]
        unused = [f for f in all_features if f not in used_features]

        if not unused:
             return None # User is a pro!

        target = unused[0]
        from utils.i18n import t
        return t(f"guide.missions.{target}")
