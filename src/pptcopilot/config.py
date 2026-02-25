"""Central configuration for ppt-copilot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    """Filesystem paths used across stages."""

    repo_root: Path
    data_dir: Path
    reports_dir: Path


@dataclass(frozen=True)
class SummarizeDefaults:
    """Deterministic defaults for baseline summarization."""

    seed: int = 0
    temperature: float = 0.0
    model: str = "mock"
    include_slide_bullets: bool = True


@dataclass(frozen=True)
class RetrievalDefaults:
    """Defaults for chunking and retrieval."""

    chunk_size_tokens: int = 40
    chunk_overlap_tokens: int = 8
    embedding_dim: int = 256
    top_k: int = 3


@dataclass(frozen=True)
class BenchDefaults:
    """Defaults for latency/cost benchmarking."""

    suite: str = "smoke"
    iterations: int = 5
    warmup: int = 1
    batch_size: int = 1
    cost_per_gpu_hour_usd: float = 1.8
    target_utilization: float = 0.7


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_paths(repo_root: Path | None = None) -> Paths:
    root = repo_root or _default_repo_root()
    return Paths(
        repo_root=root,
        data_dir=root / "data",
        reports_dir=root / "reports",
    )


def get_summarize_defaults() -> SummarizeDefaults:
    return SummarizeDefaults()


def get_retrieval_defaults() -> RetrievalDefaults:
    return RetrievalDefaults()


def get_bench_defaults() -> BenchDefaults:
    return BenchDefaults()
