import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client, WorkflowExecutionStatus, WorkflowFailureError
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError
from temporalio.service import RPCError

from genesis.core.config import settings
from genesis.core.net import host_port, tcp_ok

logger = logging.getLogger(__name__)

_client: Client | None = None
_registry: dict[str, Callable] = {}


def check() -> bool:
    host, port = host_port(settings.TEMPORAL_ADDRESS, 7233)
    return tcp_ok(host, port)


async def get_temporal_client() -> Client:
    global _client
    if _client is not None:
        return _client

    delay = 0.5
    last_err: Exception | None = None
    for attempt in range(1, 11):
        try:
            _client = await Client.connect(
                settings.TEMPORAL_ADDRESS,
                namespace=settings.TEMPORAL_NAMESPACE,
            )
            logger.info("Connected to Temporal at %s", settings.TEMPORAL_ADDRESS)
            return _client
        except Exception as exc:
            last_err = exc
            logger.warning(
                "Temporal connect %d/10 failed (%s); retrying in %.1fs",
                attempt,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5.0)

    raise RuntimeError(f"Could not connect to Temporal: {last_err}")


def task(fn: Callable) -> Callable:
    _registry[fn.__name__] = fn
    return fn


@activity.defn
async def run_registered_task(task_name: str, args: list):
    fn = _registry.get(task_name)
    if fn is None:
        raise ApplicationError(
            f"Task '{task_name}' is not registered on the worker; "
            f"define it in backend/app/tasks/{task_name}.py",
            non_retryable=True,
        )
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args)
    return await asyncio.to_thread(fn, *args)


@workflow.defn
class TaskWorkflow:
    @workflow.run
    async def run(self, task_name: str, args: list):
        return await workflow.execute_activity(
            run_registered_task,
            args=[task_name, args],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


async def run_task(fn: Callable, *args) -> str:
    if fn.__name__ not in _registry:
        raise ValueError(
            f"'{fn.__name__}' is not a @task; decorate it with @task "
            f"and put it in backend/app/tasks/{fn.__name__}.py"
        )
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    client = await get_temporal_client()
    await client.start_workflow(
        TaskWorkflow.run,
        args=[fn.__name__, list(args)],
        id=job_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        task_timeout=timedelta(seconds=30),
    )
    return job_id


async def job_status(job_id: str) -> dict:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(job_id)
    try:
        description = await handle.describe()
    except RPCError:
        return {"workflow_id": job_id, "status": "NOT_FOUND", "result": None}

    if description.status != WorkflowExecutionStatus.COMPLETED:
        return {"workflow_id": job_id, "status": description.status.name, "result": None}

    try:
        result = await handle.result()
    except WorkflowFailureError as exc:
        return {"workflow_id": job_id, "status": "FAILED", "result": str(exc)}

    return {"workflow_id": job_id, "status": "COMPLETED", "result": result}
