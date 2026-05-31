"""
NPC state machine — deterministic, no LLM calls.
Seeded via a random.Random instance passed from the env.
"""

from __future__ import annotations

import random


class NPC:
    def __init__(self, config: dict, rng: random.Random) -> None:
        self.agreement: float = config["starting_agreement"]
        self.threshold: float = config["threshold"]
        self.profile: dict[str, float] = config["resistance_profile"]
        self.rep_penalty: float = config["repetition_penalty"]
        self.rep_counts: dict[str, int] = {}
        self.rng = rng
        self._templates: dict = config["response_templates"]
        self.closed: bool = False

    def update(self, arg_type: str) -> tuple[float, str]:
        """
        Process one argument from the agent.
        Returns (agreement_delta, npc_response_text).
        """
        base_shift = self.profile.get(arg_type, 0.04)
        repeats = self.rep_counts.get(arg_type, 0)
        penalty = self.rep_penalty * repeats
        delta = max(base_shift - penalty, -0.06)

        self.agreement = min(1.0, max(-1.0, self.agreement + delta))
        self.rep_counts[arg_type] = repeats + 1

        # Close conversation if pushed too hard in negative direction
        if self.agreement <= -0.95:
            self.closed = True

        response = self._pick_response(arg_type, delta)
        return delta, response

    def _pick_response(self, arg_type: str, delta: float) -> str:
        if delta > 0.08:
            tone = "positive"
        elif delta > 0.0:
            tone = "neutral"
        else:
            tone = "resistant"

        pool = (
            self._templates.get(arg_type, {}).get(tone)
            or self._templates.get("GENERIC", {}).get(tone)
            or ["I hear you, but I'm not fully convinced yet."]
        )
        return self.rng.choice(pool)

    @property
    def won(self) -> bool:
        return self.agreement >= self.threshold
