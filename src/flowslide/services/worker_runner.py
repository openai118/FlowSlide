"""Utility to run generation worker from command line or programmatically.

Usage: import and call `asyncio.run(main())` or run with `python -m src.flowslide.services.worker_runner`.
"""

import asyncio
import logging
import os
from typing import Callable

from .generation_worker import run_worker
from ..database.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def session_factory():
    """Return a new AsyncSession instance."""
    return AsyncSessionLocal()


async def main(poll_interval: float = None):
    # read config from env
    pi = float(poll_interval or os.getenv("WORKER_POLL_INTERVAL", "2.0"))
    base_backoff = int(os.getenv("WORKER_BASE_BACKOFF", "60"))
    max_attempts = int(os.getenv("WORKER_MAX_ATTEMPTS", "5"))
    concurrency = int(os.getenv("WORKER_CONCURRENCY", "2"))

    logger.info(f"Starting generation worker with poll_interval={pi}, base_backoff={base_backoff}, max_attempts={max_attempts}, concurrency={concurrency}")
    await run_worker(
        session_factory,
        poll_interval=pi,
        base_backoff=base_backoff,
        max_attempts=max_attempts,
        concurrency=concurrency,
    )


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
