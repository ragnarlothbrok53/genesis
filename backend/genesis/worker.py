import asyncio
import logging
from datetime import timedelta

from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from genesis.core.config import settings
from genesis.loader import load_tasks
from genesis.services.jobs import TaskWorkflow, get_temporal_client, run_registered_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    tasks = load_tasks()
    logger.info("Worker loaded %d task module(s)", len(tasks))
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[TaskWorkflow],
        activities=[run_registered_task],
        workflow_runner=UnsandboxedWorkflowRunner(),
        graceful_shutdown_timeout=timedelta(seconds=20),
        max_cached_workflows=0,
        max_concurrent_workflow_tasks=5,
        max_concurrent_activities=5,
        max_concurrent_workflow_task_polls=2,
        max_concurrent_activity_task_polls=2,
    )
    logger.info("Worker listening on task queue '%s'", settings.TEMPORAL_TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
