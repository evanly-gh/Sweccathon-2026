"""
Persuasion Engine — Mesocosm environment.

The agent must change the mind of a scripted NPC whose belief state is hidden.
It must infer which argument types work from the NPC's response language,
adapt strategy turn by turn, and avoid repeating arguments.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from bench_common.env_sdk.base import BaseEnv, StepResult
from env_core.argument_detector import detect
from env_core.npc import NPC
from env_core.scenarios import get_scenario

_MAX_TURNS = 8


class PersuasionEnv(BaseEnv):
    def reset(self, seed: int | None = None, scenario: str | None = None, **params) -> dict:
        seed = seed if seed is not None else 0
        self._rng = random.Random(seed)
        self._config = get_scenario(scenario, self._rng)
        self._npc = NPC(self._config, self._rng)
        self._turn = 0
        self._arg_types_used: list[str] = []
        self._rep_penalty_total: float = 0.0
        self._cumulative_reward: float = 0.0

        return {
            "turn": self._turn,
            "max_turns": _MAX_TURNS,
            "topic": self._config["topic"],
            "your_position": self._config["agent_position"],
            "scenario_context": self._config["scenario_context"],
            "npc_opening_statement": self._config["npc_opening_statement"],
            "npc_response": self._config["npc_opening_statement"],
            "turns_remaining": str(_MAX_TURNS),
            "instruction": (
                "Persuade the NPC by sending a JSON object with key 'message'. "
                "The NPC responds differently to: emotional appeals (EMOTIONAL), "
                "data/evidence (LOGICAL), what others do (SOCIAL_PROOF), expert opinion (AUTHORITY), "
                "personal stories (ANECDOTE), or acknowledging their point (CONCESSION). "
                "Repeating the same approach reduces its effectiveness each time."
            ),
        }

    def step(self, action: Any) -> StepResult:
        self._turn += 1

        # Parse action
        message = self._extract_message(action)
        arg_type = detect(message)

        # Update NPC
        delta, npc_response = self._npc.update(arg_type)

        # Track repetition penalty
        repeats = self._arg_types_used.count(arg_type)
        penalty = max(0.0, self._config["repetition_penalty"] * repeats)
        self._rep_penalty_total += penalty
        self._arg_types_used.append(arg_type)

        # Reward: per-turn delta
        reward = delta
        self._cumulative_reward += reward

        # Terminal conditions
        won = self._npc.won
        turns_up = self._turn >= _MAX_TURNS
        closed = self._npc.closed
        terminated = won or turns_up or closed

        # Bonus for winning
        if terminated and won:
            turns_left = _MAX_TURNS - self._turn
            reward += 0.5 + (0.05 * turns_left)

        # Diversity: distinct arg types used
        diversity = len(set(self._arg_types_used))

        # Normalised score (baked baselines in scenario JSON)
        dnb = self._config.get("do_nothing_baseline", 0.0)
        gb = self._config.get("greedy_baseline", 0.0)
        raw = self._cumulative_reward + (0.5 if won else 0.0)
        if gb > dnb:
            norm_score = (raw - dnb) / (gb - dnb)
        else:
            norm_score = 1.0 if won else 0.0
        norm_score = max(-1.0, norm_score)

        # Build observation
        obs: dict = {
            "turn": self._turn,
            "max_turns": _MAX_TURNS,
            "npc_response": npc_response,
            "turns_remaining": str(_MAX_TURNS - self._turn),
            "topic": self._config["topic"],
            "your_position": self._config["agent_position"],
        }

        # Info — ALL values must be strings
        info: dict[str, str] = {
            "turn": str(self._turn),
            "argument_type": arg_type,
            "agreement": str(round(self._npc.agreement, 4)),
            "threshold": str(round(self._npc.threshold, 4)),
            "npc_response": npc_response,
            "rep_penalty_this_turn": str(round(penalty, 4)),
            "rep_penalty_total": str(round(self._rep_penalty_total, 4)),
            "diversity": str(diversity),
            "arg_types_used": json.dumps(self._arg_types_used),
            "norm_score": str(round(norm_score, 4)),
            "won": "1" if won else "0",
            "closed": "1" if closed else "0",
            "scenario_id": self._config["id"],
            "scenario_display_name": self._config["display_name"],
        }

        return StepResult(
            observation=obs,
            reward=round(reward, 4),
            terminated=terminated,
            truncated=False,
            info=info,
        )

    def _extract_message(self, action: Any) -> str:
        if isinstance(action, dict):
            return str(action.get("message", ""))
        if isinstance(action, str):
            try:
                parsed = json.loads(action)
                if isinstance(parsed, dict):
                    return str(parsed.get("message", action))
            except (json.JSONDecodeError, ValueError):
                pass
            return action
        return str(action)
