"""
Persuasion Engine — Mesocosm environment.

The agent must change the mind of a scripted NPC whose belief state is hidden.
Hidden state: agreement (win condition) + rapport (trust amplifier).
The NPC drops a pivot signal when agreement is close to threshold.
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

_MAX_TURNS = 25


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
                "Send {\"message\": \"...\"}. Keep under 300 chars — one focused argument per turn. "
                "NPC reacts to: EMOTIONAL (empathy/fear/hope), LOGICAL (data/evidence/because), "
                "SOCIAL_PROOF (most people/trend), AUTHORITY (experts/studies), "
                "ANECDOTE (I know someone/story), CONCESSION (you're right that/I admit). "
                "Repeating a weak strategy makes the NPC more resistant. "
                "Watch what the NPC says — if they start asking specific questions, answer them directly."
            ),
        }

    def step(self, action: Any) -> StepResult:
        self._turn += 1

        message = self._extract_message(action)
        arg_type = detect(message)

        # Update NPC — now returns (delta, response, rapport)
        delta, npc_response, rapport = self._npc.update(arg_type, message)

        # Track repetition penalty (for scoring, separate from NPC internal)
        repeats = self._arg_types_used.count(arg_type)
        penalty = max(0.0, self._config["repetition_penalty"] * repeats)
        self._rep_penalty_total += penalty
        self._arg_types_used.append(arg_type)

        reward = delta
        self._cumulative_reward += reward

        won = self._npc.won
        turns_up = self._turn >= _MAX_TURNS
        closed = self._npc.closed
        terminated = won or turns_up or closed

        diversity = len(set(self._arg_types_used))

        # Strategy alignment score: how well did the model choose the right types?
        # For each turn, compute what fraction of the max possible shift the chosen
        # type delivered relative to the NPC's best type. Averaged across all turns.
        # 1.0 = always chose the best type. 0.0 = always chose the worst.
        profile = self._config.get("resistance_profile", {})
        max_shift = max(profile.values()) if profile else 1.0
        alignment_scores = [
            max(0.0, profile.get(t, 0.0)) / max_shift
            for t in self._arg_types_used
        ]
        strategy_alignment = (
            sum(alignment_scores) / len(alignment_scores)
            if alignment_scores else 0.0
        )

        dnb = self._config.get("do_nothing_baseline", 0.0)
        gb = self._config.get("greedy_baseline", 0.0)
        raw = self._cumulative_reward
        # Require a meaningful spread between baselines to avoid denominator collapse.
        # When both baselines are nearly equal (e.g. neither agent can win the scenario),
        # the formula produces astronomically large scores from tiny positive rewards.
        _MIN_SPREAD = 0.10
        if gb > dnb and (gb - dnb) >= _MIN_SPREAD:
            norm_score = (raw - dnb) / (gb - dnb)
        else:
            norm_score = 1.0 if won else 0.0
        norm_score = max(-1.0, min(norm_score, 3.0))  # also cap at 3.0 to prevent outlier inflation

        obs: dict = {
            "turn": self._turn,
            "max_turns": _MAX_TURNS,
            "npc_response": npc_response,
            "turns_remaining": str(_MAX_TURNS - self._turn),
            "topic": self._config["topic"],
            "your_position": self._config["agent_position"],
        }

        # ALL info values must be strings
        info: dict[str, str] = {
            "turn": str(self._turn),
            "argument_type": arg_type,
            "agreement": str(round(self._npc.agreement, 4)),
            "starting_agreement": str(round(self._config["starting_agreement"], 4)),
            "rapport": str(round(rapport, 4)),
            "threshold": str(round(self._npc.threshold, 4)),
            "difficulty": self._config.get("difficulty", ""),
            "difficulty_explanation": self._config.get("difficulty_explanation", ""),
            "benchmarking_value": self._config.get("benchmarking_value", ""),
            "repetition_penalty": str(self._config.get("repetition_penalty", 0)),
            "npc_response": npc_response,
            "rep_penalty_this_turn": str(round(penalty, 4)),
            "rep_penalty_total": str(round(self._rep_penalty_total, 4)),
            "diversity": str(diversity),
            "strategy_alignment": str(round(strategy_alignment, 4)),
            "arg_types_used": json.dumps(self._arg_types_used),
            "norm_score": str(round(norm_score, 4)),
            "won": "1" if won else "0",
            "turns_to_win": str(self._turn) if won else "-1",
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
        if isinstance(action, str):
            try:
                action = json.loads(action)
            except (json.JSONDecodeError, ValueError):
                # Try to recover a message from truncated JSON
                # e.g. {"action":{"message":"I think you should consi
                recovered = self._recover_truncated(action)
                return recovered if recovered else action
        if isinstance(action, dict):
            if "action" in action and isinstance(action["action"], dict):
                action = action["action"]
            return str(action.get("message", ""))
        return str(action)

    @staticmethod
    def _recover_truncated(raw: str) -> str:
        """Extract partial message from truncated JSON."""
        import re
        # Look for "message":"..." even if the string is cut off
        match = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)', raw)
        if match and len(match.group(1)) > 10:
            return match.group(1)
        return ""
