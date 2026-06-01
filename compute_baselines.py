"""
Compute do-nothing and greedy/adaptive baseline scores for all scenarios.

The greedy_baseline uses the BETTER of GreedyArgAgent and AdaptiveArgAgent,
so that scenarios dominated by a single strategy (where greedy cycles through
all types and therefore underperforms) still have a meaningful ceiling.

Usage: python compute_baselines.py [--bake]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from env import PersuasionEnv
from baselines.agents import AdaptiveArgAgent, DoNothingAgent, GreedyArgAgent
from env_core.scenarios import all_scenario_names

_SEEDS = [42, 43, 44, 45, 46]
_SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def raw_score(agent_factory, scenario: str, seeds: list[int]) -> float:
    totals = []
    for seed in seeds:
        env = PersuasionEnv()
        obs = env.reset(seed=seed, scenario=scenario)
        agent = agent_factory()
        cumulative = 0.0
        while True:
            result = env.step(agent.act(obs))
            cumulative += result.reward
            obs = result.observation
            if result.terminated or result.truncated:
                break
        totals.append(cumulative)
    return sum(totals) / len(totals)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bake", action="store_true", help="Write baselines into scenario JSONs")
    args = parser.parse_args()

    print(f"{'Scenario':<30} {'DoNothing':>10} {'Greedy':>10} {'Adaptive':>10} {'Ceiling':>10}")
    print("-" * 74)

    for sc in all_scenario_names():
        dnb = raw_score(DoNothingAgent, sc, _SEEDS)
        gb = raw_score(GreedyArgAgent, sc, _SEEDS)
        ab = raw_score(AdaptiveArgAgent, sc, _SEEDS)
        # Use the better of greedy/adaptive as the normalization ceiling
        ceiling = max(gb, ab)
        print(f"{sc:<30} {dnb:>10.4f} {gb:>10.4f} {ab:>10.4f} {ceiling:>10.4f}")

        if args.bake:
            path = _SCENARIOS_DIR / f"{sc}.json"
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["do_nothing_baseline"] = round(dnb, 4)
            cfg["greedy_baseline"] = round(ceiling, 4)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)

    if args.bake:
        print("\nBaselines baked into scenario JSONs.")


if __name__ == "__main__":
    main()
