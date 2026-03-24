from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import HeadlineEvent, TradeSignal


BUY_TOKENS = {
    "dovish",
    "cuts",
    "cut",
    "safe-haven",
    "escalation",
    "sanctions",
    "banking stress",
    "gold buying",
}

SELL_TOKENS = {
    "hawkish",
    "hike",
    "hikes",
    "strong yields",
    "de-escalation",
    "ceasefire",
    "risk-on",
}

HIGH_IMPACT_TOKENS = {
    "fed",
    "fomc",
    "cpi",
    "nfp",
    "powell",
    "war",
    "attack",
    "intervention",
    "tariff",
    "surprise",
}


@dataclass(slots=True)
class Decision:
    tradeable: bool
    reason: str
    signal: TradeSignal | None = None


class SignalPolicy(Protocol):
    def evaluate(self, event: HeadlineEvent) -> Decision:
        ...  # pragma: no cover - interface only


class RuleBasedXAUUSDPolicy:
    def evaluate(self, event: HeadlineEvent) -> Decision:
        text = event.headline_clean

        buy_hits = sum(1 for token in BUY_TOKENS if token in text)
        sell_hits = sum(1 for token in SELL_TOKENS if token in text)
        impact_hits = sum(1 for token in HIGH_IMPACT_TOKENS if token in text)

        if buy_hits == 0 and sell_hits == 0:
            return Decision(tradeable=False, reason="no_clear_transmission_path")

        if buy_hits == sell_hits:
            return Decision(tradeable=False, reason="ambiguous_direction")

        side = "BUY" if buy_hits > sell_hits else "SELL"
        impact = "high" if impact_hits >= 1 else "medium"

        size = 0.20 if impact == "high" else 0.10
        tp = 250 if impact == "high" else 150

        confidence = min(0.95, 0.55 + 0.1 * abs(buy_hits - sell_hits) + 0.05 * impact_hits)

        signal = TradeSignal(
            instrument="XAUUSD",
            side=side,
            size=size,
            take_profit_pips=tp,
            stop_loss_pips=100,
            news_impact=impact,
            confidence=confidence,
            reason=f"rule_policy:{event.source}:{event.headline[:80]}",
        )
        return Decision(tradeable=True, reason="rule_match", signal=signal)
