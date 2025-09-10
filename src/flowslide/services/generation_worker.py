"""Simple generation worker that polls `generation_tasks` and executes jobs."""

import asyncio
import logging
import time
from typing import Any

from ..database.repositories import GenerationTaskRepository
from ..services.service_instances import get_ppt_service

logger = logging.getLogger(__name__)


async def _process_task(session, task_row: dict, base_backoff: int = 60, max_attempts: int = 5):
    """Process a single task dict fetched from repository."""
    try:
        task_repo = GenerationTaskRepository(session)
        task_id = task_row.get("task_id")
        task_type = task_row.get("task_type")
        payload = task_row.get("payload") or {}
        project_id = task_row.get("project_id")

        logger.info(f"Worker attempting to claim task {task_id} type={task_type} project={project_id}")

        # Try to claim the task (atomic). If claim fails, another worker took it.
        claimed = await task_repo.claim_task(task_id)
        if not claimed:
            logger.info(f"Task {task_id} was already claimed by another worker")
            return

        try:
            # Execute the task based on type
            ppt_service = get_ppt_service()
            # Support multiple task types that can trigger project workflow execution
            if task_type in ("ppt_generation", "outline_generation", "file_outline_generation"):
                # payload may include stage to run (for partial runs) or a request
                stage = payload.get("stage") if isinstance(payload, dict) else None
                if stage:
                    # mark the stage pending and start from that stage
                    await ppt_service.start_workflow_from_stage(project_id, stage)
                    # run the workflow from that stage immediately
                    await ppt_service._execute_project_workflow(project_id, payload.get("request") if isinstance(payload, dict) else None)
                else:
                    # default: run full project workflow (outline/file outline handling is inside the service)
                    await ppt_service._execute_project_workflow(project_id, payload.get("request") if isinstance(payload, dict) else None)

            # mark success
            await task_repo.mark_success(task_id)

        except Exception as e:
            logger.exception(f"Task {task_id} failed during execution: {e}")
            # mark failed and schedule retry with backoff (or dead-letter if exceeded)
            await task_repo.mark_failed_with_backoff(task_id, str(e), base_backoff=base_backoff, max_attempts=max_attempts)
    except Exception as outer_e:
        # Catch any unexpected error in claim/processing and ensure task is retried or moved to DLQ
        logger.exception(f"Unexpected error processing task {task_row.get('task_id')}: {outer_e}")
        try:
            await task_repo.mark_failed_with_backoff(task_row.get('task_id'), str(outer_e))
        except Exception:
            # If marking failed also fails, just log
            logger.exception("Failed to mark task failed after unexpected error")


async def run_worker(session_factory, poll_interval: float = 2.0, base_backoff: int = 60, max_attempts: int = 5, concurrency: int = 2):
    """Run worker loop. session_factory should be a callable that returns an AsyncSession instance."""
    logger.info("Generation worker started")
    while True:
        try:
            session = await session_factory()
            task_repo = GenerationTaskRepository(session)
            pending = await task_repo.get_pending(limit=5)
            if not pending:
                await session.close()
                await asyncio.sleep(poll_interval)
                continue

            # Limit concurrency using a semaphore
            semaphore = asyncio.Semaphore(concurrency)
            async def _run_one(task_row):
                await semaphore.acquire()
                try:
                    proc_session = await session_factory()
                    try:
                        await _process_task(proc_session, task_row, base_backoff=base_backoff, max_attempts=max_attempts)
                    finally:
                        await proc_session.close()
                finally:
                    semaphore.release()

            tasks = [asyncio.create_task(_run_one(task_row)) for task_row in pending]
            # Wait for this batch to finish before fetching more
            if tasks:
                await asyncio.gather(*tasks)

            await session.close()
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(poll_interval)
