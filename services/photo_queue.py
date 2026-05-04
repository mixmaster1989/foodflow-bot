import asyncio
import logging
from collections.abc import Awaitable, Callable

from aiogram import Bot, types
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

# Per-user queue limit. Защита от OOM при флуде фото:
# реальный пользователь столько за раз не присылает.
QUEUE_MAX_SIZE = 10


class PhotoQueueManager:
    """Manages per-user queues for sequential photo processing.

    Prevents race conditions and database locks when users upload multiple photos rapidly.
    """
    _queues: dict[int, asyncio.Queue] = {}
    _workers: dict[int, asyncio.Task] = {}

    @classmethod
    async def add_item(
        cls,
        user_id: int,
        message: types.Message,
        bot: Bot,
        state: FSMContext,
        processing_func: Callable[[types.Message, Bot, FSMContext, str], Awaitable[None]],
        file_id: str
    ) -> bool:
        """Add a photo to the user's processing queue.

        Returns:
            True если фото добавлено в очередь, False если очередь переполнена
            (юзеру при этом отправляется сообщение).
        """
        if user_id not in cls._queues:
            cls._queues[user_id] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)

        queue = cls._queues[user_id]
        position = queue.qsize()

        try:
            queue.put_nowait({
                "file_id": file_id,
                "message": message,
                "bot": bot,
                "state": state,
                "func": processing_func
            })
        except asyncio.QueueFull:
            logger.warning(
                f"[PhotoQueue] User {user_id}: queue full ({QUEUE_MAX_SIZE}), rejecting photo {file_id}"
            )
            try:
                await message.answer(
                    "⏳ Слишком много фото в очереди. "
                    "Подожди пока я обработаю текущие — затем пришли заново."
                )
            except Exception:
                pass
            return False

        if user_id not in cls._workers or cls._workers[user_id].done():
            cls._workers[user_id] = asyncio.create_task(cls._worker(user_id))
            logger.info(f"[PhotoQueue] User {user_id}: Queue started with first item.")
        else:
            pos_msg = position + 1
            logger.info(f"[PhotoQueue] User {user_id}: Added to queue. Position: {pos_msg}")

        return True

    @classmethod
    async def _worker(cls, user_id: int):
        """Background worker that processes items from the user's queue sequentially."""
        queue = cls._queues[user_id]

        while not queue.empty():
            item = await queue.get()
            file_id = item["file_id"]
            func = item["func"]

            logger.info(f"[PhotoQueue] User {user_id}: Processing item {file_id}")

            try:
                # Call the processing function
                # Signature: func(message, bot, state, file_id)
                await func(item["message"], item["bot"], item["state"], file_id)
            except Exception as e:
                logger.error(f"[PhotoQueue] Error processing item {file_id}: {e}")
                try:
                     await item["message"].answer("❌ Произошла ошибка при обработке этого фото.")
                except Exception:
                    pass
            finally:
                queue.task_done()
                remaining = queue.qsize()
                logger.info(f"[PhotoQueue] User {user_id}: Processing complete. Items left: {remaining}")

        # Cleanup when queue empty
        if user_id in cls._workers:
            del cls._workers[user_id]
        if queue.empty() and user_id in cls._queues:
            del cls._queues[user_id]
