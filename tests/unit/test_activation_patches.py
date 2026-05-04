"""Тесты для activation-правок 2026-04-23.

Покрывают 4 точки, где воронка новых пользователей теряла людей:
1. Финальный экран онбординга (handlers/onboarding.py::finish_onboarding_process)
2. Quick-food кнопки в i_ate (handlers/i_ate.py::i_ate_start)
3. Drip day1 — живой вопрос без кнопок (services/scheduler.py::send_trial_drip)
4. First log nudge — без кнопок (services/scheduler.py::send_first_log_nudge)
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from database.models import PAYMENT_SOURCE_TRIAL, Subscription, User, UserSettings


# ============================================================
# ПРАВКА №1 — Финальный экран онбординга
# ============================================================

@pytest.mark.asyncio
async def test_finish_onboarding_has_no_inline_buttons(
    db_session, mock_callback_query, mock_fsm_context, sample_user
):
    """После завершения онбординга НЕТ никаких inline-кнопок (правка 2026-04-24).

    Эволюция экрана:
    - До 23.04: 3 кнопки (📸 Отправить фото, Холодильник, Меню) — часть врала.
    - 23.04 выкат: 1 кнопка «🏠 В меню позже» — единственный безобидный выход.
    - 24.04 (эта правка): 0 кнопок. «В меню позже» работала как lifeline —
      сам бот предлагал отложить, юзеры уходили. Теперь только текст с призывом
      что-нибудь написать/сказать/сфоткать (universal_input всё ловит stateless).
    """
    from handlers.onboarding import handle_goal_accept

    mock_callback_query.message.chat.id = sample_user.id
    mock_callback_query.message.chat.first_name = "Тест"
    mock_fsm_context.get_data = AsyncMock(
        return_value={
            "gender": "male", "age": 30, "height": 180, "weight": 80.0, "goal": "lose_weight",
            "pending_targets": {"calories": 2000, "protein": 150, "fat": 60, "carbs": 200},
        }
    )
    mock_fsm_context.clear = AsyncMock()
    mock_callback_query.message.delete = AsyncMock()
    mock_callback_query.message.answer = AsyncMock()

    with patch("handlers.onboarding.get_db") as mock_get_db:
        async def db_gen():
            yield db_session
        mock_get_db.return_value = db_gen()

        await handle_goal_accept(mock_callback_query, mock_fsm_context)

    assert mock_callback_query.message.answer.called, "finish screen должен быть отправлен"
    # Берём ПЕРВЫЙ вызов: финальный текст без кнопок.
    # Второй вызов — «горячий» вопрос с кнопками onboard_ate_yes/no (добавлен 27.04).
    call_kwargs = mock_callback_query.message.answer.call_args_list[0]
    reply_markup = call_kwargs.kwargs.get("reply_markup")
    finish_text = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("text", "")

    # Не должно быть никакой inline-клавиатуры (lifeline убрана)
    assert reply_markup is None, \
        f"Инлайн-кнопок быть не должно (lifeline убрана), получено: {reply_markup}"

    # Текст должен приглашать к свободному вводу
    assert "напиши" in finish_text.lower() or "сфоткай" in finish_text.lower(), \
        "Финальный текст должен звать к свободному вводу"

    # И должен быть «эвакуационный выход» для тех, кто ещё не ел, — без кнопки, текстом
    assert "ещё не ел" in finish_text.lower(), \
        "Должна быть подсказка для тех, кто ещё не ел — напиши «ещё не ел»"


@pytest.mark.asyncio
async def test_finish_onboarding_uses_chat_first_name(
    db_session, mock_callback_query, mock_fsm_context, sample_user
):
    """Обращение в финальном экране берётся из message.chat.first_name.

    Это важно: в callback-контексте message.from_user = бот, а настоящее имя — в chat.first_name.
    """
    from handlers.onboarding import handle_goal_accept

    mock_callback_query.message.chat.id = sample_user.id
    mock_callback_query.message.chat.first_name = "Игорь"
    mock_fsm_context.get_data = AsyncMock(
        return_value={
            "gender": "male", "age": 30, "height": 180, "weight": 80.0, "goal": "lose_weight",
            "pending_targets": {"calories": 2000, "protein": 150, "fat": 60, "carbs": 200},
        }
    )
    mock_fsm_context.clear = AsyncMock()
    mock_callback_query.message.delete = AsyncMock()
    mock_callback_query.message.answer = AsyncMock()

    with patch("handlers.onboarding.get_db") as mock_get_db:
        async def db_gen():
            yield db_session
        mock_get_db.return_value = db_gen()

        await handle_goal_accept(mock_callback_query, mock_fsm_context)

    # Берём первый вызов: финальный текст с именем. Второй — «горячий» вопрос без имени.
    call_args = mock_callback_query.message.answer.call_args_list[0]
    finish_text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
    assert "Игорь" in finish_text, "Имя из chat.first_name должно быть в тексте"


@pytest.mark.asyncio
async def test_finish_onboarding_fallback_name_when_no_first_name(
    db_session, mock_callback_query, mock_fsm_context, sample_user
):
    """Если chat.first_name=None, используется fallback 'друг'."""
    from handlers.onboarding import handle_goal_accept

    mock_callback_query.message.chat.id = sample_user.id
    mock_callback_query.message.chat.first_name = None
    mock_fsm_context.get_data = AsyncMock(
        return_value={
            "gender": "male", "age": 30, "height": 180, "weight": 80.0, "goal": "lose_weight",
            "pending_targets": {"calories": 2000, "protein": 150, "fat": 60, "carbs": 200},
        }
    )
    mock_fsm_context.clear = AsyncMock()
    mock_callback_query.message.delete = AsyncMock()
    mock_callback_query.message.answer = AsyncMock()

    with patch("handlers.onboarding.get_db") as mock_get_db:
        async def db_gen():
            yield db_session
        mock_get_db.return_value = db_gen()

        await handle_goal_accept(mock_callback_query, mock_fsm_context)

    # Берём первый вызов: финальный текст с fallback именем. Второй — «горячий» вопрос.
    call_args = mock_callback_query.message.answer.call_args_list[0]
    finish_text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
    assert "друг" in finish_text, "Должен быть fallback 'друг'"


# ============================================================
# ПРАВКА №2 — i_ate_start без quick_food кнопок для первого раза
# ============================================================

@pytest.mark.asyncio
async def test_i_ate_start_no_quick_food_buttons_for_new_users(
    mock_callback_query, mock_fsm_context
):
    """i_ate_start больше НИКОГДА не показывает quick_food кнопки.

    Раньше для is_first_time=True было 4 кнопки: 🍳 Яичница, 🥪 Бутер, 🥣 Каша, 🧀 Творог.
    Они сбивали тех, кто ел не это. Теперь — единый экран для всех.
    """
    from handlers.i_ate import i_ate_start

    mock_callback_query.answer = AsyncMock()
    mock_callback_query.message.edit_media = AsyncMock()
    mock_callback_query.message.delete = AsyncMock()
    mock_callback_query.message.answer_photo = AsyncMock()
    mock_fsm_context.set_state = AsyncMock()

    await i_ate_start(mock_callback_query, mock_fsm_context)

    # Достаём reply_markup из edit_media
    assert mock_callback_query.message.edit_media.called, "должен вызвать edit_media"
    call = mock_callback_query.message.edit_media.call_args
    reply_markup = call.kwargs["reply_markup"]
    buttons = [btn for row in reply_markup.inline_keyboard for btn in row]
    callbacks = {btn.callback_data for btn in buttons}

    # Quick food callback'ы не должны присутствовать
    assert not any(cb and cb.startswith("quick_food:") for cb in callbacks), \
        f"quick_food кнопки должны быть удалены, найдено: {callbacks}"
    assert "i_ate_manual" not in callbacks, "i_ate_manual (из first_time ветки) должен быть удалён"

    # Должны быть: ⭐ Мои блюда, 🏗️ Собрать блюдо, ❌ Отмена
    assert "menu_saved_dishes" in callbacks, "должна быть кнопка Мои блюда"
    assert "menu_build_dish" in callbacks, "должна быть кнопка Собрать блюдо"
    assert "main_menu" in callbacks, "должна быть кнопка Отмена"


@pytest.mark.asyncio
async def test_i_ate_start_does_not_query_consumption_count(
    mock_callback_query, mock_fsm_context
):
    """Правка убирает лишний DB-запрос count(consumption_logs).

    Мы больше не проверяем is_first_time, поэтому не нужно ходить в БД для подсчёта логов.
    """
    from handlers.i_ate import i_ate_start

    mock_callback_query.answer = AsyncMock()
    mock_callback_query.message.edit_media = AsyncMock()
    mock_fsm_context.set_state = AsyncMock()

    # patch get_db чтобы убедиться что он НЕ вызван
    with patch("handlers.i_ate.get_db") as mock_get_db:
        await i_ate_start(mock_callback_query, mock_fsm_context)
        assert not mock_get_db.called, \
            "get_db не должен вызываться в i_ate_start — убрали is_first_time проверку"


@pytest.mark.asyncio
async def test_i_ate_start_sets_waiting_for_description(
    mock_callback_query, mock_fsm_context
):
    """i_ate_start устанавливает FSM state waiting_for_description — чтобы ловить ввод."""
    from handlers.i_ate import i_ate_start, IAteStates

    mock_callback_query.answer = AsyncMock()
    mock_callback_query.message.edit_media = AsyncMock()
    mock_fsm_context.set_state = AsyncMock()

    await i_ate_start(mock_callback_query, mock_fsm_context)
    mock_fsm_context.set_state.assert_called_once_with(IAteStates.waiting_for_description)


# ============================================================
# ПРАВКА №3 — Drip Day 1: живой вопрос без кнопок
# ============================================================

@pytest.mark.asyncio
async def test_drip_day1_has_no_buttons(db_session):
    """Drip day1 должен быть БЕЗ inline-кнопок.

    Раньше была кнопка '📸 Попробовать фото' — превращала сообщение в рассылку
    и провоцировала блокировки. Теперь — живой вопрос, ответ ловится universal_input.
    """
    from services.scheduler import send_trial_drip

    # Создаём юзера с триалом, которому пора отправить day1 (46-50 часов до истечения)
    user_id = 77777777
    user = User(id=user_id, username="dripper", is_verified=True)
    db_session.add(user)
    # Триал закончится через 48 часов -> попадаем в окно day1
    sub = Subscription(
        user_id=user_id,
        tier="pro",
        starts_at=datetime.now() - timedelta(hours=24),
        expires_at=datetime.now() + timedelta(hours=48),
        is_active=True,
        telegram_payment_charge_id=None,  # триал
        payment_source=PAYMENT_SOURCE_TRIAL,
    )
    db_session.add(sub)
    await db_session.commit()

    bot = MagicMock()
    bot.send_message = AsyncMock()

    with patch("services.scheduler.get_db") as mock_get_db:
        async def db_gen():
            yield db_session
        mock_get_db.return_value = db_gen()

        await send_trial_drip(bot)

    assert bot.send_message.called, "day1 должен быть отправлен"
    call_kwargs = bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == user_id
    assert call_kwargs.get("reply_markup") is None, \
        f"day1 должен быть без кнопок, получено: {call_kwargs.get('reply_markup')}"


@pytest.mark.asyncio
async def test_drip_day1_text_is_personal_question(db_session):
    """Текст day1 — это личный вопрос, а не рекламная рассылка."""
    from services.scheduler import send_trial_drip

    user_id = 88888888
    user = User(id=user_id, username="dripper2", is_verified=True)
    db_session.add(user)
    sub = Subscription(
        user_id=user_id,
        tier="pro",
        starts_at=datetime.now() - timedelta(hours=24),
        expires_at=datetime.now() + timedelta(hours=48),
        is_active=True,
        telegram_payment_charge_id=None,
        payment_source=PAYMENT_SOURCE_TRIAL,
    )
    db_session.add(sub)
    await db_session.commit()

    bot = MagicMock()
    bot.send_message = AsyncMock()

    with patch("services.scheduler.get_db") as mock_get_db:
        async def db_gen():
            yield db_session
        mock_get_db.return_value = db_gen()

        await send_trial_drip(bot)

    text = bot.send_message.call_args.kwargs["text"]
    # Это личный вопрос
    assert "что ты ел" in text.lower() or "что ты ела" in text.lower(), \
        f"day1 должен содержать живой вопрос про еду, текст: {text[:200]}"
    # Не рекламный тон
    assert "у тебя PRO-доступ" not in text, "убрали рекламный тон про PRO-доступ"
    assert "Попробуй сейчас, пока PRO активен" not in text, "убрали рекламный CTA"


@pytest.mark.asyncio
async def test_drip_day2_still_has_subscriptions_button(db_session):
    """Day2 сохраняет кнопку '💎 Подписки' — это момент когда уже пора продавать."""
    from services.scheduler import send_trial_drip

    user_id = 99999999
    user = User(id=user_id, username="dripper3", is_verified=True)
    db_session.add(user)
    # Попадаем в окно day2 (22-26 часов до истечения)
    sub = Subscription(
        user_id=user_id,
        tier="pro",
        starts_at=datetime.now() - timedelta(hours=48),
        expires_at=datetime.now() + timedelta(hours=24),
        is_active=True,
        telegram_payment_charge_id=None,
        payment_source=PAYMENT_SOURCE_TRIAL,
    )
    db_session.add(sub)
    await db_session.commit()

    bot = MagicMock()
    bot.send_message = AsyncMock()

    with patch("services.scheduler.get_db") as mock_get_db:
        async def db_gen():
            yield db_session
        mock_get_db.return_value = db_gen()

        await send_trial_drip(bot)

    assert bot.send_message.called
    reply_markup = bot.send_message.call_args.kwargs.get("reply_markup")
    assert reply_markup is not None, "day2 должен иметь кнопки"
    buttons = [btn for row in reply_markup.inline_keyboard for btn in row]
    callbacks = {btn.callback_data for btn in buttons}
    assert "show_subscriptions" in callbacks, "day2 должен вести на подписки"


# ============================================================
# ПРАВКА №4 — First Log Nudge без кнопок
# ============================================================

@pytest.mark.asyncio
async def test_first_log_nudge_has_no_buttons(db_session):
    """Nudge для не-логировавших теперь без inline-кнопок — чтобы походило на живое сообщение."""
    from services.scheduler import send_first_log_nudge

    # Юзер настроил профиль > 3 часов назад, но еду не логировал
    user_id = 55555555
    user = User(
        id=user_id,
        username="nudger",
        is_verified=True,
        created_at=datetime.now() - timedelta(hours=5),
        first_name="Миша",
    )
    db_session.add(user)
    settings_obj = UserSettings(
        user_id=user_id,
        gender="male",
        age=30,
        height=180,
        weight=80.0,
        goal="lose_weight",
        calorie_goal=2000,
        protein_goal=150,
        fat_goal=60,
        carb_goal=200,
        is_initialized=True,
    )
    db_session.add(settings_obj)
    await db_session.commit()

    bot = MagicMock()

    # safe_send_message — обёртка, которая вызывает bot.send_message
    async def fake_safe_send(bot_, user_id_, text, **kwargs):
        await bot_.send_message(chat_id=user_id_, text=text, **kwargs)
        return True

    bot.send_message = AsyncMock()

    with patch("services.scheduler.get_db") as mock_get_db, \
         patch("services.scheduler.safe_send_message", side_effect=fake_safe_send):
        async def db_gen():
            yield db_session
        mock_get_db.return_value = db_gen()

        await send_first_log_nudge(bot)

    assert bot.send_message.called, "nudge должен быть отправлен"
    call_kwargs = bot.send_message.call_args.kwargs
    # reply_markup НЕ должен передаваться
    assert "reply_markup" not in call_kwargs or call_kwargs.get("reply_markup") is None, \
        f"nudge должен быть без кнопок: {call_kwargs}"

    # В тексте должно быть имя юзера и инструкция напрямую писать
    text = call_kwargs["text"]
    assert "Миша" in text, "должно быть обращение по имени"
    assert "напиши" in text.lower(), "должна быть прямая инструкция — писать ответ"


# ============================================================
# ПРАВКА №5 (2026-04-24) — Кнопки экрана подтверждения «Я съел»
# ============================================================

@pytest.mark.asyncio
async def test_confirmation_interface_split_button_is_highlighted(mock_fsm_context):
    """Кнопка «Это несколько блюд» заметна: без ❌, стоит отдельной строкой выше редактирования.

    Why: Julia (24.04) наговорила 6 продуктов голосом, AI Brain выдал только один.
    На экране подтверждения было «❌ Это несколько продуктов» рядом с «❌ Отмена» —
    она восприняла оба крестика как «не то» и ушла в главное меню, потеряв весь ввод.

    Теперь кнопка идёт через 🍱, без ❌, и стоит на своей строке между
    «сохранить сейчас» и «редактировать вес/КБЖУ» — чтобы её было видно, но она
    не соревновалась за внимание с «сохранить».
    """
    from handlers.i_ate import show_confirmation_interface

    mock_fsm_context.get_data = AsyncMock(return_value={
        "pending_product": {
            "name": "гречка 200 г (200г)",
            "base_name": "гречка",
            "calories100": 326.0,
            "protein100": 10.7,
            "fat100": 6.6,
            "carbs100": 50.4,
            "fiber100": 3.5,
        }
    })
    mock_fsm_context.set_state = AsyncMock()

    message = MagicMock()
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()

    await show_confirmation_interface(message, mock_fsm_context)

    assert message.answer.called, "экран подтверждения должен быть отправлен"
    reply_markup = message.answer.call_args.kwargs["reply_markup"]
    rows = reply_markup.inline_keyboard

    # Все кнопки плоским списком
    all_buttons = [btn for row in rows for btn in row]
    callbacks = [btn.callback_data for btn in all_buttons]
    texts = [btn.text for btn in all_buttons]

    # Базовая проверка: сохранены все нужные callback'ы
    for expected in ("i_ate_confirm_now", "i_ate_ask_time", "u_split_to_batch",
                     "edit_field_weight", "i_ate_edit_macros", "main_menu"):
        assert expected in callbacks, f"callback {expected!r} должен присутствовать"

    # Найти кнопку split и её текст
    split_btn = next(b for b in all_buttons if b.callback_data == "u_split_to_batch")
    assert "❌" not in split_btn.text, \
        f"У кнопки split не должно быть ❌ (она не отмена), текст: {split_btn.text!r}"
    assert "🍱" in split_btn.text, \
        f"У кнопки split должен быть позитивный эмодзи 🍱, текст: {split_btn.text!r}"

    # Split-кнопка должна быть одна в своей строке — чтобы не терялась между другими
    for row in rows:
        if any(b.callback_data == "u_split_to_batch" for b in row):
            assert len(row) == 1, \
                f"Кнопка split должна быть одна в строке, а в строке их {len(row)}"
            break
    else:
        raise AssertionError("Кнопка u_split_to_batch должна быть где-то в разметке")

    # Cancel/main_menu тоже сохраняет ❌ — но только она
    cancel_btns = [b for b in all_buttons if "❌" in b.text]
    assert len(cancel_btns) == 1, \
        f"Ровно одна кнопка с ❌ (только Отмена), получено {len(cancel_btns)}: {[b.text for b in cancel_btns]}"


@pytest.mark.asyncio
async def test_confirmation_interface_save_is_first(mock_fsm_context):
    """Сохранение — первая строка (визуально главный путь)."""
    from handlers.i_ate import show_confirmation_interface

    mock_fsm_context.get_data = AsyncMock(return_value={
        "pending_product": {
            "name": "тест", "base_name": "тест",
            "calories100": 100, "protein100": 10, "fat100": 5, "carbs100": 20, "fiber100": 1,
        }
    })
    mock_fsm_context.set_state = AsyncMock()

    message = MagicMock()
    message.answer = AsyncMock()

    await show_confirmation_interface(message, mock_fsm_context)

    rows = message.answer.call_args.kwargs["reply_markup"].inline_keyboard
    first_row_callbacks = {btn.callback_data for btn in rows[0]}
    assert "i_ate_confirm_now" in first_row_callbacks, \
        "Первая строка должна содержать кнопку сохранения"


# ============================================================
# ПРАВКА №6 (2026-04-24) — AI Brain на актуальной модели + промпт
# на голосовой поток без пунктуации
# ============================================================

def test_ai_brain_uses_current_model():
    """AIBrainService использует актуальную модель gemini 3.1 flash-lite.

    Why: 24.04 Julia проговорила голосом 6 разных блюд («гречка 200 г 50 г рыбы
    кофе чёрный суп рыбный чай кефир») — старая модель gemini-2.5-flash-lite-preview
    не распознала это как multi и выдала один продукт «гречка 200 г». Обновление
    до 3.1-flash-lite-preview + усиленный промпт должны ловить такие случаи.
    """
    from services.ai_brain import AIBrainService
    assert AIBrainService.MODEL == "google/gemini-3.1-flash-lite-preview", \
        f"Модель должна быть gemini-3.1-flash-lite-preview, сейчас: {AIBrainService.MODEL}"
    # Явно проверяем что старая preview-модель убрана
    assert "2.5-flash-lite-preview" not in AIBrainService.MODEL, \
        "Старая 2.5-flash-lite-preview должна быть заменена"


def test_ai_brain_prompt_covers_voice_stream():
    """Промпт содержит пример голосового потока без пунктуации."""
    from services.ai_brain import AIBrainService
    prompt = AIBrainService.SYSTEM_PROMPT

    # Должен быть явный раздел про speech-to-text / голосовой ввод
    assert "ГОЛОСОВОЙ ВВОД" in prompt or "голосов" in prompt.lower(), \
        "Промпт должен явно инструктировать про голосовой поток"

    # И живой пример из наблюдённого кейса (гречка + рыба + кофе + кефир)
    assert "гречка" in prompt.lower() and "кефир" in prompt.lower(), \
        "Промпт должен содержать пример слитного голосового ввода с разными блюдами"


@pytest.mark.asyncio
async def test_ai_brain_analyze_text_multi_flow_parses_response(aioresp):
    """analyze_text корректно парсит multi-ответ модели на голосовой кейс Julia."""
    from services.ai_brain import AIBrainService

    # Эмулируем правильный ответ новой модели на кейс Julia
    aioresp.post(
        "https://openrouter.ai/api/v1/chat/completions",
        payload={
            "choices": [{
                "message": {
                    "content": (
                        '{"intent":"log_consumption","multi":true,'
                        '"items":['
                        '{"product":"гречка","weight":200},'
                        '{"product":"отварная рыба","weight":50},'
                        '{"product":"кофе чёрный","weight":null},'
                        '{"product":"суп рыбный с перловкой","weight":null},'
                        '{"product":"чай с лимоном","weight":null},'
                        '{"product":"кефир стакан","weight":null}'
                        '],"original_text":"..."}'
                    )
                }
            }]
        }
    )

    result = await AIBrainService.analyze_text(
        "гречка 200 г 50 г отварной рыбы кофе чёрный суп рыбный с перловкой чай с лимоном кефир стакан"
    )

    assert result is not None
    assert result.get("multi") is True, "Должен быть multi=true"
    assert len(result.get("items", [])) == 6, \
        f"Ожидали 6 блюд из голосового ввода, получено {len(result.get('items', []))}"
    names = [it["product"] for it in result["items"]]
    assert any("греч" in n.lower() for n in names), "гречка должна быть в списке"
    assert any("кефир" in n.lower() for n in names), "кефир должен быть в списке"


@pytest.mark.asyncio
async def test_ai_brain_analyze_text_single_dish_stays_single(aioresp):
    """Регрессия: «салат с огурцами и помидорами» остаётся ОДНИМ блюдом, не расщепляется."""
    from services.ai_brain import AIBrainService

    aioresp.post(
        "https://openrouter.ai/api/v1/chat/completions",
        payload={
            "choices": [{
                "message": {
                    "content": (
                        '{"intent":"log_consumption","multi":false,'
                        '"product":"Салат из огурцов и помидоров","weight":150,'
                        '"quantity":1,"original_text":"..."}'
                    )
                }
            }]
        }
    )

    result = await AIBrainService.analyze_text("Салат из огурцов и помидоров 150г")
    assert result is not None
    assert result.get("multi") is False, "Салат не должен расщепляться на огурцы и помидоры"
    assert "салат" in result.get("product", "").lower()
