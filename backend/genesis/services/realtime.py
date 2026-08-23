import asyncio
import json
import logging
from collections.abc import AsyncIterator

import redis.asyncio as redis

from genesis.core.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_local_subscribers: dict[str, list[asyncio.Queue]] = {}
_local_lock = asyncio.Lock()


def _embedded() -> bool:
    return settings.CACHE_BACKEND == "embedded"


def _redis_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.VALKEY_URL, decode_responses=True)
    return _client


async def _publish_local(channel: str, payload: str) -> None:
    async with _local_lock:
        queues = list(_local_subscribers.get(channel, []))
    for queue in queues:
        await queue.put(payload)


async def _subscribe_local(channel: str) -> AsyncIterator[dict]:
    queue: asyncio.Queue = asyncio.Queue()
    async with _local_lock:
        _local_subscribers.setdefault(channel, []).append(queue)
    try:
        while True:
            payload = await queue.get()
            yield json.loads(payload)
    finally:
        async with _local_lock:
            _local_subscribers[channel].remove(queue)
            if not _local_subscribers[channel]:
                del _local_subscribers[channel]


async def _subscribe_redis(channel: str) -> AsyncIterator[dict]:
    pubsub = _redis_client().pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            yield json.loads(message["data"])
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


async def publish(channel: str, message: dict) -> None:
    payload = json.dumps(message)
    if _embedded():
        await _publish_local(channel, payload)
        return
    await _redis_client().publish(channel, payload)


def subscribe(channel: str) -> AsyncIterator[dict]:
    if _embedded():
        return _subscribe_local(channel)
    return _subscribe_redis(channel)
