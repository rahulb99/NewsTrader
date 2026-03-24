from datetime import datetime, timedelta, timezone

from newstrader.models import HeadlineEvent
from newstrader.risk import RiskEngine
from newstrader.signal import RuleBasedXAUUSDPolicy


def _event(headline: str) -> HeadlineEvent:
    return HeadlineEvent(
        source="unit",
        headline=headline,
        timestamp_source=datetime.now(timezone.utc),
    )


def test_rule_policy_returns_no_trade_when_no_tokens_match():
    policy = RuleBasedXAUUSDPolicy()

    decision = policy.evaluate(_event("Commodities opened mixed in quiet session"))

    assert decision.tradeable is False
    assert decision.reason == "no_clear_transmission_path"
    assert decision.signal is None


def test_rule_policy_returns_ambiguous_when_buy_sell_hits_are_equal():
    policy = RuleBasedXAUUSDPolicy()

    decision = policy.evaluate(_event("Fed dovish hike surprise creates mixed signal"))

    assert decision.tradeable is False
    assert decision.reason == "ambiguous_direction"
    assert decision.signal is None


def test_risk_engine_blocks_on_cooldown_then_allows_after_window():
    # Use a minimal non-None dummy signal so this test only exercises RiskEngine behavior
    signal = object()

    engine = RiskEngine(max_open_positions=1, cooldown_minutes=10, max_spread_points=50)
    now = datetime.now(timezone.utc)

    engine.record_trade(executed_at=now)
    blocked = engine.validate(signal, open_positions=0, spread_points=10)
    assert blocked.allowed is False
    assert blocked.reason == "cooldown_active"

    engine.record_trade(executed_at=now - timedelta(minutes=11))
    allowed = engine.validate(signal, open_positions=0, spread_points=10)
    assert allowed.allowed is True
    assert allowed.reason == "passed"
