import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable
from aiogram import Bot, types
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

class PhotoQueueManager:
    """Manages per-user queues for sequential photo processing.
    
    Prevents race conditions and database locks when users upload multiple photos rapidly.
    """
    _queues: Dict[int, asyncio.Queue] = {}
    _workers: Dict[int, asyncio.Task] = {}

    @classmethod
    async def add_item(
        cls, 
        user_id: int, 
        message: types.Message, 
        bot: Bot, 
        state: FSMContext, 
        processing_func: Callable[[types.Message, Bot, FSMContext, str], Awaitable[None]],
        file_id: str
    ) -> None:
        """Add a photo to the user's processing queue.
        
        Args:
            user_id: Telegram user ID
            message: Message object (for replying)
            bot: Bot instance
            state: FSM context
            processing_func: Async function to call for processing
            file_id: ID of the photo file to process
        """
        if user_id not in cls._queues:
            cls._queues[user_id] = asyncio.Queue()
        
        queue = cls._queues[user_id]
        position = queue.qsize()  # Items currently waiting (excluding active one if worker running)
        
        # If worker is already running, there's 1 active item provided user_id is in _workers
        # qsize gives waiting items.
        
        await queue.put({
            "file_id": file_id,
            "message": message,
            "bot": bot,
            "state": state,
            "func": processing_func
        })
        
        # Log exact position
        # Note: If queue was empty and worker not running, this is item #1 (starts immediately).
        # If worker running, this is item #(qsize).
        
        if user_id not in cls._workers or cls._workers[user_id].done():
            # Start worker if not active
            cls._workers[user_id] = asyncio.create_task(cls._worker(user_id))
            logger.info(f"[PhotoQueue] User {user_id}: Queue started with first item.")
        else:
            # Already running - notify user about queue position
            # Position 1 means 1 item WAITING (plus 1 processing).
            pos_msg = position + 1 # 1-based index for user
            logger.info(f"[PhotoQueue] User {user_id}: Added to queue. Position: {pos_msg}")
            
            # Optional: Notify user if queue is getting long (>1)
            # Use 'create_task' to not block adding to queue
            # try:
            #    await message.answer(f"📸 Фото в очереди: {pos_msg}. Обрабатываю предыдущие...")
            # except:
            #    pass

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
                except:
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
