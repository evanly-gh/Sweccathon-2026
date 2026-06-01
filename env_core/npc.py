"""
NPC state machine — deterministic, no LLM calls.

Hidden state:
  agreement  — how convinced the NPC is (-1 to 1). Win when >= threshold.
  rapport    — trust quality of the interaction (-0.8 to 0.8).

=== AGREEMENT FORMULA ===

  effective_shift = base_shift × rapport_multiplier × fatigue - repeat_penalty
  agreement += max(effective_shift, -0.06)

  Where:
    base_shift        = resistance_profile[arg_type]  (how much this NPC responds to this type)
    rapport_multiplier = 1 + rapport × 0.30           (trust amplifies/dampens by up to ±30%)
    fatigue           = gradual decay after turn 4     (2% per turn, floors at 50%)
    repeat_penalty    = rep_penalty × repeats × weakness_factor

  Fatigue rationale: people become less movable the longer a conversation
  goes. Early turns are the most effective. Based on PMIYC finding that
  persuasive effectiveness is highest in the first 2-4 turns.

=== REPEAT PENALTY (proportional to weakness) ===

  weakness_factor = max(0.15, 1 - base_shift / max_shift_for_this_NPC)

  The NPC's strongest arg type pays only 15% penalty per repeat (almost free).
  The weakest pays up to 100%. Rationale: people don't tire of hearing good
  arguments (Hackenburg et al. 2025 — information density trumps diversity).
  They tire of hearing bad ones repeated.

  Example (cold_skeptic, max_shift=0.22, rep_penalty=0.10):
    LOGICAL (0.22):   weakness=0.15 → repeat 1 costs 0.015, repeat 2 costs 0.030
    EMOTIONAL (0.03):  weakness=0.86 → repeat 1 costs 0.086, repeat 2 costs 0.172

=== RAPPORT (delta-driven, Gottman-inspired) ===

  Rapport moves based on how well each turn went (the delta), not which
  argument type was used. Trust comes from consistent positive engagement.

  Four quadrants:
    Good answer + good rapport  → rapport up modestly      (steady deposits)
    Bad answer  + good rapport  → rapport down modestly    (good will erodes)
    Good answer + bad rapport   → rapport partial recovery (NPC sees potential)
    Bad answer  + bad rapport   → rapport craters          (compounding distrust)

  Positive streaks: each consecutive positive adds 10% more rapport gain.
  Negative streaks: each consecutive negative compounds at 50% more loss.
  This models Gottman's 5:1 ratio — negatives are disproportionately damaging.

  Recovery: when rapport < -0.3 and the agent gives a positive delta,
  rapport resets 10% toward zero before adding normal gain. The NPC
  recognizes "maybe they're onto something" without fully forgiving.
  Based on trust repair research (Handbook of Trust, 2025).

=== PIVOT SIGNAL ===

  When agreement crosses pivot_threshold (halfway to the win threshold),
  the NPC appends a realistic question to their response (fires once).
  Tests whether the agent reads and responds to specific context cues.
"""

from __future__ import annotations

import random
from env_core.slot_fill import fill_slots

# ── Rapport constants ──
_RAPPORT_CAP = 0.8
_RAPPORT_POS_BASE = 0.30       # reach rapport ~0.4 in 4-5 good turns (more impactful amplification)
_RAPPORT_NEG_BASE = 0.60       # crash to ~-0.35 in 2-3 bad turns (sharper Gottman asymmetry)
_POS_STREAK_MULT = 1.15        # +15% rapport gain per consecutive positive (more compounding)
_NEG_STREAK_MULT = 1.6         # +60% rapport loss per consecutive negative (faster cascade)
_RECOVERY_THRESHOLD = -0.3     # rapport must be this negative to trigger recovery
_RECOVERY_FACTOR = 0.10        # rapport resets 10% toward zero on recovery

# ── Agreement constants ──
_RAPPORT_AMPLIFY_MAX = 0.30    # rapport=+0.8 → +24% to base_shift
_MIN_WEAKNESS = 0.15           # even the strongest arg type pays 15% repeat penalty
_FATIGUE_START = 4             # fatigue begins after this turn
_FATIGUE_RATE = 0.02           # 2% effectiveness loss per turn past start
_FATIGUE_FLOOR = 0.50          # NPC never drops below 50% effectiveness


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
        self._turn_number: int = 0

        self._pivot_threshold: float = config.get("pivot_threshold", 0.0)
        self._pivot_fired: bool = False

    # ────────────────────────────────────────────────────────────────
    # MAIN UPDATE — called once per agent turn
    # ────────────────────────────────────────────────────────────────
    def update(self, arg_type: str, agent_message: str = "") -> tuple[float, str, float]:
        """Returns (agreement_delta, npc_response_text, rapport_after)."""
        self._turn_number += 1

        # ── Step 1: Compute agreement delta ──────────────────────

        # How much does this NPC respond to this argument type?
        base_shift = self.profile.get(arg_type, 0.04)
        repeats = self.rep_counts.get(arg_type, 0)

        # Proportional repeat penalty:
        #   weakness_factor = how far this type is from the NPC's best type
        #   Strong types (close to max) → low penalty (15% floor)
        #   Weak types (far from max) → high penalty (up to 100%)
        max_shift = max(self.profile.values()) if self.profile else 0.20
        weakness_factor = 1.0 - (base_shift / max_shift) if max_shift > 0 else 1.0
        weakness_factor = max(_MIN_WEAKNESS, weakness_factor)
        repeat_pen = self.rep_penalty * repeats * weakness_factor

        # Rapport amplification: trust makes every argument land harder
        rapport_multiplier = 1.0 + self.rapport * _RAPPORT_AMPLIFY_MAX

        # NPC fatigue: people become less movable the longer a conversation goes.
        # Turns 1-4: full effectiveness. After that, 2% decay per turn (floor 50%).
        fatigue = 1.0
        if self._turn_number > _FATIGUE_START:
            fatigue = max(_FATIGUE_FLOOR,
                          1.0 - _FATIGUE_RATE * (self._turn_number - _FATIGUE_START))

        # Final delta: base × rapport × fatigue - repeat penalty
        # Clamped at -0.06 so a single bad turn can't crater agreement
        effective_shift = base_shift * rapport_multiplier * fatigue - repeat_pen
        delta = max(effective_shift, -0.06)

        # Apply to agreement (clamped -1 to 1)
        self.agreement = min(1.0, max(-1.0, self.agreement + delta))
        self.rep_counts[arg_type] = repeats + 1

        # NPC walks out if pushed too far negative
        if self.agreement <= self._close_threshold:
            self.closed = True

        # ── Step 2: Update rapport based on this turn's delta ────
        self._update_rapport(delta)

        # ── Step 3: Generate NPC response text ───────────────────
        response = self._pick_response(arg_type, delta, agent_message)

        # ── Step 4: Pivot signal (fires once when agreement is halfway) ──
        if not self._pivot_fired and self._pivot_threshold > 0:
            # Check if agreement has crossed the pivot level
            # pivot_level = threshold - pivot_threshold × (threshold - (-1))
            # i.e. halfway between -1.0 and the win threshold
            pivot_level = self.agreement >= (
                self.threshold - self._pivot_threshold * (self.threshold - -1.0)
            )
            if pivot_level and not self.won:
                pivot_line = self._get_pivot_line()
                if pivot_line:
                    response = response + " " + pivot_line
                    self._pivot_fired = True

        return delta, response, self.rapport

    # ────────────────────────────────────────────────────────────────
    # RAPPORT UPDATE — 4 quadrants + streaks + recovery
    # ────────────────────────────────────────────────────────────────
    def _update_rapport(self, delta: float) -> None:
        if delta > 0:
            # ── Positive delta: trust deposits ──
            # Track consecutive positives (reset streak if switching from negatives)
            self._streak = max(1, self._streak + 1) if self._streak >= 0 else 1

            # Each consecutive positive adds 10% more gain (slow compounding)
            streak_bonus = _POS_STREAK_MULT ** (self._streak - 1)
            gain = delta * _RAPPORT_POS_BASE * streak_bonus

            if self.rapport < _RECOVERY_THRESHOLD:
                # Recovery: rapport is deeply negative but agent gave a good answer.
                # Reset rapport 10% toward zero — "maybe they're onto something" —
                # then add normal gain on top.
                self.rapport = self.rapport * (1.0 - _RECOVERY_FACTOR)
                self.rapport += gain
            else:
                # Normal case: add gain
                self.rapport += gain

        elif delta < 0:
            # ── Negative delta: trust withdrawals ──
            # Track consecutive negatives
            self._streak = min(-1, self._streak - 1) if self._streak <= 0 else -1

            # Each consecutive negative compounds at 50% (fast erosion)
            streak_mult = _NEG_STREAK_MULT ** (abs(self._streak) - 1)
            loss = abs(delta) * _RAPPORT_NEG_BASE * streak_mult

            if self.rapport > 0:
                # Good rapport eroding: disappointing but not devastating
                self.rapport -= loss
            else:
                # Already bad: craters 1.5x faster (compounding distrust)
                self.rapport -= loss * 1.5

        else:
            # Exact zero delta (rare): no change, reset streak
            self._streak = 0

        self.rapport = max(-_RAPPORT_CAP, min(_RAPPORT_CAP, self.rapport))

    # ────────────────────────────────────────────────────────────────
    # RESPONSE GENERATION — template selection + slot fill
    # ────────────────────────────────────────────────────────────────
    def _pick_response(self, arg_type: str, delta: float, agent_message: str = "") -> str:
        # Tone is determined by delta magnitude:
        #   > 0.08 = positive (NPC is warming up)
        #   > 0.00 = neutral  (NPC acknowledges but isn't moved much)
        #   <= 0.0 = resistant (NPC pushes back)
        if delta > 0.08:
            tone = "positive"
        elif delta > 0.0:
            tone = "neutral"
        else:
            tone = "resistant"

        # Try type-specific pool first, fall back to GENERIC, then hardcoded
        pool = (
            self._templates.get(arg_type, {}).get(tone)
            or self._templates.get("GENERIC", {}).get(tone)
            or ["I hear you, but I'm not fully convinced yet."]
        )

        # Pick deterministically via seeded RNG, then fill {topic}/{claim} slots
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
