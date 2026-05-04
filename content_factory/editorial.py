from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx
from content_factory.http_client import openrouter_post

from config import settings

logger = logging.getLogger(__name__)


COMPLIANCE_MODELS = ["google/gemini-3-flash-preview"]
CHIEF_EDITOR_MODELS = ["deepseek/deepseek-v3.2"]
REWRITER_MODELS = ["google/gemini-3-flash-preview"]
JUDGE_MODELS = ["anthropic/claude-sonnet-4.6"]


INTERNAL_TERMS = [
    "universalinput",
    "aibrainservice",
    "foodflow-bot",
    "handlers/",
    "services/",
]

BANNED_PATTERNS = [
    r"\bапрель\s+\d{4}\b",
    # NOTE: mentioning a year isn't inherently bad; it becomes spammy when repeated.
    # We only hard-flag "в 20xx" constructions that sound like dated marketing copy.
    r"\bв\s+20\d{2}\b",
    r"\bсейчас\s+(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])\b",
]

SHAMING_TOKENS = [
    "нормальный человек",
    "ненормальный",
    "тупо",
    "тупая",
    "цирк",
    "страдают",
    "смешно",
    "поздравляю",
]

HARD_BLOCK_FLAGS = {"medical_claims", "result_guarantees", "pii", "dangerous"}

WEAK_ENDING_PATTERNS = [
    r"\bостальное\b",
    r"не требует лишних переживаний",
    r"бот возьм[её]т на себя",
    r"вопрос регулярности",
    r"главное\s+[-—]\s*регулярность",
]

LECTURE_PATTERNS = [
    r"\bсмысл простой\b",
    r"худеют\s+не\s+за\s+сч[её]т",
    r"\bважно понимать\b",
    r"\bдело в том(,)? что\b",
    r"\bна самом деле\b",
]


@dataclass(frozen=True)
class EditorialResult:
    status: str  # approve | blocked
    text_final: str
    compliance: dict[str, Any]
    chief: dict[str, Any]
    judge: dict[str, Any]


def _contains_internal_terms(text: str) -> list[str]:
    low = text.lower()
    found = [t for t in INTERNAL_TERMS if t in low]
    return found


def _find_banned(text: str) -> list[str]:
    hits: list[str] = []
    for pat in BANNED_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            hits.append(pat)
    return hits


def _find_shaming(text: str) -> list[str]:
    low = text.lower()
    return [t for t in SHAMING_TOKENS if t in low]

def _has_weak_ending(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in WEAK_ENDING_PATTERNS)

def _has_lecture(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in LECTURE_PATTERNS)

def _kbju_count(text: str) -> int:
    return len(re.findall(r"\bкбжу\b", text.lower()))

def _last_sentence_word_count(text: str) -> int:
    s = (text or "").strip()
    if not s:
        return 0
    # Rough split by sentence-ending punctuation/newlines, keep the last non-empty chunk.
    parts = re.split(r"[.!?\n]+", s)
    last = ""
    for p in reversed(parts):
        p = p.strip()
        if p:
            last = p
            break
    if not last:
        return 0
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", last)
    return len(words)


def _is_only_soft_judge_issues(issues: list[str]) -> bool:
    """
    Judge may be overly strict about generic wording like "результат" or benign CTA additions.
    We treat these as non-blocking.
    """
    if not issues:
        return False
    soft_patterns = [
        r"слово 'результат'",
        r"слово \"результат\"",
        r"появилось слово 'результат'",
        r"появилось слово \"результат\"",
        r"призыв к действию",
        r"cta",
        r"голосовой помощник",
        r"войс",
        r"фото",
        r"чек",
        r"отправка",
        r"голосовой ввод",
    ]
    for it in issues:
        s = str(it).lower()
        if not any(re.search(p, s) for p in soft_patterns):
            return False
    return True


async def _call_llm_json(model: str, prompt: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Content Factory - Editorial",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    data = await openrouter_post(headers=headers, payload=payload, timeout=35.0)
    raw_content = data["choices"][0]["message"].get("content")
    if not raw_content:
        raise ValueError("Empty model content")
    raw = str(raw_content).strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
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


async def compliance_check(topic: str, text: str, *, tone_mode: str = "soft") -> dict[str, Any]:
    internal_hits = _contains_internal_terms(text)
    banned_hits = _find_banned(text)
    shaming_hits = _find_shaming(text)
    weak_ending = _has_weak_ending(text)
    lecture = _has_lecture(text)
    kbju_repetition = _kbju_count(text) > 1
    hook_too_long = _last_sentence_word_count(text) > 10

    tone_mode = (tone_mode or "soft").lower()
    if tone_mode not in {"soft", "hard"}:
        tone_mode = "soft"

    prompt = f"""
ЦЕЛЕВАЯ АУДИТОРИЯ (ЦА):
- РФ, обычные люди (не айтишники). Текст должен быть понятным и не звучать снобски.

ЗАПРЕЩЕНО (пример и почему):
- Плохо: «считать КБЖУ руками — это как писать код в блокноте» — IT-метафора, отталкивает не-айтишную ЦА.
- Такой тон/сравнения считать нежелательными (если есть — проси revise).

Ты — модератор/комплаенс FoodFlow. Проверь текст для РФ аудитории.

Задача: выявить рискованные места и решить можно ли публиковать.

Блокируй если есть:
- медицинские обещания/лечение/диагнозы
- гарантии результатов ("минус 10 кг", "похудеешь за неделю")
- шейминг/оскорбления аудитории
- призывы к опасным действиям
- персональные данные

Отдельно проверь: нет ли внутренних названий из кода и дат/годов в тексте.
Дополнительно (качество): если финал ватный/без выбора или текст превращается в лекцию — проси revise.

ТЕМА: {topic}
ТЕКСТ:
\"\"\"{text}\"\"\"

ВЕРНИ JSON:
{{
  "action": "ok" | "revise" | "block",
  "reasons": ["..."],
  "flags": ["medical_claims", "result_guarantees", "shaming", "dangerous", "pii", "internal_terms", "dates", "weak_cta", "lecture", "kbju_repetition", "hook_too_long"],
  "revise_edits": ["точечная правка 1", "точечная правка 2"],
  "internal_terms_found": {internal_hits},
  "banned_time_patterns_found": {banned_hits},
  "shaming_tokens_found": {shaming_hits}
}}
""".strip()

    for m in COMPLIANCE_MODELS:
        try:
            res = await _call_llm_json(m, prompt)
            # Merge deterministic flags
            if internal_hits and "internal_terms" not in res.get("flags", []):
                res.setdefault("flags", []).append("internal_terms")
            if banned_hits and "dates" not in res.get("flags", []):
                res.setdefault("flags", []).append("dates")
            if shaming_hits and "shaming" not in res.get("flags", []):
                res.setdefault("flags", []).append("shaming")
            if weak_ending and "weak_cta" not in res.get("flags", []):
                res.setdefault("flags", []).append("weak_cta")
            if lecture and "lecture" not in res.get("flags", []):
                res.setdefault("flags", []).append("lecture")
            if kbju_repetition and "kbju_repetition" not in res.get("flags", []):
                res.setdefault("flags", []).append("kbju_repetition")
            if hook_too_long and "hook_too_long" not in res.get("flags", []):
                res.setdefault("flags", []).append("hook_too_long")
            if internal_hits:
                res["internal_terms_found"] = internal_hits
            if banned_hits:
                res["banned_time_patterns_found"] = banned_hits
            if shaming_hits:
                res["shaming_tokens_found"] = shaming_hits

            action = (res.get("action") or "").lower()
            if action not in {"ok", "revise", "block"}:
                ok = bool(res.get("ok"))
                action = "ok" if ok else "block"
            res["action"] = action

            flags = set(res.get("flags") or [])
            if flags & HARD_BLOCK_FLAGS:
                res["action"] = "block"
            elif res["action"] == "block":
                res["action"] = "revise"

            if res["action"] == "revise" and not res.get("revise_edits"):
                edits: list[str] = []
                if shaming_hits:
                    edits.append("Убери сарказм/насмешку и любые ярлыки в адрес читателя; замени на нейтральные формулировки.")
                    edits.append("Запрещены слова/обороты: «нормальный человек», «тупо», «цирк», «страдают», «поздравляю» (сарказм), «смешно».")
                if lecture:
                    edits.append("Убери объяснялку/лекцию (например «смысл простой…»). Замени на сцену → действие → короткий вывод.")
                if weak_ending:
                    edits.append("Сделай финал жёстким: 1 предложение ДО 10 слов, выбор/давление (либо/либо, или/или). Запрещено «остальное…/бот возьмёт…/не переживай…».")
                if hook_too_long:
                    edits.append("Укороти финальную строку до 10 слов максимум. Оставь только выбор/давление, без пояснений.")
                if kbju_repetition:
                    edits.append("Не повторяй «КБЖУ» в каждом абзаце. Оставь 1 раз, дальше пиши «цифры/сводка/понятно что съел(а)».")
                if banned_hits:
                    edits.append("Убери любые упоминания месяца/года/дат; оставь максимум сезонную отсылку без дат.")
                if internal_hits:
                    edits.append("Убери любые внутренние названия из кода/модулей; опиши по-человечески.")
                res["revise_edits"] = edits
            return res
        except Exception as e:
            logger.warning(f"Compliance model {m} failed: {e}")
            continue

    return {
        "action": "block",
        "reasons": ["compliance_check_failed"],
        "flags": ["system_error"],
        "internal_terms_found": internal_hits,
        "banned_time_patterns_found": banned_hits,
        "shaming_tokens_found": shaming_hits,
    }


async def chief_editor(
    topic: str,
    text: str,
    *,
    previous_attempts: list[dict] | None = None
) -> dict[str, Any]:
    prompt = f"""
ЦЕЛЕВАЯ АУДИТОРИЯ (ЦА):
- РФ, обычные люди (не айтишники). Пишем простыми словами.

ЗАПРЕЩЕНО (пример и почему):
- Плохо: «…как писать код в блокноте» — IT-метафора, не для ЦА и звучит снобски.
- Если встречается — вычищай/заменяй на бытовое.

Ты — главный редактор FoodFlow. ЦА: РФ, обычные люди (не кодеры).

Правила:
- ВНИМАНИЕ: "ТЕМА" — это наш внутренний бриф-задание. Он не публикуется и это не заголовок! Запрещено оценивать ТЕМУ или предлагать правки к ТЕМЕ (например, "убрать IT-слово из подзаголовка/темы"). Оценивай только сам ТЕКСТ.
- нельзя добавлять новые факты о продукте, только переформулировать
- нельзя упоминать внутренние названия из кода
- нельзя писать месяц/год/дату в тексте
- стиль: коротко, читаемо, 2–3 абзаца, в конце жёсткий/чёткий крючок (1 строка)
- финальная строка: 1 предложение ДО 10 слов, выбор/давление (либо/либо, или/или). Никаких «остальное…».
- не скатывайся в «объяснялку» (например «смысл простой…»), держи сцену→действие→удар.
- «КБЖУ» не повторять в каждом абзаце: 1 раз максимум, дальше «цифры/сводка».
- ЗАПРЕЩЁННЫЕ слова-гарантии: «точно», «гарантированно», «обязательно», «наверняка», «100%» — не используй.
- ЗАПРЕЩЕНЫ временны́е обещания: «через минуту», «за секунды», «мгновенно», «сразу увидишь» и подобные — не добавляй даже если звучит красиво.
- ЗАПРЕЩЕНЫ слова-усилители при описании данных/результатов продукта: «полная», «точная», «исчерпывающая», «абсолютно все» — это новые обещания которых не было в оригинале.
- При переработке финала: сохраняй эмоциональный тон ДО. Если оригинал нейтральный — финал нейтральный. Не добавляй давление и тревогу которых не было.
- не выкидывай конкретику, которая была в исходнике (например «чек», «голосом»): можно сжать, но смысл/возможности сохраняй.

ТЕМА: {topic}
ТЕКСТ:
\"\"\"{text}\"\"\"

Верни JSON:
{{
  "decision": "approve" | "revise" | "regenerate",
  "edits": [
    "точечная правка 1",
    "точечная правка 2"
  ],
  "notes": ["..."]
}}
""".strip()

    history_context = ""
    if previous_attempts:
        history_context = "\n\nИСТОРИЯ ПРЕДЫДУЩИХ ОШИБОК (НЕ ПОВТОРЯЙ ИХ):\n"
        for i, attempt in enumerate(previous_attempts, 1):
            history_context += f"Попытка {i}: {attempt.get('reason', 'unknown')}\n"

    prompt += history_context

    for m in CHIEF_EDITOR_MODELS:
        try:
            return await _call_llm_json(m, prompt)
        except Exception as e:
            logger.warning(f"Chief editor model {m} failed: {e}")
            continue

    return {"decision": "regenerate", "edits": ["system_error"], "notes": []}


async def apply_edits(
    topic: str,
    text: str,
    *,
    edits: list[str],
    previous_attempts: list[dict] | None = None
) -> str:
    prompt = f"""
ЦЕЛЕВАЯ АУДИТОРИЯ (ЦА):
- РФ, обычные люди (не айтишники). Никаких IT-метафор.

ЗАПРЕЩЕНО (пример и почему):
- Плохо: «…как писать код в блокноте» — IT-метафора, не для ЦА.
- При рерайте: удаляй/заменяй на нейтральное/бытовое.

Ты — рерайтер FoodFlow. Твоя задача: применить правки, НЕ меняя смысл и НЕ добавляя новые факты.

ЖЁСТКО:
- ВНИМАНИЕ: "ТЕМА" — это наш внутренний бриф. Запрещено копировать куски ТЕМЫ в текст в виде заголовков или подзаголовков. Фокусируйся только на редактировании ИСХОДНОГО ТЕКСТА.
- не добавляй никаких новых фич, цифр, обещаний результата
- не упоминай внутренние названия из кода
- не пиши месяц/год/дату
- ЗАПРЕЩЕНЫ временны́е обещания: «сразу увидишь», «через минуту», «мгновенно», «за секунды» — не добавляй
- ЗАПРЕЩЕНЫ слова-усилители применительно к данным: «точные», «полные», «исчерпывающие» — не добавляй
- ЗАПРЕЩЕНЫ слова-гарантии: «наверняка», «точно», «гарантированно» — не добавляй
- оставь 2–3 абзаца

ТЕМА: {topic}
ИСХОДНЫЙ ТЕКСТ:
\"\"\"{text}\"\"\"

ПРАВКИ (выполни дословно по смыслу):
{edits}

Верни JSON:
{{ "text": "..." }}
""".strip()

    history_context = ""
    if previous_attempts:
        history_context = "\n\nИСТОРИЯ ПРЕДЫДУЩИХ ПРАВОК:\n"
        for i, attempt in enumerate(previous_attempts, 1):
            history_context += f"Попытка {i} не прошла, потому что: {attempt.get('reason', 'unknown')}\n"
    
    prompt += history_context

    for m in REWRITER_MODELS:
        try:
            res = await _call_llm_json(m, prompt)
            text_res = (res.get("text") or "").strip()
            return text_res or text
        except Exception as e:
            logger.warning(f"Rewrite model {m} failed: {e}")
            continue

    return text


async def judge_diff(
    topic: str,
    original_text: str,
    final_text: str,
    *,
    is_last_chance: bool = False
) -> dict[str, Any]:
    prompt = f"""
ЦЕЛЕВАЯ АУДИТОРИЯ (ЦА):
- РФ, обычные люди (не айтишники).

ЗАПРЕЩЕНО (пример и почему):
- Плохо: «…как писать код в блокноте» — IT-метафора, не для ЦА и признак того, что текст стал “для кодеров”.
- Если в ПОСЛЕ появилась/сохранилась такая метафора — добавь issue (но не приписывай это как “новый факт”).

Ты — строгий редактор-судья. Сравни ДО и ПОСЛЕ.

Найди:
- появились ли новые факты/фичи, которых не было ни в ДО, ни в ТЕМЕ. (Если новая фича/условие явно упоминается в ТЕМЕ — её появление в тексте ПОСЛЕ разрешено и не считается ошибкой).
- появились ли обещания результата / медицинские утверждения
- появились ли внутренние термины из кода

ВАЖНО: слово «результат» само по себе НЕ является обещанием результата. Обещание — это конкретика/гарантия:
- цифры (кг/см/проценты) и сроки (за 7 дней/неделю/месяц)
- временны́е обещания: «через минуту», «за секунды», «мгновенно», «сразу увидишь»
- слова-гарантии: «гарантированно», «точно», «обязательно», «наверняка», «100%»
- слова-усилители применительно к данным/результатам продукта которых не было в ДО: «полная», «точная», «исчерпывающая»

Добавление мягкого CTA («попробуй», «сфотографируй») — допустимо, если не добавляет новых фактов.

ТЕМА: {topic}

ДО:
\"\"\"{original_text}\"\"\"

ПОСЛЕ:
\"\"\"{final_text}\"\"\"

Верни JSON:
{{
  "ok": true/false,
  "issues": ["..."],
  "new_facts_suspected": true/false
}}
""".strip()

    if is_last_chance:
        prompt += "\n\nВНИМАНИЕ: Это ПОСЛЕДНЯЯ ПОПЫТКА. Крайне нежелательно блокировать пост. Если нет критических нарушений (мед.диагнозы, ПДН), ОБЯЗАТЕЛЬНО ОДОБРЯЙ ('ok': true)."

    for m in JUDGE_MODELS:
        try:
            res = await _call_llm_json(m, prompt)
            # Add deterministic checks
            internal_hits = _contains_internal_terms(final_text)
            banned_hits = _find_banned(final_text)
            if internal_hits:
                res.setdefault("issues", []).append(f"internal_terms:{internal_hits}")
                res["ok"] = False
            if banned_hits:
                res.setdefault("issues", []).append("time_mentions_found")
                res["ok"] = False

            # Soften overly strict judge-only issues (e.g. generic "результат" wording)
            issues = res.get("issues") or []
            if res.get("ok") is False and _is_only_soft_judge_issues(issues):
                res["ok"] = True
            return res
        except Exception as e:
            logger.warning(f"Judge model {m} failed: {e}")
            continue

    return {"ok": False, "issues": ["judge_failed"], "new_facts_suspected": True}


async def editorial_pipeline(
    topic: str, 
    text: str, 
    *, 
    tone_mode: str = "soft", 
    max_compliance_rewrites: int = 2,
    previous_attempts: list[dict] | None = None,
    is_last_chance: bool = False
) -> EditorialResult:
    current_text = text
    comp = await compliance_check(topic, current_text, tone_mode=tone_mode)
    rewrites = 0

    while comp.get("action") == "revise" and rewrites < max_compliance_rewrites:
        edits = comp.get("revise_edits") or []
        if not edits:
            break
        current_text = await apply_edits(topic, current_text, edits=edits, previous_attempts=previous_attempts)
        rewrites += 1
        comp = await compliance_check(topic, current_text, tone_mode=tone_mode)

    if comp.get("action") == "block" and not is_last_chance:
        return EditorialResult(status="blocked", text_final=current_text, compliance=comp, chief={}, judge={})
    elif comp.get("action") == "block" and is_last_chance:
        comp["action"] = "ok" # Force compliance in extreme case

    chief = await chief_editor(topic, current_text, previous_attempts=previous_attempts)
    decision = chief.get("decision")
    edits = chief.get("edits") or []

    text_final = current_text
    if decision in {"revise", "regenerate"} and edits and edits != ["system_error"]:
        text_final = await apply_edits(topic, current_text, edits=edits, previous_attempts=previous_attempts)

    judge = await judge_diff(topic, current_text, text_final, is_last_chance=is_last_chance)
    if not judge.get("ok") and not is_last_chance:
        return EditorialResult(status="blocked", text_final=text_final, compliance=comp, chief=chief, judge=judge)
    elif not judge.get("ok") and is_last_chance:
        judge["ok"] = True # Force judge approval

    return EditorialResult(status="approve", text_final=text_final, compliance=comp, chief=chief, judge=judge)

