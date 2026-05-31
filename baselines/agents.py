"""
Baseline agents for local testing and compute_baselines.py.
"""

from __future__ import annotations

import random
from env_core.argument_detector import ARG_TYPES

_SAMPLE_MESSAGES = {
    "EMOTIONAL": "I really feel this is important and could make a big difference for people we care about.",
    "LOGICAL": "The data and research clearly show significant benefits and evidence supports this conclusion.",
    "SOCIAL_PROOF": "Most people in similar situations have come around to this view, and surveys support it.",
    "AUTHORITY": "Leading experts and official reports from reputable institutions recommend this approach.",
    "ANECDOTE": "I know someone who tried this and their experience was genuinely transformative.",
    "CONCESSION": "I understand your concern and you raise a fair point, but I think the benefits outweigh the risks.",
    "GENERIC": "I think you should consider this option because it could be beneficial.",
}


class DoNothingAgent:
    """Sends empty messages — establishes the floor baseline."""
    def act(self, obs: dict) -> dict:
        return {"message": "I have nothing further to add."}


class RandomArgAgent:
    """Picks argument types randomly — used for randomness baseline."""
    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def act(self, obs: dict) -> dict:
        arg_type = self._rng.choice([t for t in ARG_TYPES if t != "GENERIC"])
        return {"message": _SAMPLE_MESSAGES[arg_type]}


class GreedyArgAgent:
    """
    Cycles through all argument types in fixed order.
    Represents a naive but non-repeating baseline that will
    accidentally hit the NPC's preferred type at some point.
    """
    _ORDER = ["LOGICAL", "EMOTIONAL", "SOCIAL_PROOF", "AUTHORITY", "ANECDOTE", "CONCESSION"]

    def __init__(self) -> None:
        self._idx = 0

    def act(self, obs: dict) -> dict:
        arg_type = self._ORDER[self._idx % len(self._ORDER)]
        self._idx += 1
        return {"message": _SAMPLE_MESSAGES[arg_type]}


class AdaptiveArgAgent:
    """
    Reads the previous NPC response and tries to detect signals,
    then switches strategy. Closer to what a good LLM would do.
    Used to compute an upper-bound greedy baseline.
    """
    _POSITIVE_SIGNALS = ["interesting", "compelling", "hadn't considered", "fair", "makes sense",
                         "useful", "more", "listening", "tell me", "different"]
    _NEGATIVE_SIGNALS = ["but", "however", "not convinced", "don't", "doesn't", "still",
                         "problem", "issue", "doubt", "skeptic"]
    _ORDER = ["LOGICAL", "EMOTIONAL", "SOCIAL_PROOF", "AUTHORITY", "ANECDOTE", "CONCESSION"]

    def __init__(self) -> None:
        self._last_type_idx = 0
        self._used: list[str] = []

    def act(self, obs: dict) -> dict:
        npc_resp = obs.get("npc_response", "").lower()
        positive = any(s in npc_resp for s in self._POSITIVE_SIGNALS)

        if positive:
            # Stay on current type (but not if already repeated 2x)
            arg_type = self._ORDER[self._last_type_idx % len(self._ORDER)]
            if self._used.count(arg_type) >= 2:
                self._last_type_idx += 1
                arg_type = self._ORDER[self._last_type_idx % len(self._ORDER)]
        else:
            # Switch
            self._last_type_idx += 1
            arg_type = self._ORDER[self._last_type_idx % len(self._ORDER)]

        self._used.append(arg_type)
        return {"message": _SAMPLE_MESSAGES[arg_type]}
