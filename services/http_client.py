"""Singleton aiohttp.ClientSession для всех outbound HTTP-вызовов.

Решает КРИТ-1: раньше каждый retry в OCR/Normalization создавал новую
ClientSession (до 18 сессий на 1 OCR-вызов), что приводило к утечке
сокетов при нагрузке.

Использование:
    from services.http_client import get_http_session

    session = await get_http_session()
    async with session.post(url, json=payload, timeout=20) as resp:
        ...

Lifecycle:
    Сессия создаётся лениво при первом get_http_session().
    Закрывается через close_http_session() при shutdown бота (см. main.py).
"""
import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)

_session: aiohttp.ClientSession | None = None
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def get_http_session() -> aiohttp.ClientSession:
    """Вернуть глобальную aiohttp.ClientSession (создать при первом вызове).

    TCPConnector с лимитом 50 одновременных соединений (20 на хост) —
    защита от утечки сокетов под нагрузкой.
    """
    global _session
    if _session is None or _session.closed:
        async with _get_lock():
            if _session is None or _session.closed:
                connector = aiohttp.TCPConnector(limit=50, limit_per_host=20)
                _session = aiohttp.ClientSession(connector=connector)
                logger.info("HTTP session initialized (limit=50, limit_per_host=20)")
    return _session


async def close_http_session() -> None:
    """Закрыть глобальную сессию. Вызывать при shutdown бота."""
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
        logger.info("HTTP session closed")
    _session = None
