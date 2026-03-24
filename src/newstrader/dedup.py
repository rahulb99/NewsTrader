from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import HeadlineEvent


@dataclass(slots=True)
class DedupResult:
    accepted: bool
    reason: str


class ExactDedupCache:
    """In-memory exact dedup with TTL.

    Suitable for MVP/demo only. Replace with Redis in production.
    """

    def __init__(self, ttl_minutes: int = 60):
        self.ttl = timedelta(minutes=ttl_minutes)
        self._seen: dict[str, datetime] = {}

    def _prune(self, now: datetime) -> None:
        expiry = now - self.ttl
        stale = [k for k, ts in self._seen.items() if ts < expiry]
        for key in stale:
            del self._seen[key]

    def check_and_add(self, event: HeadlineEvent) -> DedupResult:
        now = datetime.now(timezone.utc)
        self._prune(now)

        if event.headline_hash in self._seen:
            return DedupResult(accepted=False, reason="exact_duplicate")

        self._seen[event.headline_hash] = now
        return DedupResult(accepted=True, reason="new")
