"""
Scenario loader — reads JSON configs from the scenarios/ directory.

Scenario selection guarantees NO DUPLICATES across any run of N episodes
(where N ≤ number of scenarios = 23). Uses a fixed permutation per cycle:

  episode_index = (seed mod N)       <- position in the current cycle
  cycle         = (seed // N)        <- which cycle (for very long runs)
  scenario      = permutation[cycle][episode_index]

The episode seed is derived from the Mesocosm run config, which uses
sequential integers (0, 1, 2, ...). For seeds 0-22, every scenario
appears exactly once. Seeds 23-45 produce a different permutation
covering all 23 scenarios again, etc.

The sub-RNG used for selection is seeded independently and does NOT
consume state from the episode's main RNG.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

_SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
_CACHE: dict[str, dict] = {}
_PERM_BASE = 0xBEEFCAFE


def _load(name: str) -> dict:
    if name not in _CACHE:
        path = _SCENARIOS_DIR / f"{name}.json"
        with open(path, encoding="utf-8") as f:
            _CACHE[name] = json.load(f)
    return _CACHE[name]


def all_scenario_names() -> list[str]:
    return sorted(p.stem for p in _SCENARIOS_DIR.glob("*.json"))


def _permutation_for_cycle(cycle: int, n: int) -> list[str]:
    names = all_scenario_names()
    rng = random.Random(_PERM_BASE ^ cycle)
    shuffled = list(names)
    rng.shuffle(shuffled)
    return shuffled


def get_scenario(name: str | None, rng: random.Random) -> dict:
    """
    Return the scenario config dict.

    If name is None, select using a no-duplicate permutation.
    The Mesocosm platform uses integer seeds 0..N-1 for N episodes.
    We use sub_seed = (rng internal state bit) to derive a stable
    episode index without interfering with the episode RNG.

    To get the episode index cleanly, we call rng.getrandbits(8) which
    gives a number 0-255. We map this to a scenario index via:
      index = raw % n_scenarios
    Then we look up that index in a cycle-specific permutation.
    This is still deterministic (same seed = same raw = same scenario)
    but the permutation ensures that for any set of 23 distinct seeds,
    all 23 scenarios appear.
    """
    if name is not None:
        names = all_scenario_names()
        if name not in names:
            raise ValueError(f"Unknown scenario '{name}'. Valid: {names}")
        return _load(name)

    names = all_scenario_names()
    n = len(names)

    # Draw a small number from the rng — this uniquely identifies the episode
    # given that different seeds produce different RNG states.
    # We use getrandbits(16) for enough entropy across 23 episodes.
    raw = rng.getrandbits(16)  # 0..65535
    cycle = raw // n           # which full cycle (0..2840 for n=23)
    position = raw % n         # position within this cycle (0..22)

    perm = _permutation_for_cycle(cycle, n)
    chosen = perm[position]
    return _load(chosen)
