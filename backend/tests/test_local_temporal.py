import pytest

from genesis.local.temporal import (
    connection_params,
    get_client,
    start_local_temporal,
    stop_local_temporal,
)


async def test_start_connect_and_stop():
    params = await start_local_temporal(port=17233, ui=False)
    try:
        assert params["TEMPORAL_NAMESPACE"] == "default"
        assert connection_params() == params

        client = get_client()
        workflows = [wf async for wf in client.list_workflows()]
        assert workflows == []
    finally:
        await stop_local_temporal()

    with pytest.raises(RuntimeError):
        connection_params()
