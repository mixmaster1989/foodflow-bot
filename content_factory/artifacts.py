from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


@dataclass
class ArtifactPaths:
    run_dir: Path
    post_json: Path
    image_path: Path | None
    publish_json: Path


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_slug(value: str, max_len: int = 80) -> str:
    s = value.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9а-яё\\-_]+", "", s, flags=re.IGNORECASE)
    s = s.strip("-_")
    return (s[:max_len] or "run")


def _detect_image_ext_from_data_url(data_url: str) -> str | None:
    m = re.match(r"^data:image/(?P<fmt>[a-zA-Z0-9.+-]+);base64,", data_url)
    if not m:
        return None
    fmt = m.group("fmt").lower()
    if fmt in {"jpeg", "jpg"}:
        return "jpg"
    if fmt in {"png"}:
        return "png"
    if fmt in {"webp"}:
        return "webp"
    return fmt


async def _download_bytes(url: str, timeout_s: float = 30.0) -> bytes:
    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


async def save_run_artifacts(
    *,
    base_dir: Path,
    topic: str,
    scenario: str | None,
    post_text: str,
    image_prompt: str | None,
    image_ref: str | None,
    publish_target_chat_id: int | None,
    mode: str,
    paths: ArtifactPaths | None = None,
) -> ArtifactPaths:
    """
    Persist post text + image for every run.
    - post.json: main payload
    - image.*: decoded from data URL or downloaded from URL (if available)
    """
    if paths is None:
        paths = init_run_artifacts(base_dir=base_dir, topic=topic)
    run_dir = paths.run_dir
    stamp = run_dir.name.split("_", 1)[0] if "_" in run_dir.name else _utc_stamp()

    image_path: Path | None = None
    if image_ref and image_ref not in {"error", "error_no_url"}:
        if image_ref.startswith("data:image"):
            ext = _detect_image_ext_from_data_url(image_ref) or "png"
            header, b64 = image_ref.split(";base64,", 1)
            image_bytes = base64.b64decode(b64)
            image_path = run_dir / f"image.{ext}"
            image_path.write_bytes(image_bytes)
        elif image_ref.startswith("http://") or image_ref.startswith("https://"):
            image_bytes = await _download_bytes(image_ref)
            image_path = run_dir / "image.bin"
            image_path.write_bytes(image_bytes)

    payload: dict[str, Any] = {
        "created_at_utc": stamp,
        "mode": mode,  # e.g. "to_me" or "channel"
        "topic": topic,
        "scenario": scenario,
        "text": post_text,
        "image_prompt": image_prompt,
        "image_ref": image_ref,
        "publish_target_chat_id": publish_target_chat_id,
        "saved_image_path": str(image_path) if image_path else None,
    }

    paths.post_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.image_path = image_path
    return paths


def init_run_artifacts(*, base_dir: Path, topic: str) -> ArtifactPaths:
    artifacts_root = base_dir / "content_factory" / "runs"
    artifacts_root.mkdir(parents=True, exist_ok=True)

    stamp = _utc_stamp()
    slug = _safe_slug(topic)
    run_dir = artifacts_root / f"{stamp}_{slug}"
    if run_dir.exists():
        run_dir = artifacts_root / f"{stamp}_{slug}_{os.getpid()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    post_json = run_dir / "post.json"
    publish_json = run_dir / "publish.json"
    publish_json.write_text(json.dumps({"status": "pending"}, ensure_ascii=False, indent=2), encoding="utf-8")

    return ArtifactPaths(run_dir=run_dir, post_json=post_json, image_path=None, publish_json=publish_json)


def write_publish_result(
    paths: ArtifactPaths,
    *,
    ok: bool,
    target_chat_id: int | None,
    error: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "status": "ok" if ok else "error",
        "target_chat_id": target_chat_id,
        "error": error,
        "written_at_utc": _utc_stamp(),
    }
    paths.publish_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_run_json(paths: ArtifactPaths, filename: str, payload: dict[str, Any]) -> Path:
    p = paths.run_dir / filename
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def write_run_text(paths: ArtifactPaths, filename: str, text: str) -> Path:
    p = paths.run_dir / filename
    p.write_text(text, encoding="utf-8")
    return p

