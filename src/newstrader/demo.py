from __future__ import annotations

import asyncio
from pprint import pprint

from .audit import JsonlAuditLogger
from .config import load_app_config
from .dedup import ExactDedupCache
from .executor import DryRunExecutor
from .ingestion import AsyncStaticListConnector, StaticListConnector
from .pipeline import NewsTradingPipeline
from .risk import RiskEngine
from .service import ProductionRunner
from .signal import RuleBasedXAUUSDPolicy


SAMPLE_HEADLINES = [
    "Fed surprise dovish pivot signals potential cuts this year",
    "Geopolitical escalation raises safe-haven demand",
    "Fed surprise dovish pivot signals potential cuts this year",  # duplicate
    "Officials comment market is stable",
    "Hawkish FOMC tone pushes strong yields higher",
]


def _build_pipeline() -> NewsTradingPipeline:
    app_config = load_app_config()
    return NewsTradingPipeline(
        dedup=ExactDedupCache(ttl_minutes=app_config.pipeline.dedup_ttl_minutes),
        policy=RuleBasedXAUUSDPolicy(),
        risk=RiskEngine(
            max_open_positions=app_config.pipeline.max_open_positions,
            cooldown_minutes=app_config.pipeline.cooldown_minutes,
            max_spread_points=app_config.pipeline.max_spread_points,
        ),
        executor=DryRunExecutor(),
        audit=JsonlAuditLogger("audit.jsonl"),
        allowed_domains=app_config.pipeline.allowed_domains,
    )


def main() -> None:
    connector = StaticListConnector(name="demo", headlines=SAMPLE_HEADLINES)
    pipeline = _build_pipeline()
    app_config = load_app_config()

    results = pipeline.consume(
        connector.stream(),
        open_positions=0,
        spread_points=app_config.pipeline.max_spread_points,
    )
    for result in results:
        pprint(result)


async def main_async() -> None:
    app_config = load_app_config()
    pipeline = _build_pipeline()
    connector = AsyncStaticListConnector(name="demo-async", headlines=SAMPLE_HEADLINES, delay_ms=1)
    runner = ProductionRunner(
        pipeline=pipeline,
        connectors=[connector],
        queue_size=app_config.runtime.queue_size,
    )
    stats = await runner.run(open_positions=0, spread_points=app_config.pipeline.max_spread_points)
    pprint({"runner_stats": stats})


if __name__ == "__main__":
    main()
    asyncio.run(main_async())
