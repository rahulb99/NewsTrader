# CLAUDE.md

## Project overview

NewsTrader is a Python 3.11+ event-driven pipeline that ingests posts from X (Twitter) accounts, evaluates them for XAUUSD trading signals, validates against risk rules, and executes trades (dry-run by default).

## Architecture

```
X API (posts) -> XAPIConnector -> ProductionRunner (bounded queue)
                                       |
                                  NewsTradingPipeline
                                       |
                    domain filter -> dedup -> signal policy -> risk gate -> executor -> audit log
```

- **Ingestion**: `XAPIConnector` polls X API v2 recent-search for tracked users. `StaticListConnector`/`AsyncStaticListConnector` exist for tests and demos.
- **Signal policies**: `RuleBasedXAUUSDPolicy` (keyword matching) or `OpenAILLMPolicy` (LLM-based, selected via `NEWSTRADER_SIGNAL_POLICY=llm` env var).
- **Config**: Non-secret settings in `newstrader.toml`, secrets in env vars.

## Key commands

```bash
# Install
python -m venv .venv && source .venv/bin/activate && pip install -e .

# Run demo (static headlines, no API keys needed)
newstrader-demo

# Run tests
pytest -q
```

## Project structure

```
src/newstrader/
  ingestion.py    # SourceConnector, AsyncSourceConnector, XAPIConnector, static connectors
  pipeline.py     # NewsTradingPipeline (domain filter, dedup, signal, risk, execute, audit)
  signal.py       # RuleBasedXAUUSDPolicy, SignalPolicy protocol, Decision dataclass
  llm_policy.py   # OpenAILLMPolicy (structured JSON output via OpenAI Responses API)
  risk.py         # RiskEngine (position limits, cooldown, spread checks)
  executor.py     # ExecutionAdapter ABC, DryRunExecutor
  service.py      # ProductionRunner (async fan-in with backpressure)
  config.py       # PipelineConfig, RuntimeConfig, XAPIConfig, AppConfig (TOML loading)
  models.py       # HeadlineEvent, TradeSignal dataclasses
  dedup.py        # ExactDedupCache (in-memory TTL-based SHA256 dedup)
  audit.py        # JsonlAuditLogger
  demo.py         # CLI entrypoint with sample headlines
newstrader.toml   # Runtime config (pipeline, runtime, x_api sections)
```

## Environment variables

- `NEWSTRADER_X_BEARER_TOKEN` — X API v2 bearer token (required for live ingestion)
- `NEWSTRADER_CONFIG` — path to TOML config file (default: `newstrader.toml`)
- `OPENAI_API_KEY` — OpenAI API key (only when `NEWSTRADER_SIGNAL_POLICY=llm`)
- `NEWSTRADER_SIGNAL_POLICY` — `rule` (default) or `llm`

## Code conventions

- Python 3.11+, `from __future__ import annotations` in all modules
- Dataclasses with `slots=True` for models and configs
- ABC/Protocol for interfaces (`SourceConnector`, `AsyncSourceConnector`, `SignalPolicy`, `ExecutionAdapter`)
- Tests in `tests/` using pytest, no external test dependencies beyond pytest
