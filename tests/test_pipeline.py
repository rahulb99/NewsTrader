from datetime import datetime, timezone
import os

from newstrader.audit import JsonlAuditLogger
from newstrader.config import AppConfig
from newstrader.config import PipelineConfig
from newstrader.config import RuntimeConfig
from newstrader.config import load_app_config
from newstrader.dedup import ExactDedupCache
from newstrader.executor import DryRunExecutor
from newstrader.ingestion import AsyncStaticListConnector, StaticListConnector
from newstrader.models import HeadlineEvent
from newstrader.pipeline import NewsTradingPipeline
from newstrader.risk import RiskEngine
from newstrader.service import ProductionRunner
from newstrader.signal import RuleBasedXAUUSDPolicy


def build_pipeline(tmp_path, *, allowed_domains=None):
    return NewsTradingPipeline(
        dedup=ExactDedupCache(ttl_minutes=120),
        policy=RuleBasedXAUUSDPolicy(),
        risk=RiskEngine(max_open_positions=1, cooldown_minutes=0, max_spread_points=45),
        executor=DryRunExecutor(),
        audit=JsonlAuditLogger(str(tmp_path / "audit.jsonl")),
        allowed_domains=allowed_domains,
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


def test_connector_stream_consumed_by_pipeline(tmp_path):
    p = build_pipeline(tmp_path)
    connector = StaticListConnector(
        name="demo",
        headlines=[
            "Fed surprise dovish pivot signals potential cuts",
            "Fed surprise dovish pivot signals potential cuts",
        ],
    )

    results = p.consume(connector.stream(), open_positions=0, spread_points=10)

    assert len(results) == 2
    assert results[1]["status"] == "dropped"


def test_async_runner_processes_events(tmp_path):
    import asyncio

    p = build_pipeline(tmp_path)
    connector = AsyncStaticListConnector(name="async", headlines=["dovish fed cuts"], delay_ms=0)
    runner = ProductionRunner(pipeline=p, connectors=[connector], queue_size=16)

    stats = asyncio.run(runner.run(open_positions=0, spread_points=10))

    assert stats.ingested == 1
    assert stats.processed == 1
    assert stats.dropped_on_backpressure == 0


def test_x_domain_allowed(tmp_path):
    p = build_pipeline(tmp_path, allowed_domains={"x.com"})
    ev = HeadlineEvent(
        source="x:zaborhedge",
        headline="Fed surprise dovish pivot signals potential cuts",
        timestamp_source=datetime.now(timezone.utc),
        url="https://x.com/zaborhedge/status/123456",
    )

    result = p.process(ev, open_positions=0, spread_points=10)

    assert result["status"] in {"sent", "blocked", "no_trade"}


def test_non_allowlisted_domain_dropped(tmp_path):
    p = build_pipeline(tmp_path, allowed_domains={"x.com"})
    ev = HeadlineEvent(
        source="other",
        headline="Fed surprise dovish pivot signals potential cuts",
        timestamp_source=datetime.now(timezone.utc),
        url="https://example.com/news",
    )

    result = p.process(ev, open_positions=0, spread_points=10)

    assert result["status"] == "dropped"
    assert result["reason"] == "source_domain_not_allowed"


def test_app_config_loads_domains_and_runtime(tmp_path):
    config_path = tmp_path / "newstrader.toml"
    config_path.write_text(
        """
[pipeline]
dedup_ttl_minutes = 90
max_open_positions = 2
cooldown_minutes = 5
max_spread_points = 30
allowed_domains = ["x.com", "https://www.reuters.com/world"]

[runtime]
queue_size = 250
processing_timeout_ms = 400
min_confidence = 0.7
""".strip(),
        encoding="utf-8",
    )

    app = AppConfig.from_toml(config_path)

    assert app.pipeline == PipelineConfig(
        dedup_ttl_minutes=90,
        max_open_positions=2,
        cooldown_minutes=5,
        max_spread_points=30,
        allowed_domains={"x.com", "reuters.com"},
    )
    assert app.runtime == RuntimeConfig(queue_size=250, processing_timeout_ms=400, min_confidence=0.7)


def test_load_app_config_uses_newstrader_config_env_path(tmp_path):
    config_path = tmp_path / "custom.toml"
    config_path.write_text(
        """
[pipeline]
allowed_domains = ["x.com"]
""".strip(),
        encoding="utf-8",
    )

    previous = os.environ.get("NEWSTRADER_CONFIG")
    os.environ["NEWSTRADER_CONFIG"] = str(config_path)
    try:
        app = load_app_config()
    finally:
        if previous is None:
            os.environ.pop("NEWSTRADER_CONFIG", None)
        else:
            os.environ["NEWSTRADER_CONFIG"] = previous

    assert app.pipeline.allowed_domains == {"x.com"}
