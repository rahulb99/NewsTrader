from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
import hashlib
import uuid

Impact = Literal["low", "medium", "high"]
Side = Literal["BUY", "SELL"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class HeadlineEvent:
    source: str
    headline: str
    timestamp_source: datetime
    timestamp_ingested: datetime = field(default_factory=utc_now)
    source_msg_id: str | None = None
    url: str | None = None
    raw_payload: dict | None = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def headline_clean(self) -> str:
        return " ".join(self.headline.lower().split())

    @property
    def headline_hash(self) -> str:
        return hashlib.sha256(self.headline_clean.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class TradeSignal:
    instrument: str
    side: Side
    size: float
    take_profit_pips: int
    stop_loss_pips: int
    news_impact: Impact
    confidence: float
    reason: str
    created_at: datetime = field(default_factory=utc_now)
