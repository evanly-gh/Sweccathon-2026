"""
Run a local episode for debugging.

Usage:
    python run_local.py
    python run_local.py --agent greedy --scenario cold_skeptic
    python run_local.py --agent adaptive --seed 7 --episodes 3
    python run_local.py --trace-out showcase/data/replay.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from env import PersuasionEnv
from baselines.agents import AdaptiveArgAgent, DoNothingAgent, GreedyArgAgent, RandomArgAgent


def run_episode(agent, seed: int, scenario: str | None, trace: list | None) -> dict:
    env = PersuasionEnv()
    kwargs: dict = {}
    if scenario:
        kwargs["scenario"] = scenario
    obs = env.reset(seed=seed, **kwargs)

    if trace is not None:
        trace.append({
            "turn": 0,
            "observation": obs,
            "action": None,
            "reward": 0.0,
            "terminated": False,
            "truncated": False,
            "info": {},
        })

    step = 0
    while True:
        action = agent.act(obs)
        result = env.step(action)
        step += 1

        if trace is not None:
            trace.append({
                "turn": step,
                "observation": result.observation,
                "action": action,
                "reward": result.reward,
                "terminated": result.terminated,
                "truncated": result.truncated,
                "info": result.info,
            })

        obs = result.observation
        if result.terminated or result.truncated:
            print(f"  Episode ended at turn {step} | won={result.info.get('won')} "
                  f"| agreement={result.info.get('agreement')} "
                  f"| norm_score={result.info.get('norm_score')}")
            return result.info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=["random", "greedy", "adaptive", "nothing"], default="greedy")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--trace-out", default=None, metavar="PATH")
    args = parser.parse_args()

    agent_map = {
        "random": lambda s: RandomArgAgent(seed=s),
        "greedy": lambda _: GreedyArgAgent(),
        "adaptive": lambda _: AdaptiveArgAgent(),
        "nothing": lambda _: DoNothingAgent(),
    }

    for ep in range(args.episodes):
        seed = args.seed + ep
        label = args.scenario or "random"
        print(f"\n=== Episode {ep + 1} | scenario={label} seed={seed} agent={args.agent} ===")

        agent = agent_map[args.agent](seed)
        trace_steps: list | None = [] if (args.trace_out and ep == 0) else None
        info = run_episode(agent, seed, args.scenario, trace=trace_steps)
        print(json.dumps({k: v for k, v in info.items() if k in
                          ("won", "norm_score", "diversity", "rep_penalty_total", "scenario_id")}, indent=2))

        if trace_steps is not None and args.trace_out:
            trace_data = {
                "format": "persuasion-local-v1",
                "scenario": args.scenario or "random",
                "agent": args.agent,
                "seed": seed,
                "steps": trace_steps,
            }
            out = Path(args.trace_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(trace_data, f, indent=2)
            print(f"  Trace saved: {out}")


if __name__ == "__main__":
    main()
