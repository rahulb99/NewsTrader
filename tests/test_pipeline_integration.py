import json
from dataclasses import dataclass
from datetime import datetime, timezone

from newstrader.audit import JsonlAuditLogger
from newstrader.dedup import ExactDedupCache
from newstrader.executor import ExecutionResult
from newstrader.models import HeadlineEvent, TradeSignal
from newstrader.pipeline import NewsTradingPipeline
from newstrader.risk import RiskEngine
from newstrader.signal import Decision


@dataclass(slots=True)
class _FixedDecisionPolicy:
    decision: Decision

    def evaluate(self, event: HeadlineEvent) -> Decision:
        return self.decision


class _RejectingExecutor:
    def send(self, signal: TradeSignal) -> ExecutionResult:
        return ExecutionResult(
            accepted=False,
            ticket=None,
            retcode="BROKER_REJECT",
            sent_at=datetime.now(timezone.utc),
        )


class _FailingExecutor:
    def send(self, signal: TradeSignal) -> ExecutionResult:
        raise RuntimeError("network_down")


def _build_event() -> HeadlineEvent:
    return HeadlineEvent(
        source="integration",
        headline="Fed surprise dovish shift",
        timestamp_source=datetime.now(timezone.utc),
    )


def _build_signal() -> TradeSignal:
    return TradeSignal(
        instrument="XAUUSD",
        side="BUY",
        size=0.2,
        take_profit_pips=250,
        stop_loss_pips=100,
        news_impact="high",
        confidence=0.9,
        reason="test_signal",
    )


def test_pipeline_marks_rejected_and_writes_audit_record(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    pipeline = NewsTradingPipeline(
        dedup=ExactDedupCache(ttl_minutes=120),
        policy=_FixedDecisionPolicy(Decision(tradeable=True, reason="ok", signal=_build_signal())),
        risk=RiskEngine(max_open_positions=1, cooldown_minutes=0, max_spread_points=50),
        executor=_RejectingExecutor(),
        audit=JsonlAuditLogger(str(audit_path)),
    )

    result = pipeline.process(_build_event(), open_positions=0, spread_points=10)

    assert result["status"] == "rejected"
    assert result["reason"] == "BROKER_REJECT"

    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["status"] == "rejected"
    assert records[0]["execution"]["retcode"] == "BROKER_REJECT"


def test_pipeline_marks_failed_when_executor_raises(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    pipeline = NewsTradingPipeline(
        dedup=ExactDedupCache(ttl_minutes=120),
        policy=_FixedDecisionPolicy(Decision(tradeable=True, reason="ok", signal=_build_signal())),
        risk=RiskEngine(max_open_positions=1, cooldown_minutes=0, max_spread_points=50),
        executor=_FailingExecutor(),
        audit=JsonlAuditLogger(str(audit_path)),
    )

    result = pipeline.process(_build_event(), open_positions=0, spread_points=10)

    assert result["status"] == "failed"
    assert result["reason"] == "network_down"

    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["status"] == "failed"
    assert records[0]["reason"] == "network_down"
