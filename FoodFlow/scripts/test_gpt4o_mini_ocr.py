import base64
import json
import sys
import time
from pathlib import Path

import requests

from FoodFlow.config import settings


PROMPT = (
    "Analyze this receipt image. Return a JSON object with a list of items "
    "and the total amount. Do not include markdown formatting, just raw JSON. "
    'Expected format: {"items": [{"name": "str", "price": float, "quantity": float}], "total": float}'
)

MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o-mini-2024-07-18",
]


def load_image_bytes(path: Path) -> bytes:
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    return path.read_bytes()


def call_model(model: str, image_bytes: bytes) -> dict:
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Bot OCR Benchmark",
    }

    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return {
        "raw": content,
        "usage": data.get("usage"),
    }


def main():
    image_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("receipt.jpeg")
    image_bytes = load_image_bytes(image_path)

    results = {}
    for model in MODELS:
        print(f"\n=== {model} ===")
        start = time.perf_counter()
        try:
            result = call_model(model, image_bytes)
            elapsed = time.perf_counter() - start
            results[model] = {"success": True, "elapsed": elapsed, **result}
            print(f"✔ Success in {elapsed:.2f}s")
            print(result["raw"])
        except Exception as exc:
            elapsed = time.perf_counter() - start
            results[model] = {"success": False, "elapsed": elapsed, "error": str(exc)}
            print(f"✘ Error in {elapsed:.2f}s: {exc}")

    summary_path = Path("gpt4o_mini_ocr_results.json")
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()

