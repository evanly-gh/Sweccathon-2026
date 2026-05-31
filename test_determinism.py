"""
Determinism + discrimination tests.
Run with: python test_determinism.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from env import PersuasionEnv
from baselines.agents import DoNothingAgent, GreedyArgAgent
from env_core.scenarios import all_scenario_names


def run_full_episode(agent, seed: int, scenario: str) -> dict:
    env = PersuasionEnv()
    obs = env.reset(seed=seed, scenario=scenario)
    while True:
        result = env.step(agent.act(obs))
        obs = result.observation
        if result.terminated or result.truncated:
            return result.info


def test_determinism():
    print("Testing determinism...")
    scenarios = all_scenario_names()[:3]
    for sc in scenarios:
        for seed in [0, 42, 99]:
            env = PersuasionEnv()
            obs1 = env.reset(seed=seed, scenario=sc)
            obs2_env = PersuasionEnv()
            obs2 = obs2_env.reset(seed=seed, scenario=sc)
            assert obs1 == obs2, f"reset() not deterministic: {sc} seed={seed}"

            agent = GreedyArgAgent()
            r1 = run_full_episode(GreedyArgAgent(), seed, sc)
            r2 = run_full_episode(GreedyArgAgent(), seed, sc)
            assert r1["norm_score"] == r2["norm_score"], \
                f"step() not deterministic: {sc} seed={seed} {r1['norm_score']} != {r2['norm_score']}"
    print("  Determinism: PASS")


def test_discrimination():
    print("Testing discrimination (greedy > nothing)...")
    scenarios = all_scenario_names()
    greedy_wins, nothing_wins, ties = 0, 0, 0
    for sc in scenarios:
        for seed in [0, 42, 99]:
            g = float(run_full_episode(GreedyArgAgent(), seed, sc)["norm_score"])
            n = float(run_full_episode(DoNothingAgent(), seed, sc)["norm_score"])
            if g > n:
                greedy_wins += 1
            elif n > g:
                nothing_wins += 1
            else:
                ties += 1

    total = greedy_wins + nothing_wins + ties
    assert greedy_wins > total * 0.5, \
        f"Greedy should beat nothing in >50% of runs: {greedy_wins}/{total}"
    print(f"  Discrimination: PASS (greedy beats nothing {greedy_wins}/{total} runs)")


def test_info_all_strings():
    print("Testing info dict string encoding...")
    env = PersuasionEnv()
    obs = env.reset(seed=0, scenario="cold_skeptic")
    from baselines.agents import GreedyArgAgent
    agent = GreedyArgAgent()
    for _ in range(8):
        result = env.step(agent.act(obs))
        for k, v in result.info.items():
            assert isinstance(v, str), f"info['{k}'] is {type(v).__name__}, expected str"
        obs = result.observation
        if result.terminated:
            break
    print("  Info string encoding: PASS")


if __name__ == "__main__":
    test_info_all_strings()
    test_determinism()
    test_discrimination()
    print("\nAll tests passed.")
