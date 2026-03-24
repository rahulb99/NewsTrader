from __future__ import annotations

from pprint import pprint

from .audit import JsonlAuditLogger
from .dedup import ExactDedupCache
from .executor import DryRunExecutor
from .ingestion import StaticListConnector
from .pipeline import NewsTradingPipeline
from .risk import RiskEngine
from .signal import RuleBasedXAUUSDPolicy


SAMPLE_HEADLINES = [
    "Fed surprise dovish pivot signals potential cuts this year",
    "Geopolitical escalation raises safe-haven demand",
    "Fed surprise dovish pivot signals potential cuts this year",  # duplicate
    "Officials comment market is stable",
    "Hawkish FOMC tone pushes strong yields higher",
]


def main() -> None:
    connector = StaticListConnector(name="demo", headlines=SAMPLE_HEADLINES)

    pipeline = NewsTradingPipeline(
        dedup=ExactDedupCache(ttl_minutes=120),
        policy=RuleBasedXAUUSDPolicy(),
        risk=RiskEngine(max_open_positions=1, cooldown_minutes=10, max_spread_points=45),
        executor=DryRunExecutor(),
        audit=JsonlAuditLogger("audit.jsonl"),
    )

    results = pipeline.consume(connector.stream(), open_positions=0, spread_points=20)
    for result in results:
        pprint(result)


if __name__ == "__main__":
    main()
