"""Тесты для services/photo_queue (КРИТ-2 fix).

Проверяем что per-user queue имеет maxsize=10:
- первые QUEUE_MAX_SIZE фото добавляются успешно (return True)
- (N+1)-е фото отклоняется (return False), юзер получает сообщение
- Queue создаётся именно с указанным maxsize
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.photo_queue import QUEUE_MAX_SIZE, PhotoQueueManager


@pytest.fixture(autouse=True)
def cleanup_queue_state():
    yield
    # cancel all worker tasks created in tests so they don't leak
    for task in list(PhotoQueueManager._workers.values()):
        if not task.done():
            task.cancel()
    PhotoQueueManager._queues.clear()
    PhotoQueueManager._workers.clear()


def _make_args():
    message = MagicMock()
    message.answer = AsyncMock()
    bot = MagicMock()
    state = MagicMock()
    func = AsyncMock()
    return message, bot, state, func


def _block_worker_for(user_id: int) -> None:
    """Подменяем worker фейковым tasks чтобы реальный не выгребал очередь.

    Позволяет проверить накопление в Queue до maxsize детерминированно.
    """
    PhotoQueueManager._workers[user_id] = asyncio.create_task(asyncio.sleep(3600))


@pytest.mark.asyncio
async def test_first_n_items_accepted():
    user_id = 9001
    _block_worker_for(user_id)

    message, bot, state, func = _make_args()
    for i in range(QUEUE_MAX_SIZE):
        ok = await PhotoQueueManager.add_item(
            user_id, message, bot, state, func, f"file_{i}"
        )
        assert ok is True, f"item {i} should be accepted"


@pytest.mark.asyncio
async def test_overflow_returns_false_and_notifies_user():
    user_id = 9002
    _block_worker_for(user_id)

    message, bot, state, func = _make_args()
    for i in range(QUEUE_MAX_SIZE):
        await PhotoQueueManager.add_item(
            user_id, message, bot, state, func, f"file_{i}"
        )

    ok = await PhotoQueueManager.add_item(
        user_id, message, bot, state, func, "overflow_file"
    )
    assert ok is False
    message.answer.assert_called_once()
    sent_text = message.answer.call_args[0][0]
    assert "очереди" in sent_text


@pytest.mark.asyncio
async def test_queue_uses_max_size():
    user_id = 9003
    _block_worker_for(user_id)

    message, bot, state, func = _make_args()
    await PhotoQueueManager.add_item(user_id, message, bot, state, func, "f1")

    queue = PhotoQueueManager._queues[user_id]
    assert queue.maxsize == QUEUE_MAX_SIZE


@pytest.mark.asyncio
async def test_user_message_failure_does_not_break_add_item():
    """Если message.answer бросит исключение — add_item всё равно вернёт False."""
    user_id = 9004
    _block_worker_for(user_id)

    message, bot, state, func = _make_args()
    message.answer.side_effect = Exception("Telegram down")

    for i in range(QUEUE_MAX_SIZE):
        await PhotoQueueManager.add_item(
            user_id, message, bot, state, func, f"file_{i}"
        )

    ok = await PhotoQueueManager.add_item(
        user_id, message, bot, state, func, "overflow"
    )
    assert ok is False
