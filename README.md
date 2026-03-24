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

## TradingView indicator

A Pine v5 indicator that mirrors the current rule-based signal policy is available at `tradingview/newstrader_xauusd_indicator.pine`. Integration notes are documented in `docs/tradingview_integration.md`.

## LLM signal policy (OpenAI)

The pipeline now supports an OpenAI-backed LLM policy in addition to the default rule policy.

1. Create a `.env` file in the repo root:

```bash
OPENAI_API_KEY=sk-...
NEWSTRADER_SIGNAL_POLICY=llm
NEWSTRADER_OPENAI_MODEL=gpt-4.1-mini
NEWSTRADER_OPENAI_TEMPERATURE=0.0
```

2. Run the demo as usual (`newstrader-demo`). When `NEWSTRADER_SIGNAL_POLICY=llm`, the pipeline builds `OpenAILLMPolicy`; otherwise it uses `RuleBasedXAUUSDPolicy`.

### LLM prompt used

System prompt:

`You are a low-latency macro-news trading classifier for XAUUSD. Given one headline, return strict JSON only. Choose BUY, SELL, or NO_TRADE using the headline's likely immediate impact on gold. Do not include markdown or extra keys.`

User prompt template:

```
Classify this headline event.

source: {source}
headline: {headline}
source_timestamp_utc: {timestamp}

Output JSON schema:
{
  "tradeable": boolean,
  "reason": string,
  "side": "BUY" | "SELL" | null,
  "news_impact": "low" | "medium" | "high" | null,
  "confidence": number,
  "size": number | null,
  "take_profit_pips": integer | null,
  "stop_loss_pips": integer | null
}

Rules:
- If uncertain or conflicting signal, set tradeable=false and side/news_impact/size/take_profit_pips/stop_loss_pips to null.
- confidence must be between 0.0 and 1.0.
- If tradeable=true, include side, impact, size, TP, SL.
- Keep reason short snake_case.
```
