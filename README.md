# NewsTrader MVP Skeleton

This repository now includes a **production-oriented runtime scaffold** for a low-latency headline-to-trade system focused on **XAUUSD**.

## Architecture

- **Ingestion**: connector interface (sync + async) emits normalized `HeadlineEvent` records.
- **Pipeline**: dedup → signal policy → risk checks → execution.
- **Execution**: adapter pattern (dry-run now, MT5 adapter next).
- **Auditability**: every event outcome gets persisted to JSONL.
- **Runtime**: bounded queue + backpressure metrics via async `ProductionRunner`.

## How news ingestion works

1. A source connector yields normalized events (`HeadlineEvent`).
2. Production connectors should keep persistent browser/websocket sessions and emit only new updates.
3. The `ProductionRunner` ingests from one or more async connectors into a bounded queue.
4. A deterministic consumer drains the queue and calls `NewsTradingPipeline.process()` in order.
5. Pipeline emits one of: `dropped`, `no_trade`, `blocked`, `sent`, and logs the record.

## What is production-ready now

- Connector contracts for both sync and async sources.
- Bounded queue ingestion runner with backpressure counters.
- Deterministic ordered processing path.
- Risk and dedup protections in the hot path.
- Unit tests for duplicate suppression, direction inference, and connector ingestion.

## What still needs provider integration

To implement real low-latency connectors for LiveSquawk/FinancialJuice/ForexFactory we need one of:

- Playwright/Puppeteer authenticated session details (or existing scripts/selectors).
- Any internal API/websocket endpoint details you already have.
- Credentials/token bootstrap method (if login-gated).

Once you provide that, the placeholder `PlaywrightConnector` can be replaced with production code.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
newstrader-demo
```

The demo runs both a synchronous and an asynchronous ingestion flow using static headlines.
