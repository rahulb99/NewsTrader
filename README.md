# NewsTrader MVP Skeleton

This repository contains an MVP skeleton for a low-latency headline-to-trade system focused on **XAUUSD**.

## Design goals

- Keep MT5 as an execution endpoint (outside scraping/model logic).
- Use event-driven connectors for headline ingestion.
- Deduplicate before signal generation.
- Use deterministic/rule-based logic in the hot path first.
- Keep an auditable record of all decisions.

## Implemented in this scaffold

- Canonical event and signal models.
- In-memory exact dedup cache with TTL.
- Rule-based XAUUSD signal policy.
- Risk guardrails (spread threshold, cooldown, max open positions).
- MT5 execution adapter interface and a dry-run executor.
- Pipeline orchestration and JSONL audit logger.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
newstrader-demo
```

The demo emits sample headlines and prints resulting decisions/trades (dry-run only).

## Next steps

1. Add a real source connector (Playwright).
2. Replace in-memory dedup with Redis + vector store.
3. Add a lightweight classifier.
4. Swap dry-run executor with MetaTrader5 executor.
