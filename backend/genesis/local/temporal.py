import logging

from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment

logger = logging.getLogger(__name__)

_environment: WorkflowEnvironment | None = None


async def start_local_temporal(
    namespace: str = "default",
    ip: str = "127.0.0.1",
    port: int = 7233,
    ui: bool = True,
    ui_port: int = 8233,
) -> dict:
    global _environment
    if _environment is not None:
        raise RuntimeError("Local Temporal dev server is already running")

    _environment = await WorkflowEnvironment.start_local(
        namespace=namespace, ip=ip, port=port, ui=ui, ui_port=ui_port
    )
    params = connection_params()
    logger.info("Local Temporal dev server started at %s", params["TEMPORAL_ADDRESS"])
    if ui:
        logger.info("Temporal UI available at http://%s:%s", ip, ui_port)
    return params


def connection_params() -> dict:
    if _environment is None:
        raise RuntimeError("Local Temporal dev server is not running")
    return {
        "TEMPORAL_ADDRESS": _environment.client.service_client.config.target_host,
        "TEMPORAL_NAMESPACE": _environment.client.namespace,
    }


def get_client() -> Client:
    if _environment is None:
        raise RuntimeError("Local Temporal dev server is not running")
    return _environment.client


async def stop_local_temporal() -> None:
    global _environment
    if _environment is None:
        return
    await _environment.shutdown()
    _environment = None
