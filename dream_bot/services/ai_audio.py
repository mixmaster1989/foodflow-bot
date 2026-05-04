import aiohttp
import os
import json
import base64
import re
import logging
from config import OPENROUTER_API_KEY, GROK_PROXY

TTS_SYSTEM = (
    "Ты — голосовой чтец. Прочти дословно текст пользователя — слово в слово, ничего не добавляя и не убирая. "
    "Стиль: медленно, глубоко, таинственно — как древний мудрый оракул. "
    "Делай паузы между смысловыми блоками. Говори только по-русски."
)

DREAM_PROMPT = """Ты — Толкователь Снов. Сочетаешь глубину Юнга с мистикой древних пророков.

Сон: "{dream}"
Чувство после пробуждения: "{feeling}"

Дай толкование в трёх частях (максимум 700 символов суммарно):
1. 🌌 Мистический смысл — архетипы и символы.
2. 🧠 Психологический взгляд — что говорит подсознание.
3. 🕯 Совет Оракула — одно короткое наставление.

Пиши живо, образно, с ощущением тайны. Обращайся на "ты"."""


def _clean_for_tts(text: str) -> str:
    text = re.sub(r'[*_`#~]', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text, flags=re.UNICODE)
    text = re.sub(r'[\u2600-\u27BF\u1F300-\u1F9FF]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def _interpret(dream_text: str, feeling: str) -> tuple[str, dict]:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "google/gemini-3.1-flash-lite-preview",
        "messages": [{"role": "user", "content": DREAM_PROMPT.format(dream=dream_text, feeling=feeling)}]
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, headers=headers, json=payload, proxy=GROK_PROXY) as resp:
                resp.raise_for_status()
                data = await resp.json()
                text = data["choices"][0]["message"]["content"]
                u = data.get("usage", {})
                return text, {"prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0)}
    except Exception as e:
        logging.error(f"LLM error: {e}")
        return "Оракул сейчас занят созерцанием вечности. Постучись позже.", {}


async def _tts(text: str, output_path: str) -> bool:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "openai/gpt-audio-mini",
        "modalities": ["text", "audio"],
        "audio": {"voice": "onyx", "format": "pcm16"},
        "messages": [
            {"role": "system", "content": TTS_SYSTEM},
            {"role": "user", "content": _clean_for_tts(text)}
        ],
        "stream": True,
        "stream_options": {"include_usage": True}
    }
    try:
        audio_b64 = ""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.post(url, headers=headers, json=payload, proxy=GROK_PROXY) as resp:
                if resp.status != 200:
                    logging.error(f"TTS error {resp.status}: {(await resp.text())[:300]}")
                    return False
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        audio_data = delta.get("audio", {}).get("data", "")
                        if audio_data:
                            audio_b64 += audio_data
                    except Exception:
                        continue

        if not audio_b64:
            logging.error("TTS: пустой аудио-ответ")
            return False

        with open(output_path, "wb") as f:
            f.write(base64.b64decode(audio_b64))
        return True
    except Exception as e:
        logging.error(f"TTS error: {e}")
        return False


async def process_dream_multimodal(audio_path: str = None, text_input: str = None, feeling: str = ""):
    """Возвращает (текст толкования, путь к WAV или None, usage_dict)."""
    from services.stt import speech_to_text

    dream_text = text_input
    if audio_path:
        dream_text = await speech_to_text(audio_path)
        if not dream_text:
            return "Оракул не смог разобрать слова... Попробуй ещё раз.", None, None

    if not dream_text:
        return "Нет текста для толкования.", None, None

    interpretation, usage = await _interpret(dream_text, feeling or "неизвестно")

    wav_path = f"response_{os.getpid()}_{id(dream_text)}.wav"
    tts_ok = await _tts(interpretation, wav_path)

    return interpretation, wav_path if tts_ok else None, usage
