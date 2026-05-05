"""Realtime broker — Redis pub/sub bridge to in-memory websocket subscribers.

A single global `broker` is used by routers to publish events. WebSocket
endpoints subscribe to channels and forward messages to clients.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

import redis.asyncio as redis_async
from fastapi import WebSocket

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RealtimeBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._redis: redis_async.Redis | None = None
        self._listener_task: asyncio.Task | None = None

    async def _redis_conn(self) -> redis_async.Redis:
        if self._redis is None:
            self._redis = redis_async.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def start(self) -> None:
        """Start a background task that bridges Redis pub/sub to local subscribers."""
        if self._listener_task and not self._listener_task.done():
            return
        self._listener_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
        if self._redis:
            await self._redis.close()

    async def _listen(self) -> None:
        try:
            r = await self._redis_conn()
            pubsub = r.pubsub()
            await pubsub.psubscribe("rt:*")
            async for msg in pubsub.listen():
                if msg.get("type") not in ("pmessage", "message"):
                    continue
                channel = msg["channel"].removeprefix("rt:") if isinstance(msg["channel"], str) else ""
                try:
                    payload = json.loads(msg["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                await self._fanout_local(channel, payload)
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.exception("broker.listener_error", error=str(exc))

    async def _fanout_local(self, channel: str, payload: dict[str, Any]) -> None:
        for ws in list(self._subscribers.get(channel, set())):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001
                self._subscribers[channel].discard(ws)

    async def subscribe(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            self._subscribers[channel].add(ws)

    async def unsubscribe(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            self._subscribers[channel].discard(ws)

    async def publish(self, *, channel: str, event: str, data: dict[str, Any]) -> None:
        payload = {"event": event, "channel": channel, "data": data}
        # Local fanout for in-process speed
        await self._fanout_local(channel, payload)
        # Redis fanout for multi-instance (no-op when single instance)
        try:
            r = await self._redis_conn()
            await r.publish(f"rt:{channel}", json.dumps(payload, default=str))
        except Exception as exc:  # noqa: BLE001
            logger.warning("broker.publish_redis_failed", error=str(exc))


broker = RealtimeBroker()
