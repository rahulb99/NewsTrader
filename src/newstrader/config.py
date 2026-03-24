from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    return int(value) if value is not None else default


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    return float(value) if value is not None else default


@dataclass(slots=True)
class PipelineConfig:
    dedup_ttl_minutes: int = 120
    max_open_positions: int = 1
    cooldown_minutes: int = 10
    max_spread_points: int = 45

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls(
            dedup_ttl_minutes=_env_int("NEWSTRADER_DEDUP_TTL_MINUTES", 120),
            max_open_positions=_env_int("NEWSTRADER_MAX_OPEN_POSITIONS", 1),
            cooldown_minutes=_env_int("NEWSTRADER_COOLDOWN_MINUTES", 10),
            max_spread_points=_env_int("NEWSTRADER_MAX_SPREAD_POINTS", 45),
        )


@dataclass(slots=True)
class RuntimeConfig:
    queue_size: int = 1000
    processing_timeout_ms: int = 250
    min_confidence: float = 0.60

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        return cls(
            queue_size=_env_int("NEWSTRADER_QUEUE_SIZE", 1000),
            processing_timeout_ms=_env_int("NEWSTRADER_PROCESSING_TIMEOUT_MS", 250),
            min_confidence=_env_float("NEWSTRADER_MIN_CONFIDENCE", 0.60),
        )
