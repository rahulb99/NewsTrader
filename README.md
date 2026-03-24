# NewsTrader MVP Skeleton

NewsTrader is a **Python 3.11+ event-driven headline-to-trade pipeline** focused on **XAUUSD**.
It is designed as a production-oriented scaffold: clear interfaces, deterministic processing, and auditable outcomes.

This project is intentionally an MVP skeleton. It gives you the full runtime shape (ingestion → decisioning → execution) while leaving provider-specific integrations (live news feeds, brokerage adapters) pluggable.

## Table of contents

- [How it works](#how-it-works)
- [Core components](#core-components)
- [Data model](#data-model)
- [Decision statuses and audit log](#decision-statuses-and-audit-log)
- [Installation](#installation)
- [User guide](#user-guide)
  - [Run the demo](#run-the-demo)
  - [Run async production-style ingestion](#run-async-production-style-ingestion)
  - [Use environment configuration](#use-environment-configuration)
  - [Run tests](#run-tests)
- [Extending NewsTrader](#extending-newstrader)
- [Current limitations](#current-limitations)

## How it works

At runtime, the system processes each headline through a fixed, deterministic path:

1. **Ingestion**
   - A connector emits normalized `HeadlineEvent` objects.
   - You can use synchronous connectors (`SourceConnector`) or asynchronous connectors (`AsyncSourceConnector`).
2. **Deduplication**
   - `ExactDedupCache` suppresses repeated headlines by hash within a TTL window.
3. **Signal policy**
   - `RuleBasedXAUUSDPolicy` scans headline tokens and decides `BUY`, `SELL`, or `no_trade`.
4. **Risk gate**
   - `RiskEngine` enforces max open positions, cooldown, and spread limits.
5. **Execution**
   - `ExecutionAdapter` sends the trade signal (the default `DryRunExecutor` simulates acceptance).
6. **Audit logging**
   - Every result is appended as JSONL (`audit.jsonl` by default).

For asynchronous production-style ingestion, `ProductionRunner` fans in one or more async connectors into a bounded queue, then a single consumer processes events in order.

## Core components

- `newstrader.ingestion`
  - Connector interfaces and demo connectors (`StaticListConnector`, `AsyncStaticListConnector`, placeholder `PlaywrightConnector`).
- `newstrader.pipeline`
  - `NewsTradingPipeline` orchestration and per-event processing.
- `newstrader.signal`
  - `RuleBasedXAUUSDPolicy` keyword-based direction and impact inference.
- `newstrader.risk`
  - `RiskEngine` checks for spread, cooldown, and position limits.
- `newstrader.executor`
  - Execution abstraction with `DryRunExecutor` implementation.
- `newstrader.audit`
  - JSONL audit logger with datetime-safe serialization.
- `newstrader.service`
  - `ProductionRunner` async runtime with backpressure tracking.
- `newstrader.config`
  - Optional environment-driven config helpers.

## Data model

### `HeadlineEvent`
Normalized inbound event containing source metadata, source timestamp, optional payload, and computed hash via cleaned headline text.

### `TradeSignal`
Structured output from policy evaluation:
- `instrument` (currently `XAUUSD`)
- `side` (`BUY` / `SELL`)
- sizing and TP/SL parameters
- impact and confidence metadata

## Decision statuses and audit log

Each processed headline generates one audit record with a status:

- `dropped` — dedup rejected (e.g., `exact_duplicate`)
- `no_trade` — policy found no clear/valid trade direction
- `blocked` — risk engine denied trade
- `sent` — execution accepted
- `rejected` — execution returned not accepted
- `failed` — execution adapter raised an exception

All records are appended to JSON lines so you can stream/parse them with standard tooling.

Example:

```json
{"status":"sent","reason":"ok","event":{...},"signal":{...},"execution":{...}}
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## User guide

### Run the demo

The package includes a CLI entrypoint:

```bash
newstrader-demo
```

This runs the synchronous demo flow (`newstrader.demo:main`) using a static list of sample headlines and prints pipeline results.

### Run async production-style ingestion

`newstrader-demo` also includes an async run inside the module. If you want to run async-only manually:

```bash
python -c "import asyncio; from newstrader.demo import main_async; asyncio.run(main_async())"
```

That path uses:
- `AsyncStaticListConnector`
- `ProductionRunner` with bounded queue
- backpressure/throughput stats (`ingested`, `processed`, `dropped_on_backpressure`)

### Use environment configuration

Configuration helpers are available in `newstrader.config`.

Pipeline config environment variables:

- `NEWSTRADER_DEDUP_TTL_MINUTES` (default `120`)
- `NEWSTRADER_MAX_OPEN_POSITIONS` (default `1`)
- `NEWSTRADER_COOLDOWN_MINUTES` (default `10`)
- `NEWSTRADER_MAX_SPREAD_POINTS` (default `45`)

Runtime config environment variables:

- `NEWSTRADER_QUEUE_SIZE` (default `1000`)
- `NEWSTRADER_PROCESSING_TIMEOUT_MS` (default `250`)
- `NEWSTRADER_MIN_CONFIDENCE` (default `0.60`)

Example:

```bash
export NEWSTRADER_MAX_SPREAD_POINTS=35
export NEWSTRADER_QUEUE_SIZE=2048
newstrader-demo
```

### Run tests

```bash
pytest -q
```

## Extending NewsTrader

### 1) Implement a real connector

Subclass `AsyncSourceConnector` and emit normalized `HeadlineEvent` objects from your provider feed (browser session, websocket, or API).

### 2) Replace dry-run execution

Implement `ExecutionAdapter.send(signal)` for your broker (e.g., MT5 bridge), returning an `ExecutionResult`.

### 3) Customize decisioning/risk

- Replace or augment `RuleBasedXAUUSDPolicy` with an ML/NLP or hybrid policy.
- Extend `RiskEngine` with dynamic sizing, volatility filters, or account-aware checks.

### 4) Persist state for distributed runtime

Current dedup is in-memory; production distributed deployments should move dedup/cache state to a shared store (e.g., Redis).

## Current limitations

- Strategy is intentionally rule-based and simplistic.
- No live provider implementation is included in this repo.
- No real broker execution adapter is included (dry-run only).
- Dedup cache is in-memory only.

---

If you want, the next step can be adding a concrete `PlaywrightConnector` implementation template and a production `MT5ExecutionAdapter` contract with retry/error taxonomy.
