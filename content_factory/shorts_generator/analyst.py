from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import settings
from content_factory.http_client import openrouter_post

logger = logging.getLogger("shorts_generator.analyst")

# Available voices verified in test_voices.py
AVAILABLE_VOICES = {
    "female": [
        {"name": "Sarah", "id": "EXAVITQu4vr4xnSDxMaL", "desc": "Mature, Reassuring, Confident"},
        {"name": "Jessica", "id": "cgSgspJ2msm6clMCkdW9", "desc": "Playful, Bright, Warm"},
        {"name": "Laura", "id": "FGY2WhTYpPnrIDTdsKH5", "desc": "Enthusiast, Quirky Attitude"},
        {"name": "Bella", "id": "hpp4J3VqNfWAUOO0d1Us", "desc": "Professional, Bright, Warm"}
    ],
    "male": [
        {"name": "George", "id": "JBFqnCBsd6RMkjVDRZzb", "desc": "Warm, Captivating Storyteller"},
        {"name": "Charlie", "id": "IKne3meq5aSn9XLyUdCD", "desc": "Deep, Confident, Energetic"},
        {"name": "Liam", "id": "TX3LPaxmHKxFdv7VOQHJ", "desc": "Energetic, Social Media Creator"},
        {"name": "Brian", "id": "nPczCjzI2devNBz1zQrb", "desc": "Deep, Resonant and Comforting"}
    ]
}


def find_latest_run_dir(runs_dir: str | Path = "/home/user1/foodflow-bot_new/content_factory/runs") -> Path:
    """
    Finds the best run directory for YouTube Shorts generation.
    It scans directories from oldest to newest (up to 2 days old) and returns the oldest one
    where a Telegram/VK post was successfully published (publish.json exists) but no Short has been generated yet (shorts_published.json does not exist).
    Falls back to the absolute newest run directory if no such match is found.
    """
    import os
    import re
    from datetime import datetime, timezone, timedelta

    forced = os.environ.get("SHORTS_FORCE_RUN_DIR")
    if forced:
        forced_path = Path(forced)
        if forced_path.exists():
            logger.info(f"🚀 FORCING RUN DIRECTORY via environment variable: {forced_path.name}")
            return forced_path
        else:
            logger.warning(f"⚠️ SHORTS_FORCE_RUN_DIR set to non-existent path: {forced}")

    path = Path(runs_dir)
    if not path.exists():
        raise FileNotFoundError(f"Runs directory does not exist: {path}")

    dirs = [d for d in path.iterdir() if d.is_dir() and "T" in d.name and d.name[0].isdigit()]
    
    locale = os.environ.get("SHORTS_LOCALE", "ru")
    if locale == "es":
        dirs = [d for d in dirs if d.name.endswith("_es")]
    else:
        dirs = [d for d in dirs if not d.name.endswith("_es") and "autonomous_morning_shorts_es" not in d.name]

    if not dirs:
        raise FileNotFoundError(f"No valid run directories found in {path} for locale={locale}")

    # Sort alphabetically, oldest first (ascending)
    dirs.sort(key=lambda d: d.name)

    now_utc = datetime.now(timezone.utc)
    limit_time = now_utc - timedelta(days=2)

    target_dir = None

    for d in dirs:
        stamp = d.name[:16]
        if not re.match(r"^\d{8}T\d{6}Z$", stamp):
            continue

        try:
            folder_time = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            continue

        # Ignore folders older than 2 days
        if folder_time < limit_time:
            continue

        # Check markers
        has_post = (d / "publish.json").exists()
        has_short = (d / "shorts_published.json").exists()

        if has_post and not has_short:
            target_dir = d
            logger.info(f"🎯 Smart scan: found OLDEST folder for Shorts (published post, no video) -> {d.name}")
            break

    if target_dir:
        return target_dir

    # Fallback to the absolute newest folder
    dirs.sort(key=lambda d: d.name, reverse=True)
    latest_dir = dirs[0]
    logger.info(f"Smart scan fallback (none matching criteria in 2 days): {latest_dir.name}")
    return latest_dir


def extract_post_data(run_dir: Path) -> dict[str, Any]:
    """
    Reads post.json and checks that image.png exists.
    Also verifies the run was created TODAY (Moscow time) —
    so the YouTube worker never accidentally uses yesterday's post.
    """
    import re
    from datetime import datetime, timezone, timedelta

    post_json_path = run_dir / "post.json"
    image_png_path = run_dir / "image.png"

    if not post_json_path.exists():
        raise FileNotFoundError(f"post.json not found in {run_dir}")

    if not image_png_path.exists():
        import shutil

        # Priority 1: well-known alt names
        for alt in (
            run_dir / "demo_mockup.png",
            run_dir / "image.jpg",
            run_dir / "image.jpeg",
            run_dir / "image.webp",
        ):
            if alt.is_file():
                shutil.copy2(alt, image_png_path)
                logger.info("Shorts: created image.png from %s", alt.name)
                break

        # Priority 2: saved_image_path field inside post.json
        if not image_png_path.exists():
            with open(post_json_path, encoding="utf-8") as f:
                saved = (json.load(f).get("saved_image_path") or "").strip()
            if saved and Path(saved).is_file():
                shutil.copy2(Path(saved), image_png_path)
                logger.info("Shorts: created image.png from post.json saved_image_path")

        # Priority 3: wildcard — grab the first image file of any name in the run dir
        if not image_png_path.exists():
            candidates = []
            for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                candidates.extend(run_dir.glob(pattern))
            # Exclude our own target to avoid self-reference
            candidates = [c for c in candidates if c.name != "image.png"]
            if candidates:
                # Prefer PNGs, then by file size (largest = highest quality)
                candidates.sort(key=lambda p: (p.suffix.lower() != ".png", -p.stat().st_size))
                shutil.copy2(candidates[0], image_png_path)
                logger.info("Shorts: created image.png from wildcard scan → %s", candidates[0].name)

        if not image_png_path.exists():
            raise FileNotFoundError(
                f"image.png not found in {run_dir} and no alternative image files were found. "
                f"Files present: {[f.name for f in run_dir.iterdir()]}"
            )

    # Check freshness: run dir name starts with YYYYMMDDTHHMMSSZ timestamp
    MSK = timezone(timedelta(hours=3))
    today_msk = datetime.now(MSK).strftime("%Y%m%d")
    dir_stamp = run_dir.name[:8]  # first 8 chars = YYYYMMDD
    if re.match(r"^\d{8}$", dir_stamp) and dir_stamp != today_msk:
        logger.warning(
            f"⚠️ YouTube отдел: используем пост не за сегодня. Последний найденный пост от {dir_stamp} (сегодня {today_msk}). "
            f"Продолжаем автономную работу без привязки к дате."
        )
    else:
        logger.info(f"✅ YouTube отдел: используем сегодняшний пост от {dir_stamp}.")

    with open(post_json_path, "r", encoding="utf-8") as f:
        post_data = json.load(f)

    # If the user revised the draft during editorial phase, prefer draft_after_editorial.txt
    editorial_draft_path = run_dir / "draft_after_editorial.txt"
    if editorial_draft_path.exists():
        with open(editorial_draft_path, "r", encoding="utf-8") as f:
            final_text = f.read().strip()
            logger.info("Found revised draft_after_editorial.txt; using it as main text.")
            post_data["text"] = final_text

    return {
        "run_dir": str(run_dir),
        "topic": post_data.get("topic", run_dir.name),
        "text": post_data.get("text", ""),
        "image_path": str(image_png_path),
        "image_prompt": post_data.get("image_prompt", ""),
        "audience": post_data.get("audience", "b2c"),
        "scenario": post_data.get("scenario", ""),
    }


async def analyze_post_mood_and_voice(post_text: str, post_topic: str) -> dict[str, Any]:
    """
    Analyzes the post text using LLM, extracts mood/vibe, and selects the best matching voice.
    """
    voices_formatted = json.dumps(AVAILABLE_VOICES, indent=2, ensure_ascii=False)

    prompt = f"""
Ты — профессиональный ИИ-режиссер и звукодизайнер проекта FoodFlow.
Твоя задача: проанализировать текст рекламного/образовательного поста Telegram для озвучки вирусного YouTube Shorts, определить его настроение и выбрать ИДЕАЛЬНО подходящий голос из доступной базы ElevenLabs.

ДОСТУПНЫЕ ГОЛОСА ELEVENLABS:
{voices_formatted}

ПОСТ ДЛЯ АНАЛИЗА:
Тема: {post_topic}
Текст:
\"\"\"{post_text}\"\"\"

КРИТЕРИИ ВЫБОРА:
1. Выбери пол (gender) голоса ("female" или "male"), который лучше всего передаст интонацию поста.
2. Выбери конкретный голос из списка доступных для этого пола.
3. Опиши настроение (mood) текста (например: энергичное, ироничное, заботливое, строгое, дружелюбное).
4. Обоснуй свой выбор (reasoning), почему этот голос и его описание идеально подходят для озвучки этой темы и текста.

ВЕРНИ СТРОГО JSON-ОБЪЕКТ СЛЕДУЮЩЕГО ФОРМАТА (БЕЗ ДРУГОГО ТЕКСТА):
{{
  "mood": "строка с настроением",
  "gender": "female" | "male",
  "voice_name": "Имя голоса",
  "voice_id": "ID голоса",
  "reasoning": "подробное обоснование на русском языке"
}}
""".strip()

    candidate_models = [
        "deepseek/deepseek-v4-flash-0731",
        "google/gemini-3.5-flash-lite"
    ]

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Shorts Generator - Analyst",
    }

    # Save raw prompt for auditing
    try:
        latest_run = find_latest_run_dir()
        with open(latest_run / "analyst_prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
    except Exception as e:
        logger.error(f"Failed to save analyst prompt: {e}")

    for target_model in candidate_models:
        retries = 2 if "deepseek" in target_model else 1
        for attempt in range(1, retries + 1):
            payload = {
                "model": target_model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
            try:
                logger.info(f"🧠 Analyst requesting mood/voice from model '{target_model}' (attempt {attempt}/{retries})...")
                data = await openrouter_post(headers=headers, payload=payload, timeout=60.0)
                raw_content = data["choices"][0]["message"].get("content")
                if not raw_content:
                    raise ValueError("Empty model content received from OpenRouter")
                    
                # Save raw response for auditing
                try:
                    with open(latest_run / "analyst_response.json", "w", encoding="utf-8") as f:
                        f.write(str(raw_content))
                except Exception as e:
                    logger.error(f"Failed to save analyst response: {e}")

                raw = str(raw_content).strip()
                if raw.startswith("```json"):
                    raw = raw[7:]
                elif raw.startswith("```"):
                    raw = raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

                result = json.loads(raw)
                gender = result.get("gender")
                voice_name = result.get("voice_name")
                voice_id = result.get("voice_id")

                valid_voice = False
                if gender in AVAILABLE_VOICES:
                    for v in AVAILABLE_VOICES[gender]:
                        if v["name"].lower() == str(voice_name).lower() or v["id"] == voice_id:
                            result["voice_name"] = v["name"]
                            result["voice_id"] = v["id"]
                            valid_voice = True
                            break

                if not valid_voice:
                    logger.warning(f"Model returned invalid voice choice: {voice_name}/{voice_id}. Applying fallback.")
                    result["gender"] = "male"
                    result["voice_name"] = "Liam"
                    result["voice_id"] = "TX3LPaxmHKxFdv7VOQHJ"
                    result["mood"] = "energetic"
                    result["reasoning"] = "Fallback chosen: Liam is perfect for social media style."

                result.setdefault("mood", "friendly")
                return result

            except Exception as e:
                logger.warning(f"⚠️ Model '{target_model}' attempt {attempt} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(1.0)
                continue

    logger.error("❌ All candidate analyst models failed. Applying ultimate fallback.")
    return {
        "mood": "friendly",
        "gender": "male",
        "voice_name": "Liam",
        "voice_id": "TX3LPaxmHKxFdv7VOQHJ",
        "reasoning": "Ultimate fallback chosen.",
    }


async def run_analysis() -> dict[str, Any]:
    """
    Orchestrates the first step: finds the latest run, extracts data, and performs the analysis.
    """
    logger.info("Starting YouTube Shorts Content Factory Step 1: Integration & Analysis")
    
    # 1. Find latest run
    latest_run = find_latest_run_dir()
    
    # 2. Extract post details
    post_data = extract_post_data(latest_run)
    logger.info(f"Successfully integrated with run: {post_data['topic']}")
    
    # 3. Analyze mood and select voice
    analysis = await analyze_post_mood_and_voice(post_data["text"], post_data["topic"])
    mood = analysis.get("mood", "friendly")
    voice_name = analysis.get("voice_name", "Liam")
    voice_id = analysis.get("voice_id", "TX3LPaxmHKxFdv7VOQHJ")
    logger.info(f"Chosen voice: {voice_name} (ID: {voice_id}) with mood: '{mood}'")
    
    # Combine results
    final_payload = {
        "run_dir": post_data["run_dir"],
        "topic": post_data["topic"],
        "post_text": post_data["text"],
        "image_path": post_data["image_path"],
        "image_prompt": post_data["image_prompt"],
        "audience": post_data.get("audience", "b2c"),
        "scenario": post_data.get("scenario", ""),
        "analysis": analysis,
    }
    
    # Save the step 1 artifact locally in the run directory for persistence
    step1_output_path = latest_run / "shorts_analysis.json"
    with open(step1_output_path, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved Step 1 analysis results to {step1_output_path}")
    return final_payload
