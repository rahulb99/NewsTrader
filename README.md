# NewsTrader

NewsTrader is a **Python 3.11+ event-driven headline-to-trade pipeline** focused on **XAUUSD**.
It ingests posts from X (Twitter) accounts, runs them through a signal policy, validates against risk rules, and executes trades (dry-run by default).

## Table of contents

- [How it works](#how-it-works)
- [Core components](#core-components)
- [Data model](#data-model)
- [Decision statuses and audit log](#decision-statuses-and-audit-log)
- [Installation](#installation)
- [User guide](#user-guide)
  - [Run the demo](#run-the-demo)
  - [X API ingestion](#x-api-ingestion)
  - [LLM signal policy](#llm-signal-policy-openai)
  - [TOML configuration](#use-toml-configuration)
  - [TradingView indicator](#tradingview-indicator)
  - [Run tests](#run-tests)
- [Extending NewsTrader](#extending-newstrader)
- [Current limitations](#current-limitations)

## How it works

At runtime, the system processes each headline through a fixed, deterministic path:

1. **Ingestion**
   - `XAPIConnector` polls the X API v2 for posts by tracked users and emits normalized `HeadlineEvent` objects.
   - Synchronous connectors (`SourceConnector`) are available for tests and demos.
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
  - Connector interfaces, demo connectors (`StaticListConnector`, `AsyncStaticListConnector`), and production `XAPIConnector` for ingesting posts from X (Twitter).
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
  - TOML-driven config helpers (environment only selects config path and provides secrets).

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

The demo runs both a synchronous and an asynchronous ingestion flow using static headlines.

### X API ingestion

For production use, `XAPIConnector` polls the X (Twitter) API v2 recent-search endpoint for posts by tracked users.

1. Add your bearer token to `.env`:

```bash
NEWSTRADER_X_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAAx...
```

2. Configure tracked accounts in `newstrader.toml`:

```toml
[x_api]
tracked_users = ["zaborhedge", "FirstSquawk", "DeItaone"]
poll_interval_seconds = 30
```

3. Wire `XAPIConnector` into `ProductionRunner`:

```python
from newstrader.ingestion import XAPIConnector
from newstrader.service import ProductionRunner

connector = XAPIConnector(
    name="x-feed",
    bearer_token=os.environ["NEWSTRADER_X_BEARER_TOKEN"],
    tracked_users=app_config.x_api.tracked_users,
    poll_interval_seconds=app_config.x_api.poll_interval_seconds,
)
runner = ProductionRunner(pipeline=pipeline, connectors=[connector])
await runner.run(open_positions=0, spread_points=45)
```

The connector tracks `since_id` across polls so only new posts are fetched, and backs off automatically on rate limits (HTTP 429).

### LLM signal policy (OpenAI)

The pipeline supports an OpenAI-backed LLM policy in addition to the default rule-based policy.

1. Add to your `.env`:

```bash
OPENAI_API_KEY=sk-...
NEWSTRADER_SIGNAL_POLICY=llm
NEWSTRADER_OPENAI_MODEL=gpt-4.1-mini
NEWSTRADER_OPENAI_TEMPERATURE=0.0
```

2. Run the demo as usual (`newstrader-demo`). When `NEWSTRADER_SIGNAL_POLICY=llm`, the pipeline builds `OpenAILLMPolicy`; otherwise it uses `RuleBasedXAUUSDPolicy`.

### TradingView indicator

A Pine v5 indicator that mirrors the rule-based signal policy is available at `tradingview/newstrader_xauusd_indicator.pine`. Integration notes are in `docs/tradingview_integration.md`.

### Use TOML configuration

Configuration helpers are available in `newstrader.config`. Runtime and strategy settings now live in `newstrader.toml` (checked into source control), while environment variables should be reserved for secrets and minimal runtime wiring.

Example `newstrader.toml`:

```toml
[pipeline]
dedup_ttl_minutes = 120
max_open_positions = 1
cooldown_minutes = 10
max_spread_points = 45
allowed_domains = ["x.com"]

[runtime]
queue_size = 1000
processing_timeout_ms = 250
min_confidence = 0.60

[x_api]
tracked_users = ["zaborhedge", "FirstSquawk", "DeItaone"]
poll_interval_seconds = 30
```

The `[x_api]` section configures which X (Twitter) accounts to monitor. The bearer token is provided via the `NEWSTRADER_X_BEARER_TOKEN` environment variable.

Environment variables are reserved for secrets and minimal runtime wiring:

| Variable | Purpose |
|---|---|
| `NEWSTRADER_CONFIG` | Path to config file (default `newstrader.toml`) |
| `NEWSTRADER_X_BEARER_TOKEN` | X API v2 bearer token |
| `OPENAI_API_KEY` | OpenAI key (only when using LLM policy) |
| `NEWSTRADER_SIGNAL_POLICY` | `rule` (default) or `llm` |

### Run tests

```bash
pytest -q
```

## Extending NewsTrader

### 1) Add more source connectors

Subclass `AsyncSourceConnector` and emit `HeadlineEvent` objects from any provider (websocket feed, RSS, etc.). Wire them into `ProductionRunner` alongside `XAPIConnector`.

### 2) Replace dry-run execution

Implement `ExecutionAdapter.send(signal)` for your broker (e.g., MT5 bridge), returning an `ExecutionResult`.

### 3) Customize decisioning/risk

- Replace or augment `RuleBasedXAUUSDPolicy` with an ML/NLP or hybrid policy.
- Extend `RiskEngine` with dynamic sizing, volatility filters, or account-aware checks.

### 4) Persist state for distributed runtime

Current dedup is in-memory; production distributed deployments should move dedup/cache state to a shared store (e.g., Redis).

## Current limitations

- Strategy is intentionally rule-based and simplistic.
- X API connector requires a bearer token with recent-search access.
- No real broker execution adapter is included (dry-run only).
- Dedup cache is in-memory only.

