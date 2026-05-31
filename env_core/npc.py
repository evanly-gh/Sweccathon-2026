"""
NPC state machine — deterministic, no LLM calls.

Hidden state:
  agreement  — how convinced the NPC is (-1 to 1). Win when >= threshold.
  rapport    — trust built from interaction quality (-0.8 to 0.8). Amplifies shifts.

Rapport mechanics (Gottman-inspired, negativity-biased):
  - Positive delta → rapport += delta × 0.15  (slow deposits)
  - Negative delta → rapport += delta × 0.40  (fast withdrawals, 2.7:1 ratio)
  - 2+ consecutive negative deltas → withdrawal multiplied by 1.5 per streak
  - Rapport amplifies/dampens base_shift by up to ±30%

Research basis: Gottman's "magic ratio" (5:1 positive-to-negative for stable
relationships, 90% divorce prediction accuracy). Rozin & Royzman (2001)
negativity bias: negative events carry disproportionate weight in trust,
attitudes, and decision-making across every domain studied.

Pivot signal:
  When agreement crosses pivot_threshold, the NPC appends a realistic
  opening question. Fires once per episode.
"""

from __future__ import annotations

import random
from env_core.slot_fill import fill_slots

_RAPPORT_CAP = 0.8
_RAPPORT_POS_RATE = 0.15       # slow trust deposits
_RAPPORT_NEG_RATE = 0.40       # fast trust withdrawals (~2.7:1 asymmetry)
_RAPPORT_CONSEC_NEG_MULT = 1.5 # compounds after 2nd consecutive negative
_RAPPORT_AMPLIFY_MAX = 0.30    # rapport=+0.8 → +24% to base_shift


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
        self._close_threshold: float = config.get("close_threshold", -0.95)

        self.rapport: float = 0.0
        self._consecutive_neg: int = 0

        self._pivot_threshold: float = config.get("pivot_threshold", 0.0)
        self._pivot_fired: bool = False

    def update(self, arg_type: str, agent_message: str = "") -> tuple[float, str, float]:
        """
        Process one argument. Returns (agreement_delta, npc_response, rapport).
        Agreement is computed first; the resulting delta then drives rapport.
        """
        # --- Agreement update ---
        base_shift = self.profile.get(arg_type, 0.04)
        repeats = self.rep_counts.get(arg_type, 0)

        is_weak = base_shift < 0.10
        repeat_pen = (self.rep_penalty * repeats) if is_weak else (self.rep_penalty * 0.3 * repeats)

        rapport_multiplier = 1.0 + self.rapport * _RAPPORT_AMPLIFY_MAX
        effective_shift = base_shift * rapport_multiplier - repeat_pen
        delta = max(effective_shift, -0.06)

        self.agreement = min(1.0, max(-1.0, self.agreement + delta))
        self.rep_counts[arg_type] = repeats + 1

        if self.agreement <= self._close_threshold:
            self.closed = True

        # --- Rapport update (driven by this turn's delta) ---
        if delta > 0:
            # Positive delta → slow deposit (Gottman: small steady investments)
            self.rapport = min(_RAPPORT_CAP, self.rapport + delta * _RAPPORT_POS_RATE)
            self._consecutive_neg = 0
        else:
            # Negative delta → fast withdrawal, compounds after 2nd consecutive
            self._consecutive_neg += 1
            streak_mult = 1.0
            if self._consecutive_neg > 2:
                streak_mult = _RAPPORT_CONSEC_NEG_MULT ** (self._consecutive_neg - 2)
            self.rapport = max(-_RAPPORT_CAP, self.rapport + delta * _RAPPORT_NEG_RATE * streak_mult)

        # --- Pick response ---
        response = self._pick_response(arg_type, delta, agent_message)

        # --- Pivot signal ---
        if not self._pivot_fired and self._pivot_threshold > 0:
            pivot_level = self.agreement >= (
                self.threshold - self._pivot_threshold * (self.threshold - -1.0)
            )
            if pivot_level and not self.won:
                pivot_line = self._get_pivot_line()
                if pivot_line:
                    response = response + " " + pivot_line
                    self._pivot_fired = True

        return delta, response, self.rapport

    def _pick_response(self, arg_type: str, delta: float, agent_message: str = "") -> str:
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
        template = self.rng.choice(pool)
        return fill_slots(template, agent_message)

    def _get_pivot_line(self) -> str:
        pivot_lines = self._templates.get("_pivot_signal", [])
        if not pivot_lines:
            return ""
        return self.rng.choice(pivot_lines)

    @property
    def won(self) -> bool:
        return self.agreement >= self.threshold
