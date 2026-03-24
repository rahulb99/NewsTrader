"""NewsTrader package."""

from .ingestion import SourceConnector
from .models import HeadlineEvent, TradeSignal

__all__ = ["SourceConnector", "HeadlineEvent", "TradeSignal"]
