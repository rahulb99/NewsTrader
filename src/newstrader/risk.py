from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import TradeSignal


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    reason: str


class RiskEngine:
    def __init__(
        self,
        max_open_positions: int = 1,
        cooldown_minutes: int = 10,
        max_spread_points: int = 50,
    ):
        self.max_open_positions = max_open_positions
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self.max_spread_points = max_spread_points
        self._last_trade_at: datetime | None = None

    def validate(self, signal: TradeSignal, *, open_positions: int, spread_points: int) -> RiskDecision:
        now = datetime.now(timezone.utc)

        if open_positions >= self.max_open_positions:
            return RiskDecision(False, "max_open_positions")

        if spread_points > self.max_spread_points:
            return RiskDecision(False, "spread_too_wide")

        if self._last_trade_at and now - self._last_trade_at < self.cooldown:
            return RiskDecision(False, "cooldown_active")

        return RiskDecision(True, "passed")

    def record_trade(self, executed_at: datetime | None = None) -> None:
        """
        Record that a trade has been successfully executed.

        If ``executed_at`` is not provided, the current UTC time is used.
        """
        if executed_at is None:
            executed_at = datetime.now(timezone.utc)
        self._last_trade_at = executed_at
