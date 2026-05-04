"""Тесты для services/http_client (КРИТ-1 fix).

Проверяем что singleton aiohttp.ClientSession:
- возвращает одну и ту же сессию при повторных вызовах
- пересоздаётся после close
- использует TCPConnector с лимитом 50
- close корректно работает повторно (idempotent)
"""
import aiohttp
import pytest

from services.http_client import close_http_session, get_http_session


@pytest.mark.asyncio
async def test_returns_same_session_on_subsequent_calls():
    await close_http_session()
    s1 = await get_http_session()
    s2 = await get_http_session()
    assert s1 is s2
    assert isinstance(s1, aiohttp.ClientSession)
    assert not s1.closed
    await close_http_session()


@pytest.mark.asyncio
async def test_session_recreated_after_close():
    await close_http_session()
    s1 = await get_http_session()
    await close_http_session()
    assert s1.closed
    s2 = await get_http_session()
    assert s2 is not s1
    assert not s2.closed
    await close_http_session()


@pytest.mark.asyncio
async def test_connector_has_documented_limits():
    await close_http_session()
    s = await get_http_session()
    assert s.connector.limit == 50
    assert s.connector.limit_per_host == 20
    await close_http_session()


@pytest.mark.asyncio
async def test_close_is_idempotent():
    await close_http_session()
    await close_http_session()  # second close — must not raise
    s = await get_http_session()
    assert not s.closed
    await close_http_session()
