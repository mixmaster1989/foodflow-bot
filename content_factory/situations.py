from __future__ import annotations

import random
import re
from dataclasses import dataclass

from content_factory.state import FactoryState


@dataclass(frozen=True)
class Situation:
    category: str
    brief: str


SITUATIONS: list[Situation] = [
    Situation("on_the_go_snack", "перекус на бегу: съел(а) что-то по пути и уже не помнишь что именно"),
    Situation("delivery", "доставка: заказал(а) еду, хочется понять КБЖУ без угадайки"),
    Situation("eating_out", "еда вне дома: кафе/ресторан, много блюд и напитков на столе"),
    Situation("weekend", "выходные: застолье/шашлыки/поездка, легко ‘забить’ на учёт"),
    Situation("breakfast", "утро/завтрак: день начинается, хочется быстро понять ‘вписался(ась)’ или нет"),
    Situation("evening", "вечер: поздний ужин/дожор, хочется честно увидеть цифры и успокоиться"),
    Situation("alcohol", "алкоголь: бар/вино/пиво, ‘дырка’ в рационе, которую обычно не считают"),
    Situation("slipped", "сорвался(ась): съел(а) лишнего, важно не бросить, а спокойно увидеть картину"),
    Situation("shopping_receipt", "чек: магазин/кафе, проще сфоткать чек и получить КБЖУ"),
]


def pick_situation(state: FactoryState, window: int = 10) -> Situation:
    recent = set(state.last_categories[-window:])
    candidates = [s for s in SITUATIONS if s.category not in recent]
    if not candidates:
        candidates = list(SITUATIONS)
    return random.choice(candidates)


def extract_hook(text: str) -> str:
    # first sentence-ish, normalized
    t = re.sub(r"<[^>]+>", " ", text)
    t = t.strip()
    m = re.split(r"[.!?\n]", t, maxsplit=1)
    hook = (m[0] if m else t)[:160]
    hook = hook.lower()
    hook = re.sub(r"\s+", " ", hook).strip()
    return hook


def extract_final_hook(text: str) -> str:
    # last sentence-ish, normalized (for anti-repeat of endings)
    t = re.sub(r"<[^>]+>", " ", text or " ")
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    parts = re.split(r"[.!?\n]+", t)
    last = ""
    for p in reversed(parts):
        p = p.strip()
        if p:
            last = p
            break
    last = last[:200].lower()
    last = re.sub(r"[^a-zа-яё0-9\s-]+", " ", last, flags=re.IGNORECASE)
    last = re.sub(r"\s+", " ", last).strip()
    return last

