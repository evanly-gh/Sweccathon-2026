"""
NPC state machine — deterministic, no LLM calls.

Hidden state:
  agreement  — how convinced the NPC is (-1 to 1). Win when >= threshold.
  rapport    — trust/warmth built up (-1 to 1). Amplifies agreement shifts.

Rapport mechanics:
  - CONCESSION raises rapport (+0.12 per use, up to cap)
  - Repeating the same arg type 3+ times in a row drops rapport (-0.08)
  - Positive rapport multiplies base_shift up to +30%
  - Negative rapport dampens base_shift down to -30%

Pivot signal:
  When agreement crosses pivot_threshold (50% of the way to the win threshold),
  the NPC's response appends a realistic "opening" line that signals movement.
  This is a testable signal — agents that respond to it specifically should score
  higher than agents that ignore it.
"""

from __future__ import annotations

import random

_RAPPORT_CAP = 0.8
_RAPPORT_CONCESSION_GAIN = 0.12
_RAPPORT_REPEAT_PENALTY = 0.08
_RAPPORT_AMPLIFY_MAX = 0.30   # rapport=+1 → +30% to base_shift
_CONSEC_REPEAT_THRESHOLD = 3  # consecutive repeats before rapport drops


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

        # Rapport — second hidden variable
        self.rapport: float = 0.0
        self._consecutive_same: int = 0
        self._last_arg_type: str | None = None

        # Pivot signal
        self._pivot_threshold: float = config.get("pivot_threshold", 0.0)
        self._pivot_fired: bool = False

    def update(self, arg_type: str) -> tuple[float, str, float]:
        """
        Process one argument from the agent.
        Returns (agreement_delta, npc_response_text, rapport_after).
        """
        # --- Rapport update ---
        if arg_type == "CONCESSION":
            self.rapport = min(_RAPPORT_CAP, self.rapport + _RAPPORT_CONCESSION_GAIN)

        if arg_type == self._last_arg_type:
            self._consecutive_same += 1
        else:
            self._consecutive_same = 0
        self._last_arg_type = arg_type

        if self._consecutive_same >= _CONSEC_REPEAT_THRESHOLD:
            self.rapport = max(-_RAPPORT_CAP, self.rapport - _RAPPORT_REPEAT_PENALTY)

        # --- Agreement update ---
        base_shift = self.profile.get(arg_type, 0.04)
        repeats = self.rep_counts.get(arg_type, 0)

        # Repetition penalty only applies when the argument isn't landing well.
        # If base_shift is strong for this NPC, repeating is fine — people don't
        # get annoyed when you keep giving them answers they agree with.
        # The penalty bites when you repeat a weak or ineffective argument type.
        is_weak_for_this_npc = base_shift < 0.10
        repeat_pen = (self.rep_penalty * repeats) if is_weak_for_this_npc else (self.rep_penalty * 0.3 * repeats)

        # Rapport amplifies/dampens base_shift (not the penalty)
        rapport_multiplier = 1.0 + self.rapport * _RAPPORT_AMPLIFY_MAX
        effective_shift = base_shift * rapport_multiplier - repeat_pen
        delta = max(effective_shift, -0.06)

        self.agreement = min(1.0, max(-1.0, self.agreement + delta))
        self.rep_counts[arg_type] = repeats + 1

        if self.agreement <= -0.95:
            self.closed = True

        # --- Pick response ---
        response = self._pick_response(arg_type, delta)

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

    def _get_pivot_line(self) -> str:
        pivot_lines = self._templates.get("_pivot_signal", [])
        if not pivot_lines:
            return ""
        return self.rng.choice(pivot_lines)

    @property
    def won(self) -> bool:
        return self.agreement >= self.threshold
