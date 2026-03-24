from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - python<3.11 fallback
    import tomli as tomllib


def _normalize_domain(value: str) -> str:
    candidate = value.strip().lower()
    if not candidate:
        return ""

    if "://" in candidate:
        host = urlparse(candidate).netloc
        candidate = host or candidate
    else:
        candidate = candidate.split("/", 1)[0]

    if candidate.startswith("www."):
        candidate = candidate[4:]
    if ":" in candidate:
        candidate = candidate.split(":", 1)[0]
    return candidate


@dataclass(slots=True)
class PipelineConfig:
    dedup_ttl_minutes: int = 120
    max_open_positions: int = 1
    cooldown_minutes: int = 10
    max_spread_points: int = 45
    allowed_domains: set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineConfig":
        domains = {
            normalized
            for entry in data.get("allowed_domains", [])
            if isinstance(entry, str)
            for normalized in [_normalize_domain(entry)]
            if normalized
        }
        return cls(
            dedup_ttl_minutes=int(data.get("dedup_ttl_minutes", 120)),
            max_open_positions=int(data.get("max_open_positions", 1)),
            cooldown_minutes=int(data.get("cooldown_minutes", 10)),
            max_spread_points=int(data.get("max_spread_points", 45)),
            allowed_domains=domains,
        )


@dataclass(slots=True)
class RuntimeConfig:
    queue_size: int = 1000
    processing_timeout_ms: int = 250
    min_confidence: float = 0.60

    @classmethod
    def from_dict(cls, data: dict) -> "RuntimeConfig":
        return cls(
            queue_size=int(data.get("queue_size", 1000)),
            processing_timeout_ms=int(data.get("processing_timeout_ms", 250)),
            min_confidence=float(data.get("min_confidence", 0.60)),
        )


@dataclass(slots=True)
class AppConfig:
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    @classmethod
    def from_toml(cls, path: str | Path) -> "AppConfig":
        parsed = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            pipeline=PipelineConfig.from_dict(parsed.get("pipeline", {})),
            runtime=RuntimeConfig.from_dict(parsed.get("runtime", {})),
        )


def load_app_config() -> AppConfig:
    """Load non-secret runtime settings from TOML config.

    Environment variables are only used for locating the config file.
    """

    path = Path(os.getenv("NEWSTRADER_CONFIG", "newstrader.toml"))
    if path.exists():
        return AppConfig.from_toml(path)
    return AppConfig()
