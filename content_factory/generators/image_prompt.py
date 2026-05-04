from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from content_factory.http_client import openrouter_post

from config import settings

logger = logging.getLogger(__name__)


VISION_PROMPT_MODELS = [
    "google/gemini-3-flash-preview",
]


def _path_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(suffix)
    if not mime:
        raise ValueError(f"Unsupported image type: {path.name}")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _best_effort_json(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Empty model output")
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        obj, _idx = decoder.raw_decode(raw)
        return obj


async def generate_image_prompt_from_refs(
    *,
    post_text: str,
    refs: list[Path],
    ref_descriptions: list[str] | None = None,
    model: str | None = None,
    timeout_s: float = 60.0,
) -> dict[str, Any]:
    """
    Use a multimodal model (Gemini) to write a high-quality image generation prompt
    consistent with brand refs.

    Returns JSON with:
    - prompt: str
    - negative_prompt: str
    - notes: list[str]
    """
    if not refs:
        raise ValueError("refs must not be empty")
    if ref_descriptions and len(ref_descriptions) != len(refs):
        raise ValueError("ref_descriptions length must match refs length")

    chosen_model = model or VISION_PROMPT_MODELS[0]
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Content Factory",
    }

    desc_lines = []
    for i, p in enumerate(refs):
        d = (ref_descriptions[i] if ref_descriptions else "").strip()
        d = d or "Reference image"
        desc_lines.append(f"{i+1}) {p.name}: {d}")
    refs_desc = "\n".join(desc_lines)

    prompt_text = f"""
You are an art director for FoodFlow marketing posts.

Task: write ONE image generation prompt for the given post, using the reference images to keep style consistent.

Constraints:
- Output must be photorealistic lifestyle + subtle cyberpunk accents (neon glow), premium look.
- Vertical composition (1:1 or 4:5), social-friendly.
- No visible text, no logos, no watermarks, no QR codes, no readable UI text (letters or numbers).
- Avoid uncanny hands and distorted faces.
- Keep colors aligned to brand refs (teal/green + blue glow; clean warm wood/food).

Post text (meaning only; do NOT put this text on the image):
\"\"\"{post_text}\"\"\"

Reference images:
{refs_desc}

Return STRICT JSON (no markdown):
{{
  "prompt": "single prompt string",
  "negative_prompt": "things to avoid (include: readable text, letters, numbers, watermark, QR, logo)",
  "notes": ["short bullets on what you decided"]
}}
""".strip()

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
    for p in refs:
        content.append({"type": "image_url", "image_url": {"url": _path_to_data_url(p)}})

    payload = {
        "model": chosen_model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.6,
    }

    logger.info(f"🖼️ Writing image prompt via {chosen_model} with {len(refs)} refs...")
    data = await openrouter_post(headers=headers, payload=payload, timeout=timeout_s)
    raw = data["choices"][0]["message"].get("content")
    result = _best_effort_json(raw)

    if isinstance(result, dict):
        result.setdefault("model", chosen_model)
    if not isinstance(result, dict) or not result.get("prompt"):
        raise ValueError(f"Invalid image prompt result: {result}")
    return result

