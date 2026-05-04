from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FactoryState:
    last_categories: list[str] = field(default_factory=list)
    last_hooks: list[str] = field(default_factory=list)
    last_final_hooks: list[str] = field(default_factory=list)


def load_state(path: Path) -> FactoryState:
    if not path.exists():
        return FactoryState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return FactoryState(
            last_categories=list(data.get("last_categories") or []),
            last_hooks=list(data.get("last_hooks") or []),
            last_final_hooks=list(data.get("last_final_hooks") or []),
        )
    except Exception:
        return FactoryState()


def save_state(path: Path, state: FactoryState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "last_categories": state.last_categories[-50:],
        "last_hooks": state.last_hooks[-50:],
        "last_final_hooks": state.last_final_hooks[-50:],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

