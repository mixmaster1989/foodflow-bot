import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Подключаем корень проекта для config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from content_factory.artifacts import (
    init_run_artifacts,
    save_run_artifacts,
    write_publish_result,
    write_run_json,
    write_run_text,
)
from content_factory.dzen_stylist import style_for_dzen
from content_factory.editorial import editorial_pipeline
from content_factory.generators.data_fetcher import get_random_meal_for_demo
from content_factory.generators.image import generate_image
from content_factory.generators.image_prompt import generate_image_prompt_from_refs
from content_factory.generators.reels import (
    format_reels_for_tg,
    generate_reels_scenario,
)
from content_factory.generators.scenario_writer import generate_scenario
from content_factory.generators.text import generate_post_content
from content_factory.notify import notify_admin
from content_factory.publishers.dzen import publish_to_dzen
from content_factory.publishers.telegram import publish_to_telegram
from content_factory.publishers.vk import publish_to_vk
from content_factory.renderer import TelegramRenderer
from content_factory.situations import extract_final_hook, extract_hook, pick_situation
from content_factory.state import load_state, save_state
from content_factory.stylist import decorate_for_telegram
from content_factory.vk_stylist import style_for_vk

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("content_factory")

def _default_image_refs(base_dir: Path) -> tuple[list[Path], list[str]]:
    refs_dir = base_dir / "content_factory" / "image_refs"
    refs = [
        refs_dir / "ref_past_post.png",
        refs_dir / "ref_shopping_mode.png",
        refs_dir / "main_menu.png",
        refs_dir / "logo_foodflowbot.png",
    ]
    desc = [
        "Past successful post image example (style anchor)",
        "Cyberpunk grocery scene reference (green neon, phone framing)",
        "FoodFlow main style reference (photorealistic lifestyle + neon)",
        "FoodFlow logo reference (brand shape/colors; do NOT place logo on output)",
    ]
    return refs, desc


async def _build_image_prompt(
    *,
    base_dir: Path,
    topic: str,
    post_text: str,
    fallback_prompt: str | None,
    artifacts,
) -> tuple[str | None, dict]:
    """
    Prefer Gemini vision-generated prompt using brand refs; fallback to generator's prompt.
    """
    refs, desc = _default_image_refs(base_dir)
    if not all(p.exists() for p in refs):
        missing = [str(p) for p in refs if not p.exists()]
        payload = {"ok": False, "reason": "missing_refs", "missing": missing}
        write_run_json(artifacts, "image_prompt_vision.json", payload)
        return fallback_prompt, payload

    try:
        res = await generate_image_prompt_from_refs(post_text=post_text, refs=refs, ref_descriptions=desc)
        prompt = (res.get("prompt") or "").strip()
        negative = (res.get("negative_prompt") or "").strip()
        payload = {"ok": True, "model": res.get("model"), "prompt": prompt, "negative_prompt": negative, "notes": res.get("notes") or []}
        write_run_json(artifacts, "image_prompt_vision.json", payload)
        if negative:
            return f"{prompt}\n\nNegative prompt: {negative}", payload
        return (prompt or fallback_prompt), payload
    except Exception as e:
        payload = {"ok": False, "reason": "vision_failed", "error": str(e)}
        write_run_json(artifacts, "image_prompt_vision.json", payload)
        return fallback_prompt, payload

async def run_daily_factory_job():
    logger.info("🏭 Запуск полной фабрики контента (ТЕСТ ВСЕХ СЦЕНАРИЕВ)...")

    topics = {
        "pain": "Как сорваться с диеты из-за одной пачки чипсов, которую лень было взвешивать",
        "use_case": "Вечер с друзьями, пицца и пиво: как не умереть от чувства вины на утро",
        "anti_old_school": "Почему MyFitnessPal и кухонные весы — это медленная смерть вашего энтузиазма",
        "result": "Как за неделю в FoodFlow перестать бояться еды и начать видеть результат",
        "myth_buster": "Миф о том, что углеводы после 18:00 превращаются в тыкву на боках",
        "lazy_pro": "Как вписать любимый фастфуд в рацион и продолжать худеть"
    }

    for scenario, topic in topics.items():
        logger.info(f"\n--- ПРОГОН СЦЕНАРИЯ: {scenario} ---")
        result = await generate_post_content(topic, scenario=scenario)

        text = result.get('text', 'N/A')
        image_prompt = result.get('image_prompt', 'N/A')

        print(f"\n[{scenario.upper()}]")
        print(f"📝 ТЕКСТ: {text[:100]}...")

        # Генерируем картинку
        image_url = None
        if image_prompt != "N/A" and "error" not in image_prompt.lower():
            image_url = await generate_image(image_prompt)
            print(f"🎨 КАРТИНКА: {image_url}")

        print("="*50)

        # Публикуем ТОЛЬКО сценарий 'anti_old_school' для финального теста
        if scenario == "anti_old_school" and text:
            logger.info(f"🚀 Пробуем ПОЛНУЮ публикацию сценария {scenario}...")
            await publish_to_telegram(text, image_url=image_url)

async def run_factory_iteration(
    previous_attempts: list[dict] | None = None,
    is_last_chance: bool = False,
    target_chat_id: int | None = None,
    no_image: bool = False,
    tone_mode: str = "soft"
) -> dict:
    """Основная итерация: выбор сценария, генерация и публикация."""
    logger.info(f"🏭 Запуск плановой итерации Контент-Завода... (Last chance: {is_last_chance})")

    # 1. Сценарист генерирует свежую ситуацию, сценарий и тему
    state_path = Path(settings.BASE_DIR) / "content_factory" / "state.json"
    state = load_state(state_path)
    scenario_data = await generate_scenario(state)
    situation = scenario_data["situation"]
    scenario = scenario_data["scenario"]
    topic = scenario_data["topic"]

    # 2. Генерация контента
    result = await generate_post_content(
        topic,
        scenario=scenario,
        tone_mode=tone_mode,
        situation_category=situation.category,
        situation_brief=situation.brief,
        recent_final_hooks=state.last_final_hooks[-2:],
    )
    text = result.get('text')
    image_prompt = result.get('image_prompt')

    if not text or "Системная ошибка" in text:
        logger.error("❌ Ошибка генерации контента. Пропуск итерации.")
        return {"ok": False, "reason": "generation_failed", "scenario": scenario, "topic": topic}

    artifacts = init_run_artifacts(base_dir=settings.BASE_DIR, topic=topic)
    write_run_text(artifacts, "draft_generator.txt", text)
    write_run_json(artifacts, "tone.json", {"tone_mode": tone_mode})
    write_run_json(artifacts, "situation.json", {"category": situation.category, "brief": situation.brief})
    write_run_json(artifacts, "image_prompt_generator.json", {"image_prompt": image_prompt})

    editorial = await editorial_pipeline(
        topic,
        text,
        tone_mode=tone_mode,
        previous_attempts=previous_attempts,
        is_last_chance=is_last_chance
    )
    text_final = editorial.text_final
    if editorial.status != "approve":
        logger.error("⛔ Пост заблокирован редакцией. Публикации не будет.")
        write_run_text(artifacts, "draft_after_editorial.txt", text_final)
        write_run_json(
            artifacts,
            "editorial.json",
            {"compliance": editorial.compliance, "chief": editorial.chief, "judge": editorial.judge},
        )
        write_publish_result(
            artifacts,
            ok=False,
            target_chat_id=settings.CONTENT_FACTORY_TARGET_CHAT_ID,
            error="blocked_by_editorial",
        )

        # Собираем причины блока для истории
        reason = "blocked_by_editorial"
        judge_issues = editorial.judge.get("issues") or []
        chief_notes = editorial.chief.get("notes") or []
        block_details = "; ".join(judge_issues + chief_notes)

        return {
            "ok": False,
            "reason": reason,
            "details": block_details,
            "run_dir": str(artifacts.run_dir),
            "scenario": scenario,
            "topic": topic
        }

    write_run_text(artifacts, "draft_after_editorial.txt", text_final)

    style = await decorate_for_telegram(topic=topic, text=text_final)
    publish_text = style.text_html if style.ok else text_final
    write_run_text(artifacts, "draft_after_stylist.html", publish_text)

    effective_image_prompt: str | None = None
    image_url = None
    _vision_payload = None
    if not no_image:
        scenario_type = result.get("scenario") or scenario
        if scenario_type == "demo_screenshot":
            # Just fallback to generic image for iteration tests until we refactor properly
            food_prompt = f"High quality food photography of {topic}, top-down view"
            image_url = await generate_image(food_prompt)
        else:
            effective_image_prompt, _vision_payload = await _build_image_prompt(
                base_dir=settings.BASE_DIR,
                topic=topic,
                post_text=publish_text,
                fallback_prompt=image_prompt,
                artifacts=artifacts,
            )
            image_url = await generate_image(effective_image_prompt or image_prompt or "")

    artifacts = await save_run_artifacts(
        base_dir=settings.BASE_DIR,
        topic=topic,
        scenario=scenario,
        post_text=publish_text,
        image_prompt=effective_image_prompt or image_prompt,
        image_ref=image_url,
        publish_target_chat_id=settings.CONTENT_FACTORY_TARGET_CHAT_ID,
        mode="channel",
        paths=artifacts,
    )
    write_run_json(
        artifacts,
        "editorial.json",
        {"compliance": editorial.compliance, "chief": editorial.chief, "judge": editorial.judge},
    )
    write_run_json(
        artifacts,
        "styling.json",
        {"ok": style.ok, "issues": style.issues, "model": style.model},
    )

    # 4. Публикация
    logger.info(f"🚀 Публикация сценария '{scenario}'...")

    publish_target = target_chat_id or settings.CONTENT_FACTORY_TARGET_CHAT_ID

    # Telegram
    tg_success = await publish_to_telegram(publish_text, image_url=image_url, target_chat_id=publish_target, parse_mode="HTML")
    write_publish_result(
        artifacts,
        ok=tg_success,
        target_chat_id=publish_target,
        error=None if tg_success else "publish_to_telegram returned False",
    )

    # VK: отдельная ветка — свой стилист, та же картинка
    vk_style = await style_for_vk(topic=topic, text=text_final)
    write_run_json(artifacts, "vk_styling.json", {"ok": vk_style.ok, "issues": vk_style.issues, "model": vk_style.model})
    write_run_text(artifacts, "vk_draft.txt", vk_style.text)
    vk_success = await publish_to_vk(vk_style.text, image_url=image_url)
    write_run_json(artifacts, "vk_publish.json", {"ok": vk_success})

    # Dzen: отдельная ветка — свой стилист, та же картинка
    dzen_style = await style_for_dzen(topic=topic, text=text_final)
    write_run_json(artifacts, "dzen_styling.json", {"ok": dzen_style.ok, "issues": dzen_style.issues, "model": dzen_style.model})
    write_run_text(artifacts, "dzen_draft.txt", dzen_style.text)
    dzen_success = await publish_to_dzen(dzen_style.text, image_url=image_url, title=f"FoodFlow: {topic[:50]}")
    write_run_json(artifacts, "dzen_publish.json", {"ok": dzen_success})

    if tg_success:
        logger.info("🏆 Итерация успешно завершена!")
        # Update state only on successful publish
        state.last_categories.append(situation.category)
        state.last_hooks.append(extract_hook(publish_text))
        state.last_final_hooks.append(extract_final_hook(publish_text))

        scenario_type = result.get("scenario") or scenario
        if scenario_type:
            state.last_scenarios.append(scenario_type)

        save_state(state_path, state)
        if not no_image and _vision_payload is not None and not _vision_payload.get("ok"):
            await notify_admin(
                title="Content Factory: vision prompt fallback",
                lines=[
                    f"reason: {_vision_payload.get('reason')}",
                    f"scenario: {scenario}",
                ],
                run_dir=artifacts.run_dir,
            )
        return {"ok": True, "reason": "published", "run_dir": str(artifacts.run_dir), "scenario": scenario, "topic": topic}
    else:
        logger.error("⚠️ Публикация прошла с ошибками.")
        return {"ok": False, "reason": "publish_failed", "run_dir": str(artifacts.run_dir), "scenario": scenario, "topic": topic}

async def run_reels_iteration(target_chat_id: int | None = None, manual_topic: str | None = None) -> dict:
    """Итерация генерации сценария для Instagram Reels."""
    logger.info("🎬 Запуск генерации сценария Reels...")

    # 1. Сценарист генерирует тему и ситуацию (если не передана вручную)
    state_path = Path(settings.BASE_DIR) / "content_factory" / "state.json"
    state = load_state(state_path)

    if manual_topic:
        from content_factory.situations import pick_situation
        situation = pick_situation(state, window=10)
        topic = manual_topic
    else:
        scenario_data = await generate_scenario(state)
        situation = scenario_data["situation"]
        topic = scenario_data["topic"]

    # 2. Генерация самого сценария
    reels_data = await generate_reels_scenario(topic, situation.brief)
    if "error" in reels_data:
        return {"ok": False, "reason": "generation_failed"}

    # Подготовка текста для редактуры (склеиваем всё что произносится или пишется)
    full_content = f"{reels_data['hook']['speech']} {reels_data['hook']['overlay']} " \
                   f"{reels_data['body']['speech']} {reels_data['body']['overlay']} " \
                   f"{reels_data['cta']['speech']} {reels_data['cta']['overlay']}"

    # 3. Редактура (Комплаенс)
    # Для Reels используем is_last_chance=True, чтобы быть лояльнее к стилистике видео
    editorial = await editorial_pipeline(topic, full_content, tone_mode="soft", is_last_chance=True)

    # Если заблокировано по жестким флагам - выходим
    if editorial.status != "approve":
        logger.error("⛔ Сценарий Reels заблокирован редакцией.")
        return {"ok": False, "reason": "blocked_by_editorial", "details": str(editorial.compliance.get("reasons"))}

    # 4. Форматирование и отправка
    formatted_text = format_reels_for_tg(reels_data)

    publish_target = target_chat_id or (settings.ADMIN_IDS[0] if settings.ADMIN_IDS else None)
    if not publish_target:
        logger.error("❌ Некуда слать сценарий (ADMIN_IDS пуст)")
        return {"ok": False, "reason": "no_target"}

    success = await publish_to_telegram(formatted_text, target_chat_id=publish_target, parse_mode="HTML")

    if success:
        logger.info("🏆 Сценарий Reels успешно отправлен!")
        # Обновляем стейт (чтобы не частить с темами)
        state.last_categories.append(situation.category)
        save_state(state_path, state)
        return {"ok": True, "topic": topic}

    return {"ok": False, "reason": "publish_failed"}

async def run_one_post(topic: str, scenario: str | None, target_chat_id: int | None, *, no_image: bool, tone_mode: str = "soft") -> None:
    tone_mode = (tone_mode or "soft").lower()
    if tone_mode not in {"soft", "hard"}:
        tone_mode = "soft"
    state_path = Path(settings.BASE_DIR) / "content_factory" / "state.json"
    state = load_state(state_path)
    situation = pick_situation(state, window=10)

    if scenario == "demo_screenshot":
        meal_data = get_random_meal_for_demo()
        topic = f"Обед: {meal_data['food_name']}. КБЖУ: {meal_data['calories']} ккал, Б: {meal_data['protein']}г, Ж: {meal_data['fat']}г, У: {meal_data['carbs']}г."
        logger.info(f"Loaded real meal data for demo_screenshot: {topic}")

    result = await generate_post_content(
        topic,
        scenario=scenario,
        tone_mode=tone_mode,
        situation_category=situation.category,
        situation_brief=situation.brief,
        recent_final_hooks=state.last_final_hooks[-2:],
    )
    text = result.get("text")
    image_prompt = result.get("image_prompt")

    if not text or "Системная задержка" in text:
        logger.error("❌ Ошибка генерации контента. Пропуск.")
        return

    artifacts = init_run_artifacts(base_dir=settings.BASE_DIR, topic=topic)
    write_run_text(artifacts, "draft_generator.txt", text)
    write_run_json(artifacts, "tone.json", {"tone_mode": tone_mode})
    write_run_json(artifacts, "situation.json", {"category": situation.category, "brief": situation.brief})
    write_run_json(artifacts, "image_prompt_generator.json", {"image_prompt": image_prompt})

    editorial = await editorial_pipeline(topic, text, tone_mode=tone_mode)
    text_final = editorial.text_final

    publish_target_chat_id = target_chat_id or settings.CONTENT_FACTORY_TARGET_CHAT_ID
    write_run_text(artifacts, "draft_after_editorial.txt", text_final)

    style = await decorate_for_telegram(topic=topic, text=text_final)
    publish_text = style.text_html if style.ok else text_final
    write_run_text(artifacts, "draft_after_stylist.html", publish_text)

    write_run_text(artifacts, "draft_after_stylist.html", publish_text)

    effective_image_prompt: str | None = None
    image_url = None
    if not no_image:
        scenario_type = result.get("scenario") or scenario
        if scenario_type == "demo_screenshot":
            # For demo_screenshot, generate a picture of the food and render the mockup
            food_prompt = f"High quality food photography of {meal_data['food_name']}, top-down view, realistic, bright lighting"
            food_img_url = await generate_image(food_prompt)

            # Download the food image to a temp file if it's base64 or URL
            temp_food_path = "content_factory/runs/temp_food.png"
            if food_img_url and food_img_url.startswith("data:image"):
                import base64
                format, imgstr = food_img_url.split(';base64,')
                with open(temp_food_path, "wb") as f:
                    f.write(base64.b64decode(imgstr))

            # Render mockup
            import os
            mockup_base = "content_factory/image_refs/mockup_phone_base.png"
            output_mockup = os.path.join(str(artifacts.run_dir), "demo_mockup.png")
            renderer = TelegramRenderer(mockup_base)

            photo_to_render = temp_food_path if os.path.exists(temp_food_path) else "assets/emojis/plate.png"
            rendered_path = renderer.render_demo(
                food_photo_path=photo_to_render,
                food_name=meal_data['food_name'],
                calories=meal_data['calories'],
                protein=meal_data['protein'],
                fat=meal_data['fat'],
                carbs=meal_data['carbs'],
                output_path=output_mockup
            )
            image_url = rendered_path
            effective_image_prompt = "Mockup generated locally via TelegramRenderer"
        else:
            effective_image_prompt, _vision_payload = await _build_image_prompt(
                base_dir=settings.BASE_DIR,
                topic=topic,
                post_text=publish_text,
                fallback_prompt=image_prompt,
                artifacts=artifacts,
            )
            image_url = await generate_image(effective_image_prompt or image_prompt or "")

    publish_target_chat_id = target_chat_id or settings.CONTENT_FACTORY_TARGET_CHAT_ID
    artifacts = await save_run_artifacts(
        base_dir=settings.BASE_DIR,
        topic=topic,
        scenario=result.get("scenario") or scenario,
        post_text=publish_text,
        image_prompt=effective_image_prompt if not no_image else image_prompt,
        image_ref=image_url,
        publish_target_chat_id=publish_target_chat_id,
        mode="to_me" if target_chat_id else "channel",
        paths=artifacts,
    )
    write_run_json(
        artifacts,
        "editorial.json",
        {"compliance": editorial.compliance, "chief": editorial.chief, "judge": editorial.judge},
    )
    write_run_json(
        artifacts,
        "styling.json",
        {"ok": style.ok, "issues": style.issues, "model": style.model},
    )

    if editorial.status != "approve":
        write_publish_result(
            artifacts,
            ok=False,
            target_chat_id=publish_target_chat_id,
            error="blocked_by_editorial",
        )
        logger.error("⛔ Пост заблокирован редакцией. Публикации не будет.")
        return

    tg_success = await publish_to_telegram(publish_text, image_url=image_url, target_chat_id=target_chat_id, parse_mode="HTML")
    vk_success = await publish_to_vk(publish_text, image_url=image_url)
    write_run_json(artifacts, "vk_publish.json", {"ok": vk_success})
    # Dzen
    dzen_style = await style_for_dzen(topic=topic, text=text_final)
    write_run_json(artifacts, "dzen_styling.json", {"ok": dzen_style.ok, "issues": dzen_style.issues, "model": dzen_style.model})
    write_run_text(artifacts, "dzen_draft.txt", dzen_style.text)
    dzen_success = await publish_to_dzen(dzen_style.text, image_url=image_url, title=f"FoodFlow: {topic[:50]}")
    write_run_json(artifacts, "dzen_publish.json", {"ok": dzen_success})
    write_publish_result(
        artifacts,
        ok=tg_success,
        target_chat_id=publish_target_chat_id,
        error=None if tg_success else "publish_to_telegram returned False",
    )
    if tg_success:
        # Advance state on successful publish (both channel + DM tests)
        state.last_categories.append(situation.category)
        state.last_hooks.append(extract_hook(publish_text))
        state.last_final_hooks.append(extract_final_hook(publish_text))
        save_state(state_path, state)


async def main():
    parser = argparse.ArgumentParser(prog="content_factory")
    parser.add_argument("--topic", type=str, default=None)
    parser.add_argument("--scenario", type=str, default=None)
    parser.add_argument("--to-me", action="store_true", help="Send to admin DM for testing.")
    tone_group = parser.add_mutually_exclusive_group()
    tone_group.add_argument("--soft", action="store_true", help="Force soft tone.")
    tone_group.add_argument("--hard", action="store_true", help="Force hard tone.")
    parser.add_argument("--reels", action="store_true", help="Generate Instagram Reels scenario instead of post.")
    img_group = parser.add_mutually_exclusive_group()
    img_group.add_argument("--no-image", action="store_true", help="Skip image generation (cheaper).")
    img_group.add_argument("--with-image", action="store_true", help="Force image generation even in tests.")
    args = parser.parse_args()

    logger.info("🚀 Ручной запуск контент-пайплайна...")

    target_chat_id = settings.ADMIN_IDS[0] if (args.to_me and settings.ADMIN_IDS) else None
    no_image = args.no_image or (args.to_me and not args.with_image)
    tone_mode = "hard" if args.hard else "soft"

    if args.reels:
        await run_reels_iteration(target_chat_id=target_chat_id, manual_topic=args.topic)
        return

    if args.topic:
        await run_one_post(args.topic, args.scenario, target_chat_id=target_chat_id, no_image=no_image, tone_mode=tone_mode)
        return

    await run_factory_iteration(target_chat_id=target_chat_id, no_image=no_image, tone_mode=tone_mode)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Работа завершена.")

