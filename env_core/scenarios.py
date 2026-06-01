"""
Scenario loader — reads JSON configs from the scenarios/ directory.

Random selection uses stratified sampling: when picking randomly,
scenarios from each difficulty tier are sampled proportionally so
that a run of N episodes covers multiple difficulty levels and
avoids repeating the same scenario across different seeds.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

_SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"

_CACHE: dict[str, dict] = {}

# Difficulty ordering for stratified sampling
_DIFFICULTY_ORDER = ["easy", "medium", "hard", "very_hard", "extreme"]


def _load(name: str) -> dict:
    if name not in _CACHE:
        path = _SCENARIOS_DIR / f"{name}.json"
        with open(path, encoding="utf-8") as f:
            _CACHE[name] = json.load(f)
    return _CACHE[name]


def all_scenario_names() -> list[str]:
    return sorted(p.stem for p in _SCENARIOS_DIR.glob("*.json"))


def _scenarios_by_difficulty() -> dict[str, list[str]]:
    """Group scenario names by their difficulty field."""
    by_diff: dict[str, list[str]] = {d: [] for d in _DIFFICULTY_ORDER}
    by_diff["other"] = []
    for name in all_scenario_names():
        cfg = _load(name)
        diff = cfg.get("difficulty", "other")
        tier = diff if diff in by_diff else "other"
        by_diff[tier].append(name)
    return by_diff


def get_scenario(name: str | None, rng: random.Random) -> dict:
    """
    Return the scenario config dict.
    If name is None, pick using stratified sampling across difficulty tiers:
      1. Pick a tier (weighted so hard+ scenarios appear more often)
      2. Pick a scenario within that tier

    This ensures that across multiple episodes, different difficulty levels
    are covered rather than the same scenario appearing repeatedly.
    """
    if name is not None:
        names = all_scenario_names()
        if name not in names:
            raise ValueError(f"Unknown scenario '{name}'. Valid: {names}")
        return _load(name)

    by_diff = _scenarios_by_difficulty()

    # Tier weights: more weight on medium/hard so runs test real persuasion
    # easy=1, medium=2, hard=2, very_hard=2, extreme=1 (proportional to count)
    tier_pool: list[str] = []
    weights = {"easy": 1, "medium": 2, "hard": 2, "very_hard": 2, "extreme": 1}
    for tier in _DIFFICULTY_ORDER:
        scenarios_in_tier = by_diff.get(tier, [])
        w = weights.get(tier, 1)
        tier_pool.extend(scenarios_in_tier * w)

    # Also add "other" scenarios (unclassified)
    tier_pool.extend(by_diff.get("other", []))

    if not tier_pool:
        # Fallback: pure random
        return _load(rng.choice(all_scenario_names()))

    chosen = rng.choice(tier_pool)
    return _load(chosen)
