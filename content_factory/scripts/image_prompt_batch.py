from __future__ import annotations

import argparse
import asyncio
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from content_factory.generators.image import generate_image
from content_factory.generators.image_prompt import generate_image_prompt_from_refs


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


async def main() -> None:
    parser = argparse.ArgumentParser(prog="image_prompt_batch")
    parser.add_argument("--out", type=str, default=None, help="Output directory (default: content_factory/image_prompt_runs/<stamp>/)")
    parser.add_argument("--refs-dir", type=str, default="content_factory/image_refs", help="Directory with reference images")
    args = parser.parse_args()

    refs_dir = Path(args.refs_dir)
    refs = [
        refs_dir / "ref_past_post.png",
        refs_dir / "ref_shopping_mode.png",
        refs_dir / "main_menu.png",
        refs_dir / "logo_foodflowbot.png",
    ]
    for p in refs:
        if not p.exists():
            raise FileNotFoundError(str(p))

    ref_desc = [
        "Past successful post image example (style anchor)",
        "Cyberpunk grocery scene reference (green neon, phone framing)",
        "FoodFlow main style reference (photorealistic lifestyle + neon)",
        "FoodFlow logo reference (brand shape/colors; do NOT place logo on output)",
    ]

    posts = [
        {
            "id": "bar_snacks",
            "text": "<b>В баре стоит бокал, на столе — тарелка закусок, а в голове каша: сколько калорий? 🍷🍽️</b>\n\nДостать приложение, тыкать меню, вспоминать порцию, угадывать по памяти — <b>занятие так себе</b>.\n\nСчитать вручную — <b>как бюджет на салфетке</b>. Просто лишняя возня.\n\n<b>Сфоткал → отправил → получил цифры</b>. Или кинул голосом, чеком — FoodFlow пришлёт без ввода.\n\nВечером, когда тянет к пиву или вину: <b>лишнее само не рассосётся</b>.\n\n<blockquote>Либо видишь цифры, либо снова гадаешь.</blockquote>",
        },
        {
            "id": "receipt_street",
            "text": "<b>Весной стоишь с пакетом из магазина или с чеком из кафе: смотришь на еду и пытаешься понять — это 300 ккал или 800.</b> 🛒🍔❓\n\nВводишь сам, злишься, и всё это быстро надоедает.\n\n<b>Проблема не в дисциплине.</b> Просто считать так — уже <b>устарело</b>.\n\nВ FoodFlow ты просто сфоткал чек, отправил в бот или скинул голосом — и сразу получил КБЖУ и понятные цифры по еде. <b>Сфоткал. Отправил. Получил сводку.</b>\n\n<blockquote>Или у тебя будут чёткие цифры, или снова догадки.</blockquote>",
        },
        {
            "id": "picnic_shashlik",
            "text": "<b>Шашлыки, салаты, поездка к друзьям — и в какой-то момент уже просто не хочется ничего записывать.</b> 🍖🌸\n\nВесной это особенно легко: стол длинный, разговоры идут, а счёт калорий откладываешь на потом.\n\nС FoodFlow всё проще: <b>сфоткал еду, отправил — получил КБЖУ</b>. Через неделю появляется <b>очень полезная вещь</b>: ты меньше забиваешь на еду, потому что проверка занимает пару секунд, а не кучу времени. Получаешь готовый расчёт без хлопот — и уже спокойнее понимаешь, что было на тарелке 📸\n\n<blockquote>Либо ты видишь цифры, либо снова в неведении.</blockquote>",
        },
    ]

    out_dir = Path(args.out) if args.out else Path("content_factory") / "image_prompt_runs" / _utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for item in posts:
        prompt_obj = await generate_image_prompt_from_refs(
            post_text=item["text"],
            refs=refs,
            ref_descriptions=ref_desc,
        )
        prompt = prompt_obj["prompt"]
        negative = prompt_obj.get("negative_prompt") or ""

        image_url = await generate_image(prompt if not negative else f"{prompt}\n\nNegative prompt: {negative}")
        saved_image_path = None
        if isinstance(image_url, str) and image_url.startswith("data:image/") and ";base64," in image_url:
            header, b64 = image_url.split(";base64,", 1)
            ext = header.split("data:image/", 1)[1].split(";", 1)[0].strip().lower()
            if ext == "jpeg":
                ext = "jpg"
            img_bytes = base64.b64decode(b64)
            saved_image_path = str(out_dir / f"{item['id']}.{ext}")
            Path(saved_image_path).write_bytes(img_bytes)

        one = {
            "id": item["id"],
            "prompt": prompt,
            "negative_prompt": negative,
            "image_url": image_url,
            "saved_image_path": saved_image_path,
            "notes": prompt_obj.get("notes") or [],
        }
        results.append(one)
        (out_dir / f"{item['id']}.json").write_text(json.dumps(one, ensure_ascii=False, indent=2), encoding="utf-8")

    (out_dir / "batch.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())

