from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict

from .audit import JsonlAuditLogger
from .dedup import ExactDedupCache
from .executor import ExecutionAdapter
from .models import HeadlineEvent
from .risk import RiskEngine
from .signal import RuleBasedXAUUSDPolicy


class NewsTradingPipeline:
    def __init__(
        self,
        dedup: ExactDedupCache,
        policy: RuleBasedXAUUSDPolicy,
        risk: RiskEngine,
        executor: ExecutionAdapter,
        audit: JsonlAuditLogger,
    ):
        self.dedup = dedup
        self.policy = policy
        self.risk = risk
        self.executor = executor
        self.audit = audit



    def consume(self, events: Iterable[HeadlineEvent], *, open_positions: int, spread_points: int) -> list[dict]:
        """Process a batch/stream chunk of already-normalized events."""
        results: list[dict] = []
        for event in events:
            results.append(self.process(event, open_positions=open_positions, spread_points=spread_points))
        return results

    def process(self, event: HeadlineEvent, *, open_positions: int, spread_points: int) -> dict:
        dedup = self.dedup.check_and_add(event)
        if not dedup.accepted:
            record = {
                "event": asdict(event),
                "status": "dropped",
                "reason": dedup.reason,
            }
            self.audit.log(record)
            return record

        decision = self.policy.evaluate(event)
        if not decision.tradeable or decision.signal is None:
            record = {
                "event": asdict(event),
                "status": "no_trade",
                "reason": decision.reason,
            }
            self.audit.log(record)
            return record

        risk = self.risk.validate(decision.signal, open_positions=open_positions, spread_points=spread_points)
        if not risk.allowed:
            record = {
                "event": asdict(event),
                "signal": asdict(decision.signal),
                "status": "blocked",
                "reason": risk.reason,
            }
            self.audit.log(record)
            return record

        result = self.executor.send(decision.signal)
        record = {
            "event": asdict(event),
            "signal": asdict(decision.signal),
            "execution": asdict(result),
            "status": "sent",
            "reason": "ok",
        }
        self.audit.log(record)
        return record
