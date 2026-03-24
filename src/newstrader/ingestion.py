from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable, Iterator
from datetime import datetime, timezone

from .models import HeadlineEvent


class SourceConnector(ABC):
    """Synchronous connector contract used by tests and local demos."""

    name: str

    @abstractmethod
    def stream(self) -> Iterator[HeadlineEvent]:
        """Yield normalized `HeadlineEvent` objects."""


class AsyncSourceConnector(ABC):
    """Asynchronous connector contract for production ingestion."""

    name: str

    @abstractmethod
    async def stream(self) -> AsyncIterator[HeadlineEvent]:
        """Yield normalized `HeadlineEvent` objects as they arrive."""


class StaticListConnector(SourceConnector):
    """Demo connector that turns a static iterable into events."""

    def __init__(self, name: str, headlines: Iterable[str]):
        self.name = name
        self._headlines = headlines

    def stream(self) -> Iterator[HeadlineEvent]:
        for headline in self._headlines:
            now = datetime.now(timezone.utc)
            yield HeadlineEvent(
                source=self.name,
                headline=headline,
                timestamp_source=now,
                raw_payload={"headline": headline},
            )


class AsyncStaticListConnector(AsyncSourceConnector):
    """Async demo connector for production runner smoke-tests."""

    def __init__(self, name: str, headlines: Iterable[str], delay_ms: int = 0):
        self.name = name
        self._headlines = headlines
        self._delay_ms = delay_ms

    async def stream(self) -> AsyncIterator[HeadlineEvent]:
        for headline in self._headlines:
            if self._delay_ms:
                await asyncio.sleep(self._delay_ms / 1000)
            now = datetime.now(timezone.utc)
            yield HeadlineEvent(
                source=self.name,
                headline=headline,
                timestamp_source=now,
                raw_payload={"headline": headline},
            )


class PlaywrightConnector(AsyncSourceConnector):
    """Placeholder for production browser-based ingestion.

    Requires site-specific scripts/selectors and credentials/session material.
    """

    def __init__(self, name: str):
        self.name = name

    async def stream(self) -> AsyncIterator[HeadlineEvent]:
        raise NotImplementedError(
            "PlaywrightConnector requires provider-specific implementation and credentials."
        )
