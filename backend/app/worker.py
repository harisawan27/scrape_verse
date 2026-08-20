"""Standalone background worker process for Web Radar.

Executes autonomous scheduler ticks, claims due Watches with SKIP LOCKED on Neon/PostgreSQL,
triggers Bright Data Scraper Studio collections, correlates snapshots, evaluates semantic alert
conditions, and executes self-healing recovery loops.

Usage:
    python -m app.worker
"""

import asyncio
import logging
import signal
import sys

from app.config import get_settings
from app.services.scheduler import AsyncSchedulerRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("webradar.worker")


async def main() -> None:
    settings = get_settings()
    logger.info(
        "Starting standalone Web Radar Worker (interval=%.1fs, db=%s)",
        settings.scheduler_poll_interval_seconds,
        "Neon/PostgreSQL" if "postgres" in settings.database_url else "SQLite",
    )

    runner = AsyncSchedulerRunner(poll_interval_seconds=settings.scheduler_poll_interval_seconds)
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Received termination signal. Shutting down worker gracefully...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)

    runner.start()
    try:
        if sys.platform == "win32":
            while not stop_event.is_set():
                await asyncio.sleep(1.0)
        else:
            await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Worker interrupted by user.")
    finally:
        await runner.stop()
        logger.info("Web Radar Worker shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
