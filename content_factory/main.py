import sys
import os
import asyncio
import logging
import random
import argparse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from pathlib import Path

# Подключаем корень проекта для config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content_factory.generators.text import generate_post_content
from content_factory.generators.image import generate_image
from content_factory.generators.image_prompt import generate_image_prompt_from_refs
from content_factory.publishers.telegram import publish_to_telegram
from content_factory.publishers.vk import publish_to_vk
from content_factory.artifacts import init_run_artifacts, save_run_artifacts, write_publish_result, write_run_json, write_run_text
from content_factory.editorial import editorial_pipeline
from content_factory.stylist import decorate_for_telegram
from content_factory.vk_stylist import style_for_vk
from content_factory.state import load_state, save_state
from content_factory.situations import pick_situation, extract_hook, extract_final_hook
from content_factory.generators.scenario_writer import generate_scenario
from content_factory.notify import notify_admin
from config import settings

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
    is_last_chance: bool = False
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
    # Soft default; Hard rarely (1 out of 5)
    tone_mode = "hard" if (random.randint(1, 5) == 1) else "soft"

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

    # Fail-safe: avoid 3 identical endings in a row (even if generator/editor slipped)
    final_hook = extract_final_hook(publish_text)
    if len(state.last_final_hooks) >= 2 and final_hook:
        a, b = state.last_final_hooks[-2], state.last_final_hooks[-1]
        if final_hook == a == b:
            variants = [
                "Либо фиксируешь, либо дальше гадаешь.",
                "Или считаешь, или снова живёшь на глаз.",
                "Либо смотришь цифры, либо продолжаешь наугад.",
                "Или фото сейчас, или хаос в голове дальше.",
            ]
            replacement = next((v for v in variants if extract_final_hook(v) not in {a, b}), None)
            if replacement:
                stripped = publish_text.strip()
                # Replace last non-empty line/sentence by appending a new final line
                publish_text = stripped + "\n\n" + replacement
                write_run_text(artifacts, "draft_after_final_guard.html", publish_text)

    # 3. Image prompt via refs (Gemini vision) + image generation
    effective_image_prompt, vision_payload = await _build_image_prompt(
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
    
    # Telegram
    tg_success = await publish_to_telegram(publish_text, image_url=image_url, parse_mode="HTML")
    write_publish_result(
        artifacts,
        ok=tg_success,
        target_chat_id=settings.CONTENT_FACTORY_TARGET_CHAT_ID,
        error=None if tg_success else "publish_to_telegram returned False",
    )

    # VK: отдельная ветка — свой стилист, та же картинка
    vk_style = await style_for_vk(topic=topic, text=text_final)
    write_run_json(artifacts, "vk_styling.json", {"ok": vk_style.ok, "issues": vk_style.issues, "model": vk_style.model})
    write_run_text(artifacts, "vk_draft.txt", vk_style.text)
    vk_success = await publish_to_vk(vk_style.text, image_url=image_url)
    write_run_json(artifacts, "vk_publish.json", {"ok": vk_success})
    
    if tg_success:
        logger.info("🏆 Итерация успешно завершена!")
        # Update state only on successful publish
        state.last_categories.append(situation.category)
        state.last_hooks.append(extract_hook(publish_text))
        state.last_final_hooks.append(extract_final_hook(publish_text))
        save_state(state_path, state)
        if not (vision_payload or {}).get("ok"):
            await notify_admin(
                title="Content Factory: vision prompt fallback",
                lines=[
                    f"reason: {(vision_payload or {}).get('reason')}",
                    f"scenario: {scenario}",
                ],
                run_dir=artifacts.run_dir,
            )
        return {"ok": True, "reason": "published", "run_dir": str(artifacts.run_dir), "scenario": scenario, "topic": topic}
    else:
        logger.error("⚠️ Публикация прошла с ошибками.")
        return {"ok": False, "reason": "publish_failed", "run_dir": str(artifacts.run_dir), "scenario": scenario, "topic": topic}

async def run_one_post(topic: str, scenario: str | None, target_chat_id: int | None, *, no_image: bool, tone_mode: str = "soft") -> None:
    tone_mode = (tone_mode or "soft").lower()
    if tone_mode not in {"soft", "hard"}:
        tone_mode = "soft"
    state_path = Path(settings.BASE_DIR) / "content_factory" / "state.json"
    state = load_state(state_path)
    situation = pick_situation(state, window=10)

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

    final_hook = extract_final_hook(publish_text)
    if len(state.last_final_hooks) >= 2 and final_hook:
        a, b = state.last_final_hooks[-2], state.last_final_hooks[-1]
        if final_hook == a == b:
            variants = [
                "Либо фиксируешь, либо дальше гадаешь.",
                "Или считаешь, или снова живёшь на глаз.",
                "Либо смотришь цифры, либо продолжаешь наугад.",
                "Или фото сейчас, или хаос в голове дальше.",
            ]
            replacement = next((v for v in variants if extract_final_hook(v) not in {a, b}), None)
            if replacement:
                stripped = publish_text.strip()
                publish_text = stripped + "\n\n" + replacement
                write_run_text(artifacts, "draft_after_final_guard.html", publish_text)

    effective_image_prompt: str | None = None
    image_url = None
    if not no_image:
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
    img_group = parser.add_mutually_exclusive_group()
    img_group.add_argument("--no-image", action="store_true", help="Skip image generation (cheaper).")
    img_group.add_argument("--with-image", action="store_true", help="Force image generation even in tests.")
    args = parser.parse_args()

    logger.info("🚀 Ручной запуск контент-пайплайна...")

    if args.topic:
        target_chat_id = settings.ADMIN_IDS[0] if (args.to_me and settings.ADMIN_IDS) else None
        no_image = args.no_image or (args.to_me and not args.with_image)
        tone_mode = "hard" if args.hard else "soft"
        await run_one_post(args.topic, args.scenario, target_chat_id=target_chat_id, no_image=no_image, tone_mode=tone_mode)
        return

    await run_factory_iteration()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Работа завершена.")

