from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import TradeSignal


@dataclass(slots=True)
class ExecutionResult:
    accepted: bool
    ticket: int | None
    retcode: str
    sent_at: datetime


class ExecutionAdapter:
    def send(self, signal: TradeSignal) -> ExecutionResult:  # pragma: no cover - interface only
        raise NotImplementedError


class DryRunExecutor(ExecutionAdapter):
    def __init__(self):
        self._ticket = 100000

    def send(self, signal: TradeSignal) -> ExecutionResult:
        self._ticket += 1
        return ExecutionResult(
            accepted=True,
            ticket=self._ticket,
            retcode="DRY_RUN_OK",
            sent_at=datetime.now(timezone.utc),
        )
