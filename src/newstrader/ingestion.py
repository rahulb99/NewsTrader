from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone

from .models import HeadlineEvent


class SourceConnector(ABC):
    """Base connector contract.

    A real implementation should keep a persistent browser session (or websocket
    client) and emit only *new* headline payloads as they appear.
    """

    name: str

    @abstractmethod
    def stream(self) -> Iterator[HeadlineEvent]:
        """Yield normalized `HeadlineEvent` objects."""


class StaticListConnector(SourceConnector):
    """Demo connector that turns a static iterable into events.

    This is useful for tests/dev and mirrors the interface that a real
    Playwright/websocket connector would provide.
    """

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
