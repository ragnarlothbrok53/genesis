import asyncio

import pytest

from genesis.core.config import settings
from genesis.services import realtime


@pytest.fixture
def embedded_realtime(monkeypatch):
    monkeypatch.setattr(settings, "CACHE_BACKEND", "embedded")
    yield realtime


async def test_subscriber_receives_published_message(embedded_realtime):
    received = []

    async def consume():
        async for message in embedded_realtime.subscribe("orders"):
            received.append(message)
            break

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await embedded_realtime.publish("orders", {"id": 1, "status": "shipped"})
    await asyncio.wait_for(consumer, timeout=1)

    assert received == [{"id": 1, "status": "shipped"}]


async def test_publish_with_no_subscribers_is_a_no_op(embedded_realtime):
    await embedded_realtime.publish("empty-channel", {"noop": True})


async def test_subscriber_only_receives_messages_for_its_channel(embedded_realtime):
    received = []

    async def consume():
        async for message in embedded_realtime.subscribe("a"):
            received.append(message)
            break

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await embedded_realtime.publish("b", {"channel": "b"})
    await embedded_realtime.publish("a", {"channel": "a"})
    await asyncio.wait_for(consumer, timeout=1)

    assert received == [{"channel": "a"}]
