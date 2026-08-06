#!/usr/bin/env python3
import sys
import os
import asyncio
import logging

# Ensure root foodflow-bot_new directory is on sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("vk_influencer_daemon")

from content_factory.guerrilla.vk_influencer import influencer_task
from content_factory.guerrilla.memory import init_db

async def main():
    logger.info("🚀 Starting Standalone VK Influencer Daemon (Анна Третьякова)...")
    await init_db()
    await influencer_task()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 VK Influencer Daemon stopped by user.")
    except Exception as e:
        logger.critical(f"❌ VK Influencer Daemon fatal error: {e}", exc_info=True)
