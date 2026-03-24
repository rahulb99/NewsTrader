from __future__ import annotations

import asyncio
from pprint import pprint

from .audit import JsonlAuditLogger
from .config import LLMConfig
from .dedup import ExactDedupCache
from .executor import DryRunExecutor
from .ingestion import AsyncStaticListConnector, StaticListConnector
from .llm_policy import OpenAILLMPolicy
from .pipeline import NewsTradingPipeline
from .risk import RiskEngine
from .service import ProductionRunner
from .signal import RuleBasedXAUUSDPolicy, SignalPolicy


SAMPLE_HEADLINES = [
    "Fed surprise dovish pivot signals potential cuts this year",
    "Geopolitical escalation raises safe-haven demand",
    "Fed surprise dovish pivot signals potential cuts this year",  # duplicate
    "Officials comment market is stable",
    "Hawkish FOMC tone pushes strong yields higher",
]


def _build_pipeline() -> NewsTradingPipeline:
    llm_config = LLMConfig.from_env()
    policy: SignalPolicy = RuleBasedXAUUSDPolicy()
    if llm_config.enabled:
        if not llm_config.api_key:
            raise ValueError("OPENAI_API_KEY is required when NEWSTRADER_SIGNAL_POLICY=llm")
        policy = OpenAILLMPolicy(
            api_key=llm_config.api_key,
            model=llm_config.model,
            temperature=llm_config.temperature,
        )

    return NewsTradingPipeline(
        dedup=ExactDedupCache(ttl_minutes=120),
        policy=policy,
        risk=RiskEngine(max_open_positions=1, cooldown_minutes=10, max_spread_points=45),
        executor=DryRunExecutor(),
        audit=JsonlAuditLogger("audit.jsonl"),
    )


def main() -> None:
    connector = StaticListConnector(name="demo", headlines=SAMPLE_HEADLINES)
    pipeline = _build_pipeline()

    results = pipeline.consume(connector.stream(), open_positions=0, spread_points=20)
    for result in results:
        pprint(result)


async def main_async() -> None:
    pipeline = _build_pipeline()
    connector = AsyncStaticListConnector(name="demo-async", headlines=SAMPLE_HEADLINES, delay_ms=1)
    runner = ProductionRunner(pipeline=pipeline, connectors=[connector], queue_size=128)
    stats = await runner.run(open_positions=0, spread_points=20)
    pprint({"runner_stats": stats})


if __name__ == "__main__":
    main()
    asyncio.run(main_async())
