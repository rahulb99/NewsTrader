from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from .ingestion import AsyncSourceConnector
from .models import HeadlineEvent
from .pipeline import NewsTradingPipeline


@dataclass(slots=True)
class RuntimeStats:
    ingested: int = 0
    processed: int = 0
    dropped_on_backpressure: int = 0


class ProductionRunner:
    """Bounded-queue async runner for production-style ingestion.

    Connector tasks push normalized events into a queue. A single consumer keeps
    decisioning/execution ordered and deterministic.
    """

    def __init__(self, pipeline: NewsTradingPipeline, connectors: Iterable[AsyncSourceConnector], queue_size: int = 1000):
        self.pipeline = pipeline
        self.connectors = list(connectors)
        self.queue: asyncio.Queue[HeadlineEvent] = asyncio.Queue(maxsize=queue_size)
        self.stats = RuntimeStats()
        self._shutdown = asyncio.Event()

    async def _produce(self, connector: AsyncSourceConnector) -> None:
        async for event in connector.stream():
            if self._shutdown.is_set():
                break
            try:
                self.queue.put_nowait(event)
                self.stats.ingested += 1
            except asyncio.QueueFull:
                self.stats.dropped_on_backpressure += 1

    async def _consume(self, *, open_positions: int, spread_points: int) -> None:
        while not self._shutdown.is_set() or not self.queue.empty():
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            self.pipeline.process(event, open_positions=open_positions, spread_points=spread_points)
            self.stats.processed += 1
            self.queue.task_done()

    async def run(self, *, open_positions: int, spread_points: int, run_for_seconds: int | None = None) -> RuntimeStats:
        producer_tasks = [asyncio.create_task(self._produce(connector)) for connector in self.connectors]
        consumer_task = asyncio.create_task(self._consume(open_positions=open_positions, spread_points=spread_points))

        if run_for_seconds is not None:
            await asyncio.sleep(run_for_seconds)
            self._shutdown.set()

        await asyncio.gather(*producer_tasks, return_exceptions=False)
        self._shutdown.set()
        await consumer_task
        return self.stats


def make_ingest_timestamp() -> datetime:
    return datetime.now(timezone.utc)
