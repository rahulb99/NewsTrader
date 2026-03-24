from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict
from urllib.parse import urlparse

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
        allowed_domains: set[str] | None = None,
    ):
        self.dedup = dedup
        self.policy = policy
        self.risk = risk
        self.executor = executor
        self.audit = audit
        self.allowed_domains = {d.lower() for d in (allowed_domains or set())}

    def _is_domain_allowed(self, event: HeadlineEvent) -> bool:
        if not self.allowed_domains:
            return True

        if not event.url:
            return True

        parsed = urlparse(event.url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if ":" in host:
            host = host.split(":", 1)[0]
        return host in self.allowed_domains



    def consume(self, events: Iterable[HeadlineEvent], *, open_positions: int, spread_points: int) -> list[dict]:
        """Process a batch/stream chunk of already-normalized events."""
        results: list[dict] = []
        for event in events:
            results.append(self.process(event, open_positions=open_positions, spread_points=spread_points))
        return results

    def process(self, event: HeadlineEvent, *, open_positions: int, spread_points: int) -> dict:
        if not self._is_domain_allowed(event):
            record = {
                "event": asdict(event),
                "status": "dropped",
                "reason": "source_domain_not_allowed",
            }
            self.audit.log(record)
            return record

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

        try:
            result = self.executor.send(decision.signal)
        except Exception as exc:
            record = {
                "event": asdict(event),
                "signal": asdict(decision.signal),
                "status": "failed",
                "reason": str(exc),
            }
            self.audit.log(record)
            return record

        accepted = getattr(result, "accepted", True)
        if accepted:
            record = {
                "event": asdict(event),
                "signal": asdict(decision.signal),
                "execution": asdict(result),
                "status": "sent",
                "reason": "ok",
            }
        else:
            rejection_reason = getattr(result, "reason", None)
            if rejection_reason is None and hasattr(result, "retcode"):
                rejection_reason = str(getattr(result, "retcode"))
            if rejection_reason is None:
                rejection_reason = "rejected"
            record = {
                "event": asdict(event),
                "signal": asdict(decision.signal),
                "execution": asdict(result),
                "status": "rejected",
                "reason": rejection_reason,
            }
        self.audit.log(record)
        return record
