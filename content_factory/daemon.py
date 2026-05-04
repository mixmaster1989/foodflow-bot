from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from content_factory.main import run_factory_iteration
from content_factory.notify import notify_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("content_factory.daemon")


MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _next_run_preview(hour: int, minute: int) -> str:
    now = datetime.now(MOSCOW_TZ)
    nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if nxt <= now:
        nxt = nxt + timedelta(days=1)
    return nxt.isoformat()


async def _job_wrapper() -> None:
    try:
        logger.info("⏰ Scheduled run started.")
        last_res = None
        history = []
        for attempt in range(1, 4):
            is_last = (attempt == 3)
            res = await run_factory_iteration(previous_attempts=history, is_last_chance=is_last)
            last_res = res
            if res.get("ok"):
                break
            
            # Если не прошли редактуру, сохраняем причину для следующей попытки
            if res.get("reason") == "blocked_by_editorial":
                history.append({
                    "topic": res.get("topic"),
                    "reason": res.get("details") or "blocked by judge"
                })
            else:
                # Если упало по другой причине (сеть, генерация), ретраим без добавления в историю ревизий
                pass

            if attempt < 3:
                logger.warning(f"🔁 Retry after block (attempt {attempt}/3). History size: {len(history)}")
                await asyncio.sleep(2)
        logger.info("✅ Scheduled run finished.")
        if last_res and not last_res.get("ok"):
            logger.warning(f"⚠️ Scheduled run ended without publish: {last_res}")
            reason = last_res.get("reason") or "unknown"
            run_dir = last_res.get("run_dir")
            await notify_admin(
                title="Content Factory: run not published",
                lines=[
                    f"reason: {reason}",
                    f"scenario: {last_res.get('scenario')}",
                    f"topic: {last_res.get('topic')}",
                ],
                run_dir=(Path(run_dir) if run_dir else None),
            )
    except Exception as e:
        logger.exception(f"❌ Scheduled run crashed: {e}")


async def main() -> None:
    parser = argparse.ArgumentParser(prog="content_factory.daemon")
    parser.add_argument("--run-once", action="store_true", help="Run one iteration immediately and exit.")
    parser.add_argument("--run-now", action="store_true", help="Run one iteration immediately on startup, then keep schedule.")
    args = parser.parse_args()

    if args.run_once:
        await _job_wrapper()
        return

    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    trigger = CronTrigger(hour=16, minute=0, timezone=MOSCOW_TZ)
    scheduler.add_job(_job_wrapper, trigger=trigger, id="daily_1600_msk", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()

    logger.info("🚀 Content Factory daemon started.")
    logger.info("🕒 Schedule: every day at 16:00 Europe/Moscow.")
    logger.info(f"➡️ Next run (approx): {_next_run_preview(16, 0)}")

    if args.run_now:
        # fire and forget, keep scheduler alive
        asyncio.create_task(_job_wrapper())

    # Keep running forever
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())

