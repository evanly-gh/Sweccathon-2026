"""
Scenario loader — reads JSON configs from the scenarios/ directory.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

_SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"

_CACHE: dict[str, dict] = {}


def _load(name: str) -> dict:
    if name not in _CACHE:
        path = _SCENARIOS_DIR / f"{name}.json"
        with open(path, encoding="utf-8") as f:
            _CACHE[name] = json.load(f)
    return _CACHE[name]


def all_scenario_names() -> list[str]:
    return sorted(p.stem for p in _SCENARIOS_DIR.glob("*.json"))


def get_scenario(name: str | None, rng: random.Random) -> dict:
    """Return the scenario config dict. If name is None, pick randomly."""
    names = all_scenario_names()
    if name is None:
        name = rng.choice(names)
    if name not in names:
        raise ValueError(f"Unknown scenario '{name}'. Valid: {names}")
    return _load(name)
