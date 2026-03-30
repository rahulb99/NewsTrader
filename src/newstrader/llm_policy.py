from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .models import HeadlineEvent, TradeSignal
from .signal import Decision

SYSTEM_PROMPT = (
    "You are a low-latency macro-news trading classifier for XAUUSD. "
    "Given one headline, return strict JSON only. "
    "Choose BUY, SELL, or NO_TRADE using the headline's likely immediate impact on gold. "
    "Do not include markdown or extra keys."
)

USER_PROMPT_TEMPLATE = """Classify this headline event.

source: {source}
headline: {headline}
source_timestamp_utc: {timestamp}

Output JSON schema:
{{
  "tradeable": boolean,
  "reason": string,
  "side": "BUY" | "SELL" | null,
  "news_impact": "low" | "medium" | "high" | null,
  "confidence": number,
  "size": number | null,
  "take_profit_pips": integer | null,
  "stop_loss_pips": integer | null
}}

Rules:
- If uncertain or conflicting signal, set tradeable=false and side/news_impact/size/take_profit_pips/stop_loss_pips to null.
- confidence must be between 0.0 and 1.0.
- If tradeable=true, include side, impact, size, TP, SL.
- Keep reason short snake_case.
"""


class LLMResponsesAPI(Protocol):
    def create(
        self,
        *,
        model: str,
        temperature: float,
        input: list[dict[str, Any]],
        response_format: dict[str, Any],
    ) -> Any:  # pragma: no cover - protocol shape only
        ...


class LLMResponseClient(Protocol):
    responses: LLMResponsesAPI  # pragma: no cover - protocol shape only


@dataclass(slots=True)
class OpenAILLMPolicy:
    api_key: str
    model: str = "gpt-4.1-mini"
    temperature: float = 0.0
    client: LLMResponseClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            from openai import OpenAI

            self.client = OpenAI(api_key=self.api_key)

    def _build_prompt(self, event: HeadlineEvent) -> str:
        return USER_PROMPT_TEMPLATE.format(
            source=event.source,
            headline=event.headline,
            timestamp=event.timestamp_source.isoformat(),
        )

    def _extract_response_text(self, response) -> str:
        if getattr(response, "output_text", None):
            return response.output_text

        chunks: list[str] = []
        for item in getattr(response, "output", []):
            for content in getattr(item, "content", []):
                text = getattr(content, "text", None)
                if text:
                    chunks.append(text)
        return "\n".join(chunks)

    def evaluate(self, event: HeadlineEvent) -> Decision:
        response = self.client.responses.create(
            model=self.model,
            temperature=self.temperature,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_prompt(event)},
            ],
            response_format={"type": "json_object"},
        )

        raw = self._extract_response_text(response)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return Decision(tradeable=False, reason="llm_invalid_json", signal=None)

        tradeable_raw = payload.get("tradeable", False)
        if isinstance(tradeable_raw, bool):
            tradeable = tradeable_raw
        elif isinstance(tradeable_raw, str):
            normalized = tradeable_raw.strip().lower()
            if normalized in ("true", "1", "yes"):
                tradeable = True
            else:
                tradeable = False
        else:
            tradeable = bool(tradeable_raw)

        reason_value = payload.get("reason", "llm_unknown")
        reason = str(reason_value) if reason_value is not None else "llm_unknown"

        if not tradeable:
            return Decision(tradeable=False, reason=reason, signal=None)

        # When tradeable is True, ensure all required fields are present and valid.
        try:
            side_raw = payload["side"]
            size_raw = payload["size"]
            tp_raw = payload["take_profit_pips"]
            sl_raw = payload["stop_loss_pips"]
            impact_raw = payload["news_impact"]
            confidence_raw = payload["confidence"]

            if (
                side_raw is None
                or size_raw is None
                or tp_raw is None
                or sl_raw is None
                or impact_raw is None
                or confidence_raw is None
            ):
                # Missing required values despite tradeable=True – no trade.
                return Decision(tradeable=False, reason="llm_missing_fields", signal=None)

            side = str(side_raw)
            news_impact = str(impact_raw)
            size = float(size_raw)
            take_profit_pips = int(tp_raw)
            stop_loss_pips = int(sl_raw)
            confidence = max(0.0, min(1.0, float(confidence_raw)))
        except (KeyError, TypeError, ValueError):
            # Any missing key or invalid type/value should result in a safe no-trade decision.
            return Decision(tradeable=False, reason="llm_invalid_fields", signal=None)

        signal = TradeSignal(
            instrument="XAUUSD",
            side=side,
            size=size,
            take_profit_pips=take_profit_pips,
            stop_loss_pips=stop_loss_pips,
            news_impact=news_impact,
            confidence=confidence,
            reason=f"llm_policy:{event.source}:{event.headline[:80]}",
        )
        return Decision(tradeable=True, reason=reason, signal=signal)
