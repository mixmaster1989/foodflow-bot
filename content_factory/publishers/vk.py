import logging
import base64
import re
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

from config import settings


def _tg_html_to_plain(text: str) -> str:
    if not text:
        return ""
    t = text
    t = t.replace("<blockquote>", "\n\n").replace("</blockquote>", "")
    t = t.replace("<tg-spoiler>", "").replace("</tg-spoiler>", "")
    # strip any remaining tags
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


def _decode_data_image(data_url: str) -> tuple[bytes, str]:
    header, b64 = data_url.split(";base64,", 1)
    ext = header.split("data:image/", 1)[1].split(";", 1)[0].strip().lower()
    if ext == "jpeg":
        ext = "jpg"
    return base64.b64decode(b64), ext


async def _vk_call(session: aiohttp.ClientSession, method: str, **params: Any) -> Any:
    if not settings.VK_TOKEN:
        raise RuntimeError("VK_TOKEN is not configured")
    payload = {"access_token": settings.VK_TOKEN, "v": settings.VK_API_VERSION}
    payload.update({k: v for k, v in params.items() if v is not None})
    r = await session.post(f"https://api.vk.com/method/{method}", data=payload)
    data = await r.json()
    if "error" in data:
        raise RuntimeError(f"VK API error ({method}): {data['error']}")
    return data.get("response")


async def _upload_wall_photo(session: aiohttp.ClientSession, *, image_url: str) -> str | None:
    if not settings.VK_GROUP_ID:
        raise RuntimeError("VK_GROUP_ID is not configured")

    img_bytes: bytes | None = None
    ext = "png"
    if image_url.startswith("data:image/") and ";base64," in image_url:
        img_bytes, ext = _decode_data_image(image_url)
    elif image_url.startswith("http://") or image_url.startswith("https://"):
        rr = await session.get(image_url, timeout=aiohttp.ClientTimeout(total=45.0))
        rr.raise_for_status()
        img_bytes = await rr.read()
    else:
        return None

    upload = await _vk_call(session, "photos.getWallUploadServer", group_id=settings.VK_GROUP_ID)
    upload_url = upload["upload_url"]

    form = aiohttp.FormData()
    form.add_field("photo", img_bytes, filename=f"image.{ext}", content_type=f"image/{'jpeg' if ext == 'jpg' else ext}")
    up = await session.post(upload_url, data=form, timeout=aiohttp.ClientTimeout(total=60.0))
    up.raise_for_status()
    up_data = await up.json()

    saved = await _vk_call(
        session,
        "photos.saveWallPhoto",
        group_id=settings.VK_GROUP_ID,
        photo=up_data.get("photo"),
        server=up_data.get("server"),
        hash=up_data.get("hash"),
    )
    if not saved or not isinstance(saved, list):
        return None

    item = saved[0]
    owner_id = item.get("owner_id")
    photo_id = item.get("id")
    if owner_id is None or photo_id is None:
        return None
    return f"photo{owner_id}_{photo_id}"


async def publish_to_vk(text: str, image_url: str | None = None) -> bool:
    """
    Публикует пост на стену ВК группы FoodFlow через VK API.
    """
    if not settings.VK_TOKEN or not settings.VK_GROUP_ID:
        logger.info("VK publishing is not configured; skip.")
        return False

    msg = _tg_html_to_plain(text)
    if not msg:
        return False

    async with aiohttp.ClientSession() as session:
        attachment = None
        if image_url and image_url not in {"error", "error_no_url"}:
            try:
                attachment = await _upload_wall_photo(session, image_url=image_url)
            except Exception as e:
                logger.warning(f"VK photo upload failed: {e}")
                attachment = None

        try:
            res = await _vk_call(
                session,
                "wall.post",
                owner_id=f"-{settings.VK_GROUP_ID}",
                from_group=1,
                signed=0,
                message=msg,
                attachments=attachment,
            )
            post_id = (res or {}).get("post_id")
            logger.info(f"VK post published: {post_id}")
            return True
        except Exception as e:
            logger.error(f"VK publish failed: {e}")
            return False
