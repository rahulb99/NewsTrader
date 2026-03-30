from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable, Iterator
from datetime import datetime, timezone

from .models import HeadlineEvent

log = logging.getLogger(__name__)


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


class XAPIConnector(AsyncSourceConnector):
    """Production connector that polls X (Twitter) API v2 for posts by tracked users.

    Uses the recent-search endpoint to fetch new posts since the last poll.
    Requires a bearer token (set via ``NEWSTRADER_X_BEARER_TOKEN`` env var).
    """

    BASE_URL = "https://api.x.com/2"

    def __init__(
        self,
        name: str,
        bearer_token: str,
        tracked_users: list[str],
        poll_interval_seconds: int = 30,
    ):
        self.name = name
        self._bearer_token = bearer_token
        self._tracked_users = tracked_users
        self._poll_interval = poll_interval_seconds
        self._since_id: str | None = None

    async def stream(self) -> AsyncIterator[HeadlineEvent]:
        import httpx

        query = " OR ".join(f"from:{user}" for user in self._tracked_users)
        headers = {"Authorization": f"Bearer {self._bearer_token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                params: dict[str, str | int] = {
                    "query": query,
                    "tweet.fields": "created_at,author_id",
                    "expansions": "author_id",
                    "user.fields": "username",
                    "max_results": 100,
                }
                if self._since_id:
                    params["since_id"] = self._since_id

                try:
                    resp = await client.get(
                        f"{self.BASE_URL}/tweets/search/recent",
                        headers=headers,
                        params=params,
                    )
                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("retry-after", "60"))
                        log.warning("X API rate-limited, backing off %ds", retry_after)
                        await asyncio.sleep(retry_after)
                        continue
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    log.error("X API request failed: %s", exc)
                    await asyncio.sleep(self._poll_interval)
                    continue

                data = resp.json()

                # Build author_id -> username map from includes
                users_map: dict[str, str] = {}
                for user in data.get("includes", {}).get("users", []):
                    users_map[user["id"]] = user["username"]

                tweets = data.get("data", [])
                # Yield oldest-first for chronological order
                for tweet in reversed(tweets):
                    author = users_map.get(tweet.get("author_id", ""), "unknown")
                    created_at = datetime.fromisoformat(
                        tweet["created_at"].replace("Z", "+00:00")
                    )
                    yield HeadlineEvent(
                        source=f"x:{author}",
                        headline=tweet["text"],
                        timestamp_source=created_at,
                        source_msg_id=tweet["id"],
                        url=f"https://x.com/{author}/status/{tweet['id']}",
                        raw_payload=tweet,
                    )

                # Advance the cursor so next poll only fetches new tweets
                meta = data.get("meta", {})
                if meta.get("newest_id"):
                    self._since_id = meta["newest_id"]

                await asyncio.sleep(self._poll_interval)
