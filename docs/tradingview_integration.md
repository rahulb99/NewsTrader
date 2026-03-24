# TradingView indicator integration for NewsTrader

This project generates `BUY`/`SELL` XAUUSD signals from headline text in `RuleBasedXAUUSDPolicy`.

Because TradingView Pine scripts cannot directly read your Python service stream, the practical setup is:

1. Keep NewsTrader as the source of truth for event parsing/risk/execution.
2. Recreate the same headline-token scoring logic in Pine for visualization + alerts.
3. (Optional but recommended) Push NewsTrader events into TradingView alerts/webhooks so the chart and execution stay aligned.

## How the system logic maps to TradingView

Python policy behavior (current repo):

- Buy/sell direction from token hit counts in headline text.
- `no_trade` when no directional token or equal buy/sell hits.
- Impact is `high` if at least one impact token hit, else `medium`.
- Position proxy and targets:
  - `size`: `0.20` for high impact else `0.10`
  - `take_profit_pips`: `250` for high impact else `150`
  - `stop_loss_pips`: `100`
- Confidence formula: `min(0.95, 0.55 + 0.10 * abs(buy_hits - sell_hits) + 0.05 * impact_hits)`.

The Pine script in `tradingview/newstrader_xauusd_indicator.pine` mirrors this logic for chart-side signal markers and alert conditions.

## Installation steps

1. Open TradingView chart (XAUUSD recommended).
2. Open **Pine Editor**.
3. Paste contents of `tradingview/newstrader_xauusd_indicator.pine`.
4. Click **Add to chart**.
5. In indicator inputs, set:
   - `Latest headline text`
   - `Headline source`
   - optional `Min confidence to display signal`
6. Create alerts from:
   - `NewsTrader BUY`
   - `NewsTrader SELL`

## Operational recommendations

- Use this Pine indicator primarily for **signal visualization and alerting**.
- Keep trade gating (max open positions, spread filter, cooldown) in Python risk engine, because Pine cannot safely access broker-side position/spread state equivalent to your service runtime.
- If you want true automation:
  - Let NewsTrader emit webhook payloads.
  - Use TradingView only as display/confirmation, or route alert webhooks into your order bridge.
