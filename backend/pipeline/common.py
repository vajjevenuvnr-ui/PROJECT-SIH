"""Shared helpers for the pipeline: config, paths, step timing."""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[1]


@lru_cache
def config() -> dict:
    cfg = yaml.safe_load((BACKEND / "pipeline" / "config.yaml").read_text(encoding="utf-8"))
    cfg["paths"] = {k: BACKEND / v for k, v in cfg["paths"].items()}
    for p in cfg["paths"].values():
        p.mkdir(parents=True, exist_ok=True)
    return cfg


@dataclass
class Timer:
    """Collects per-step timings for the run report."""

    steps: list[tuple[str, float]] = field(default_factory=list)
    started: float = field(default_factory=time.perf_counter)

    @contextlib.contextmanager
    def step(self, name: str):
        t0 = time.perf_counter()
        print(f"  > {name} ...", flush=True)
        try:
            yield
        finally:
            dt = time.perf_counter() - t0
            self.steps.append((name, dt))
            print(f"    {name}: {dt:.1f} s", flush=True)

    @property
    def total(self) -> float:
        return time.perf_counter() - self.started

    def report(self) -> str:
        lines = [f"    {n:<34} {t:6.1f} s" for n, t in self.steps]
        return "\n".join(lines + [f"    {'TOTAL':<34} {self.total:6.1f} s"])
