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


class LLMResponseClient(Protocol):
    def responses(self):  # pragma: no cover - protocol shape only
        ...


@dataclass(slots=True)
class OpenAILLMPolicy:
    api_key: str
    model: str = "gpt-4.1-mini"
    temperature: float = 0.0
    client: Any | None = None

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
            return Decision(tradeable=False, reason="llm_parse_error", signal=None)

        tradeable = bool(payload.get("tradeable", False))
        reason = str(payload.get("reason", "llm_unknown"))

        if not tradeable:
            return Decision(tradeable=False, reason=reason, signal=None)

        try:
            signal = TradeSignal(
                instrument="XAUUSD",
                side=str(payload["side"]),
                size=float(payload["size"]),
                take_profit_pips=int(payload["take_profit_pips"]),
                stop_loss_pips=int(payload["stop_loss_pips"]),
                news_impact=str(payload["news_impact"]),
                confidence=max(0.0, min(1.0, float(payload["confidence"]))),
                reason=f"llm_policy:{event.source}:{event.headline[:80]}",
            )
        except (KeyError, TypeError, ValueError):
            return Decision(tradeable=False, reason="llm_invalid_payload", signal=None)
        return Decision(tradeable=True, reason=reason, signal=signal)
