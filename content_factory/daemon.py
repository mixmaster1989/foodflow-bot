from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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
        skip_file = Path("/home/user1/foodflow-bot_new/skip_today.lock")
        if skip_file.exists():
            logger.warning("🚫 skip_today.lock file found! Skipping today's Telegram/VK/Dzen post iteration as requested by user.")
            try:
                skip_file.unlink()
                logger.info("🗑️ skip_today.lock deleted automatically so tomorrow runs normally.")
            except Exception as e:
                logger.error(f"Failed to delete skip_today.lock: {e}")
            return

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


async def _shorts_job_wrapper() -> None:
    try:
        import os
        logger.info("⏰ Scheduled YouTube Shorts run started.")
        os.environ.pop("SHORTS_FORCE_RUN_DIR", None)
        os.environ.pop("SHORTS_PUBLISH_AT", None)
        os.environ["SHORTS_LOCALE"] = "ru"
        from content_factory.shorts_generator.worker import main as run_shorts_worker
        await run_shorts_worker()
        logger.info("✅ Scheduled YouTube Shorts run finished successfully.")
    except Exception as e:
        logger.exception(f"❌ Scheduled YouTube Shorts run crashed: {e}")
    finally:
        import os
        os.environ.pop("SHORTS_LOCALE", None)


async def _shorts_es_job_wrapper() -> None:
    try:
        import os
        logger.info("⏰ Scheduled Spanish YouTube Shorts run started.")
        os.environ.pop("SHORTS_FORCE_RUN_DIR", None)
        os.environ.pop("SHORTS_PUBLISH_AT", None)
        os.environ["SHORTS_LOCALE"] = "es"
        from content_factory.shorts_generator.worker import main as run_shorts_worker
        await run_shorts_worker()
        logger.info("✅ Scheduled Spanish YouTube Shorts run finished successfully.")
    except Exception as e:
        logger.exception(f"❌ Scheduled Spanish YouTube Shorts run crashed: {e}")
    finally:
        import os
        os.environ.pop("SHORTS_LOCALE", None)


async def _youtube_diplomat_job_wrapper() -> None:
    try:
        from content_factory.youtube_diplomat import run_youtube_diplomat_pass

        stats = await run_youtube_diplomat_pass()
        logger.info("✅ YouTube Diplomat pass: %s", stats)
    except Exception as e:
        logger.exception(f"❌ YouTube Diplomat pass crashed: {e}")


async def _morning_shorts_job_wrapper() -> None:
    try:
        logger.info("⏰ Scheduled autonomous morning YouTube Shorts run started [RU].")
        from content_factory.generators.autonomous_shorts import run_morning_shorts_pipeline
        await run_morning_shorts_pipeline(locale="ru")
        logger.info("✅ Scheduled autonomous morning YouTube Shorts run finished successfully [RU].")
    except Exception as e:
        logger.exception(f"❌ Scheduled autonomous morning YouTube Shorts run crashed [RU]: {e}")


async def _morning_shorts_es_job_wrapper() -> None:
    try:
        logger.info("⏰ Scheduled autonomous morning YouTube Shorts run started [ES/LATAM].")
        from content_factory.generators.autonomous_shorts import run_morning_shorts_pipeline
        await run_morning_shorts_pipeline(locale="es")
        logger.info("✅ Scheduled autonomous morning YouTube Shorts run finished successfully [ES/LATAM].")
    except Exception as e:
        logger.exception(f"❌ Scheduled autonomous morning YouTube Shorts run crashed [ES/LATAM]: {e}")


async def _post_es_job_wrapper() -> None:
    try:
        logger.info("⏰ Scheduled Spanish Telegram post run started.")
        from content_factory.main_es import run_factory_iteration_es
        await run_factory_iteration_es()
        logger.info("✅ Scheduled Spanish Telegram post run finished successfully.")
    except Exception as e:
        logger.exception(f"❌ Scheduled Spanish Telegram post run crashed: {e}")


def _cleanup_runs_job() -> None:
    """Sync cleanup of old content_factory artifact folders (runs retention)."""
    import subprocess
    import sys

    script = Path(__file__).resolve().parent.parent / "scripts" / "cleanup_content_factory_runs.py"
    try:
        logger.info("🧹 Scheduled content_factory runs cleanup started.")
        subprocess.run(
            [sys.executable, str(script), "--days", "14"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("✅ Scheduled content_factory runs cleanup finished.")
    except subprocess.CalledProcessError as e:
        logger.error("❌ Runs cleanup failed: %s\n%s", e.stderr or e, e.stdout or "")
    except Exception as e:
        logger.exception(f"❌ Runs cleanup crashed: {e}")


async def main() -> None:
    parser = argparse.ArgumentParser(prog="content_factory.daemon")
    parser.add_argument("--run-once", action="store_true", help="Run one iteration immediately and exit.")
    parser.add_argument("--run-now", action="store_true", help="Run one iteration immediately on startup, then keep schedule.")
    parser.add_argument("--run-morning-shorts", action="store_true", help="Run the autonomous morning Shorts generation immediately and exit.")
    parser.add_argument("--run-morning-shorts-es", action="store_true", help="Run the autonomous Spanish morning Shorts generation immediately and exit.")
    parser.add_argument("--run-telegram-es", action="store_true", help="Run the Spanish Telegram post translation and publication immediately and exit.")
    parser.add_argument("--run-shorts-es", action="store_true", help="Run the Spanish afternoon Shorts generation immediately and exit.")
    args = parser.parse_args()

    if args.run_once:
        await _job_wrapper()
        return

    if args.run_morning_shorts:
        await _morning_shorts_job_wrapper()
        return

    if args.run_morning_shorts_es:
        await _morning_shorts_es_job_wrapper()
        return

    if args.run_telegram_es:
        await _post_es_job_wrapper()
        return

    if args.run_shorts_es:
        await _shorts_es_job_wrapper()
        return

    # Telegram/VK/Dzen Post: FIXED at 16:00 MSK (not dynamic)
    POST_HOUR, POST_MINUTE = 16, 0

    # Spanish Telegram Post: FIXED at 16:30 MSK (shifted to avoid conflict with Russian Shorts generation)
    SPANISH_POST_HOUR, SPANISH_POST_MINUTE = 16, 30

    # YouTube Shorts trigger: FIXED at 16:05 MSK (not dynamic)
    SHORTS_HOUR, SHORTS_MINUTE = 16, 5

    # Spanish YouTube Shorts trigger: FIXED at 16:35 MSK (shifted to avoid conflict with Russian Shorts generation)
    SPANISH_SHORTS_HOUR, SPANISH_SHORTS_MINUTE = 16, 35

    # Autonomous Morning Shorts trigger: FIXED at 09:00 MSK
    MORNING_SHORTS_HOUR, MORNING_SHORTS_MINUTE = 9, 0

    # Autonomous Spanish Morning Shorts trigger: FIXED at 10:10 MSK
    MORNING_SHORTS_ES_HOUR, MORNING_SHORTS_ES_MINUTE = 10, 10

    scheduler = AsyncIOScheduler(
        timezone=MOSCOW_TZ,
        job_defaults={
            "misfire_grace_time": 3600,
            "coalesce": True,
        }
    )
    trigger = CronTrigger(hour=POST_HOUR, minute=POST_MINUTE, timezone=MOSCOW_TZ)
    scheduler.add_job(
        _job_wrapper,
        trigger=trigger,
        id="daily_post_1600_msk",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Afternoon YouTube Shorts: disabled as requested to focus on high-quality morning Shorts
    # shorts_trigger = CronTrigger(hour=SHORTS_HOUR, minute=SHORTS_MINUTE, timezone=MOSCOW_TZ)
    # scheduler.add_job(
    #     _shorts_job_wrapper,
    #     trigger=shorts_trigger,
    #     id="daily_shorts_1605_msk",
    #     replace_existing=True,
    #     max_instances=1,
    #     coalesce=True,
    # )

    morning_shorts_trigger = CronTrigger(hour=MORNING_SHORTS_HOUR, minute=MORNING_SHORTS_MINUTE, timezone=MOSCOW_TZ)
    scheduler.add_job(
        _morning_shorts_job_wrapper,
        trigger=morning_shorts_trigger,
        id="daily_morning_shorts_0900_msk",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Spanish Morning Shorts: frozen/disabled to conserve API tokens
    # morning_shorts_es_trigger = CronTrigger(hour=MORNING_SHORTS_ES_HOUR, minute=MORNING_SHORTS_ES_MINUTE, timezone=MOSCOW_TZ)
    # scheduler.add_job(
    #     _morning_shorts_es_job_wrapper,
    #     trigger=morning_shorts_es_trigger,
    #     id="daily_morning_shorts_es_0930_msk",
    #     replace_existing=True,
    #     max_instances=1,
    #     coalesce=True,
    # )

    # Spanish Telegram Post: frozen/disabled to conserve API tokens
    # spanish_post_trigger = CronTrigger(hour=SPANISH_POST_HOUR, minute=SPANISH_POST_MINUTE, timezone=MOSCOW_TZ)
    # scheduler.add_job(
    #     _post_es_job_wrapper,
    #     trigger=spanish_post_trigger,
    #     id="daily_post_es_1610_msk",
    #     replace_existing=True,
    #     max_instances=1,
    #     coalesce=True,
    # )

    # Spanish Afternoon YouTube Shorts: disabled as requested to focus on high-quality morning Shorts
    # spanish_shorts_trigger = CronTrigger(hour=SPANISH_SHORTS_HOUR, minute=SPANISH_SHORTS_MINUTE, timezone=MOSCOW_TZ)
    # scheduler.add_job(
    #     _shorts_es_job_wrapper,
    #     trigger=spanish_shorts_trigger,
    #     id="daily_shorts_es_1615_msk",
    #     replace_existing=True,
    #     max_instances=1,
    #     coalesce=True,
    # )

    cleanup_trigger = CronTrigger(hour=4, minute=0, timezone=MOSCOW_TZ)
    scheduler.add_job(
        _cleanup_runs_job,
        trigger=cleanup_trigger,
        id="daily_runs_cleanup_0400_msk",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _youtube_diplomat_job_wrapper,
        trigger=IntervalTrigger(minutes=20, timezone=MOSCOW_TZ),
        id="youtube_diplomat_every_20m",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()

    logger.info("🚀 Content Factory daemon started with YouTube Shorts module.")
    logger.info("🕒 Schedule:")
    logger.info(f"   - Telegram/VK/Dzen Post: every day at {POST_HOUR:02d}:{POST_MINUTE:02d} Europe/Moscow.")
    logger.info(f"   - Autonomous Morning YouTube Shorts Video: every day at {MORNING_SHORTS_HOUR:02d}:{MORNING_SHORTS_MINUTE:02d} Europe/Moscow.")
    logger.info(f"   - Autonomous Spanish Morning Shorts: every day at {MORNING_SHORTS_ES_HOUR:02d}:{MORNING_SHORTS_ES_MINUTE:02d} Europe/Moscow.")
    logger.info(f"   - Spanish Telegram Post: every day at {SPANISH_POST_HOUR:02d}:{SPANISH_POST_MINUTE:02d} Europe/Moscow.")
    logger.info("   - Runs cleanup: every day at 04:00 Europe/Moscow (retention 14d).")
    logger.info("   - YouTube Diplomat (comment replies): every 20 minutes.")
    logger.info(f"➡️ Next post run (approx): {_next_run_preview(POST_HOUR, POST_MINUTE)}")
    logger.info(f"➡️ Next morning shorts run (approx): {_next_run_preview(MORNING_SHORTS_HOUR, MORNING_SHORTS_MINUTE)}")
    logger.info(f"➡️ Next Spanish morning shorts run (approx): {_next_run_preview(MORNING_SHORTS_ES_HOUR, MORNING_SHORTS_ES_MINUTE)}")
    logger.info(f"➡️ Next Spanish post run (approx): {_next_run_preview(SPANISH_POST_HOUR, SPANISH_POST_MINUTE)}")

    if args.run_now:
        # fire and forget, keep scheduler alive
        asyncio.create_task(_job_wrapper())

    # Keep running forever
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())

