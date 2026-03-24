from datetime import datetime, timezone

from newstrader.audit import JsonlAuditLogger
from newstrader.dedup import ExactDedupCache
from newstrader.executor import DryRunExecutor
from newstrader.models import HeadlineEvent
from newstrader.pipeline import NewsTradingPipeline
from newstrader.risk import RiskEngine
from newstrader.signal import RuleBasedXAUUSDPolicy


def build_pipeline(tmp_path):
    return NewsTradingPipeline(
        dedup=ExactDedupCache(ttl_minutes=120),
        policy=RuleBasedXAUUSDPolicy(),
        risk=RiskEngine(max_open_positions=1, cooldown_minutes=0, max_spread_points=45),
        executor=DryRunExecutor(),
        audit=JsonlAuditLogger(str(tmp_path / "audit.jsonl")),
    )


def test_duplicate_headline_dropped(tmp_path):
    p = build_pipeline(tmp_path)
    ev = HeadlineEvent(
        source="test",
        headline="Fed surprise dovish pivot signals potential cuts",
        timestamp_source=datetime.now(timezone.utc),
    )

    first = p.process(ev, open_positions=0, spread_points=10)
    second = p.process(ev, open_positions=0, spread_points=10)

    assert first["status"] in {"sent", "blocked", "no_trade"}
    assert second["status"] == "dropped"
    assert second["reason"] == "exact_duplicate"


def test_hawkish_event_generates_sell_or_block(tmp_path):
    p = build_pipeline(tmp_path)
    ev = HeadlineEvent(
        source="test",
        headline="Hawkish FOMC surprise pushes strong yields higher",
        timestamp_source=datetime.now(timezone.utc),
    )

    result = p.process(ev, open_positions=0, spread_points=10)

    assert result["status"] in {"sent", "blocked"}
    if result["status"] == "sent":
        assert result["signal"]["side"] == "SELL"
