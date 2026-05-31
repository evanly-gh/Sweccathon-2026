"""
NPC state machine — deterministic, no LLM calls.

Hidden state:
  agreement  — how convinced the NPC is (-1 to 1). Win when >= threshold.
  rapport    — trust quality of the interaction (-0.8 to 0.8).

Rapport mechanics (Gottman-inspired, delta-driven):
  Rapport is driven entirely by how well each turn went (the delta), not
  by which argument type was used. This is grounded in rapport research
  showing trust comes from consistent positive engagement, not from any
  single technique.

  The four quadrants:
    Good answer + good rapport  → agreement up, rapport up modestly
    Bad answer + good rapport   → agreement down, rapport down modestly
    Good answer + bad rapport   → agreement up a little, rapport recovers
    Bad answer + bad rapport    → agreement down hard, rapport craters

  Streak scaling: consecutive positives/negatives compound the effect.
  Negative streaks compound faster (Gottman 5:1 asymmetry).

  Recovery mechanic: a good answer while rapport is very negative triggers
  a partial reset to -0.1 × |rapport| — the NPC recognizes the shift but
  doesn't fully forgive. Based on trust repair research on "pro-relationship
  motivation signals" (Handbook of Trust, 2025).

Rapport amplifies agreement shifts by up to ±30%.
"""

from __future__ import annotations

import random
from env_core.slot_fill import fill_slots

_RAPPORT_CAP = 0.8

# Base rates for rapport change from delta
_RAPPORT_POS_BASE = 0.25       # reach rapport ~0.3-0.5 in 4-5 good turns
_RAPPORT_NEG_BASE = 0.50       # crash to ~-0.3 in 2-3 bad turns (2:1 asymmetry)

# Streak multipliers
_POS_STREAK_MULT = 1.1         # each consecutive positive → 10% more rapport gain
_NEG_STREAK_MULT = 1.5         # each consecutive negative → 50% more rapport loss

# Recovery: when rapport < -0.3 and delta > 0, reset rapport toward zero
_RECOVERY_THRESHOLD = -0.3     # rapport must be this low to trigger recovery
_RECOVERY_FACTOR = 0.10        # rapport resets to current × (1 - factor)

# Rapport influence on agreement
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
        self._streak: int = 0     # positive = consecutive good, negative = consecutive bad

        self._pivot_threshold: float = config.get("pivot_threshold", 0.0)
        self._pivot_fired: bool = False

    def update(self, arg_type: str, agent_message: str = "") -> tuple[float, str, float]:
        """
        Process one argument. Returns (agreement_delta, npc_response, rapport).
        """
        # --- Agreement update (computed first, delta drives rapport) ---
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

        # --- Rapport update (driven by delta, scaled by streak and current rapport) ---
        self._update_rapport(delta)

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

    def _update_rapport(self, delta: float) -> None:
        """
        Update rapport based on this turn's agreement delta.

        The four quadrants:
          delta > 0, rapport >= 0 → both go up modestly
          delta < 0, rapport >= 0 → rapport drops modestly (good will erodes)
          delta < 0, rapport < 0  → rapport craters (compounding distrust)
          delta > 0, rapport < 0  → partial recovery (NPC sees potential)
        """
        if delta > 0:
            # --- Positive delta ---
            self._streak = max(1, self._streak + 1) if self._streak >= 0 else 1

            # Streak bonus: each consecutive positive adds 10% more gain
            streak_bonus = _POS_STREAK_MULT ** (self._streak - 1)
            gain = delta * _RAPPORT_POS_BASE * streak_bonus

            if self.rapport < _RECOVERY_THRESHOLD:
                # Recovery mechanic: rapport is very negative, good answer resets
                # toward zero. NPC thinks "maybe they're onto something."
                self.rapport = self.rapport * (1.0 - _RECOVERY_FACTOR)
                # Still add the normal gain on top of the reset
                self.rapport += gain
            else:
                self.rapport += gain

        elif delta < 0:
            # --- Negative delta ---
            self._streak = min(-1, self._streak - 1) if self._streak <= 0 else -1

            # Streak penalty: each consecutive negative compounds at 50%
            streak_mult = _NEG_STREAK_MULT ** (abs(self._streak) - 1)
            loss = abs(delta) * _RAPPORT_NEG_BASE * streak_mult

            if self.rapport > 0:
                # Had good rapport → erodes modestly (disappointing but not devastating)
                self.rapport -= loss
            else:
                # Already negative → craters faster
                self.rapport -= loss * 1.5

        else:
            # delta == 0 (exact zero, rare) → no rapport change, reset streak
            self._streak = 0

        # Clamp
        self.rapport = max(-_RAPPORT_CAP, min(_RAPPORT_CAP, self.rapport))

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
