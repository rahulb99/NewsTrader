from datetime import datetime, timezone

from newstrader.llm_policy import OpenAILLMPolicy
from newstrader.models import HeadlineEvent


class _FakeResponses:
    def __init__(self, payload: str):
        self.payload = payload

    def create(self, **kwargs):
        class Resp:
            output_text = ""
            output = []

            def __init__(self, payload):
                self.output_text = payload

        return Resp(self.payload)


class _FakeClient:
    def __init__(self, payload: str):
        self.responses = _FakeResponses(payload)


def test_llm_policy_tradeable_payload_maps_to_signal():
    policy = OpenAILLMPolicy(
        api_key="test",
        client=_FakeClient(
            '{"tradeable": true, "reason": "macro_gold_bullish", "side": "BUY", '
            '"news_impact": "high", "confidence": 0.82, "size": 0.2, '
            '"take_profit_pips": 250, "stop_loss_pips": 100}'
        ),
    )

    event = HeadlineEvent(
        source="unit",
        headline="Fed surprise dovish shift",
        timestamp_source=datetime.now(timezone.utc),
    )

    decision = policy.evaluate(event)

    assert decision.tradeable is True
    assert decision.signal is not None
    assert decision.signal.side == "BUY"
    assert decision.signal.news_impact == "high"


def test_llm_policy_no_trade_payload_maps_to_no_trade():
    policy = OpenAILLMPolicy(
        api_key="test",
        client=_FakeClient(
            '{"tradeable": false, "reason": "ambiguous_direction", "side": null, '
            '"news_impact": null, "confidence": 0.31, "size": null, '
            '"take_profit_pips": null, "stop_loss_pips": null}'
        ),
    )

    event = HeadlineEvent(
        source="unit",
        headline="Officials comment market is stable",
        timestamp_source=datetime.now(timezone.utc),
    )

    decision = policy.evaluate(event)

    assert decision.tradeable is False
    assert decision.signal is None
    assert decision.reason == "ambiguous_direction"


def test_llm_policy_invalid_json_returns_parse_error():
    policy = OpenAILLMPolicy(
        api_key="test",
        client=_FakeClient("not valid json {{{"),
    )

    event = HeadlineEvent(
        source="unit",
        headline="Some headline",
        timestamp_source=datetime.now(timezone.utc),
    )

    decision = policy.evaluate(event)

    assert decision.tradeable is False
    assert decision.signal is None
    assert decision.reason == "llm_parse_error"


def test_llm_policy_missing_fields_returns_invalid_payload():
    # tradeable=true but required fields are missing
    policy = OpenAILLMPolicy(
        api_key="test",
        client=_FakeClient('{"tradeable": true, "reason": "bullish", "confidence": 0.9}'),
    )

    event = HeadlineEvent(
        source="unit",
        headline="Gold surges on Fed pivot",
        timestamp_source=datetime.now(timezone.utc),
    )

    decision = policy.evaluate(event)

    assert decision.tradeable is False
    assert decision.signal is None
    assert decision.reason == "llm_invalid_payload"


def test_llm_policy_null_fields_when_tradeable_returns_invalid_payload():
    # tradeable=true but required fields are null (TypeError on float(None))
    policy = OpenAILLMPolicy(
        api_key="test",
        client=_FakeClient(
            '{"tradeable": true, "reason": "bullish", "side": "BUY", '
            '"news_impact": "high", "confidence": 0.85, "size": null, '
            '"take_profit_pips": null, "stop_loss_pips": null}'
        ),
    )

    event = HeadlineEvent(
        source="unit",
        headline="Gold surges on Fed pivot",
        timestamp_source=datetime.now(timezone.utc),
    )

    decision = policy.evaluate(event)

    assert decision.tradeable is False
    assert decision.signal is None
    assert decision.reason == "llm_invalid_payload"
