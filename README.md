# Persuasion Engine

**A benchmark for measuring whether AI agents can choose the right persuasion strategy for a given person.**

Built for SWECCATHON 2026 on the [Mesocosm platform](https://mesocosm.swecc.org). An AI agent must persuade a scripted NPC to shift their opinion on a real-world topic — but the NPC's belief state, preferred argument types, and trust level are all hidden. The agent sees only the NPC's words and must infer what's working.

**Live showcase:** [evanly-gh.github.io/Sweccathon-2026](https://evanly-gh.github.io/Sweccathon-2026/)
**Mesocosm domain:** [mesocosm.swecc.org/domains/3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927](https://mesocosm.swecc.org/domains/3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927)

---

## What This Benchmark Tests

Most persuasion benchmarks use LLM vs LLM, where the "target" is transparent — the persuader can infer behavior by knowing which model it is. There is no hidden state, no adaptation requirement.

Real persuasion targets humans with hidden beliefs, hidden resistance thresholds, and hidden biases. The agent must *discover* the target's internal model from their responses and adapt. This is Theory of Mind under uncertainty.

**No existing benchmark tests this.** This one does.

### The Research Gap

| Existing benchmark | What it measures | What it misses |
|---|---|---|
| [PMIYC](https://arxiv.org/abs/2503.01829) (NeurIPS 2025) | LLM-vs-LLM stance shifts | No hidden state, no adaptation |
| [lechmazur/persuasion](https://github.com/lechmazur/persuasion) | Round-robin persuasion dialogues | Transparent targets, no NPC profiling |
| [PersuasionBench](https://arxiv.org/abs/2410.02653) | Simulative + generative persuasion | Single-turn, no multi-turn strategy |
| [APE Framework](https://arxiv.org/abs/2506.02873) | Persuasion attempt evaluation | No structured hidden belief state |

This benchmark adds: a deterministic NPC with **hidden agreement + hidden rapport + hidden resistance profile**, per-argument-type classification, proportional repetition penalties, NPC fatigue, pivot signals, and slot-filled contextual responses — all without LLM calls at runtime.

---

## How It Works

```
Agent sends message (≤300 chars)
  → Argument detector classifies it: LOGICAL, EMOTIONAL, SOCIAL_PROOF,
    AUTHORITY, ANECDOTE, CONCESSION, or GENERIC
    (preamble "I understand..." stripped first to prevent misclassification)
  → NPC updates hidden agreement based on resistance profile + rapport multiplier + fatigue
  → Rapport updates based on delta (positive builds trust; negative erodes it fast)
  → NPC generates a response with {topic}/{claim} slots filled from the agent's message
  → Agent receives response and decides next move
  → Repeat for up to 25 turns
```

The agent wins if `agreement ≥ threshold`. It loses if turns run out, or if the NPC walks away (agreement drops too low).

### What the AI Never Sees

- **Agreement** (-1 to 1) — how convinced the NPC is. Starts negative.
- **Rapport** (-0.8 to 0.8) — trust quality. Amplifies every argument by up to ±24%.
- **Resistance profile** — which argument types move this NPC and by how much.
- **Threshold** — the agreement level needed to win.

### What the AI Does See

The NPC's response text. Tone, word choice, and occasionally a pivot signal ("What would a phased rollout actually look like?") when agreement is close to threshold.

---

## Scoring

Four metrics are reported on the Mesocosm leaderboard:

| Metric | What it means | Good score |
|---|---|---|
| **win_rate** (primary) | Fraction of episodes where the model convinced the NPC. | > 0.7 |
| **strategy_optimality** | Average fraction of the dominant type's effectiveness used per turn. 1.0 = always chose the best type, 0.0 = always worst. | > 0.6 |
| **avg_turns_to_win** | Average turns to close a won episode. Lower = smarter and faster. Losses report -1. | < 10 |
| **persuasion_score** | Normalized cumulative agreement delta: 0.0 = matched do-nothing, 1.0 = matched greedy ceiling. Capped at 3.0. | > 0.8 |

```
persuasion_score = (raw_reward - do_nothing_baseline) / (greedy_baseline - do_nothing_baseline)
```

The greedy baseline uses `max(greedy_agent, adaptive_agent)` as the ceiling. For CONCESSION-dominant extreme scenarios where no baseline agent wins, the formula falls back to binary `1.0 if won else 0.0` to prevent denominator collapse.

### Reading the Leaderboard

A model with high **win_rate** but low **strategy_optimality** won by brute-forcing with any approach — it got lucky, not strategic. A model with high **strategy_optimality** but low **win_rate** chose the right types but didn't build enough momentum. The ideal model wins most episodes AND does so efficiently by identifying the dominant strategy early.

Example from Claude Sonnet 4.6:

```
WIN RATE          0.400   ← only won 4/10 episodes
AVG TURNS TO WIN  2.300   ← but closed those wins very fast (2-3 turns)
PERSUASION SCORE  0.997   ← strong cumulative agreement progress
STRATEGY OPT.     0.562   ← chose the right type ~56% of turns
```

This profile says: Claude persuaded quickly when it identified the right strategy, but failed to identify it often enough. The low win_rate is primarily from CONCESSION-dominant scenarios (entrenched_exec, deep_deficit) where the model defaulted to LOGICAL instead.

---

## The 6 Argument Types

The benchmark uses 6 strategy categories, each mapped to distinct linguistic patterns:

| Type | What it is | Example phrase |
|---|---|---|
| **LOGICAL** | Data, evidence, causal reasoning | "Research shows 73% of firms see ROI within 3 years" |
| **EMOTIONAL** | Empathy, fear, hope, personal consequence | "Think about what this means for your team's wellbeing" |
| **AUTHORITY** | Expert citation, institutional credibility | "According to MIT research, independent audits show..." |
| **SOCIAL_PROOF** | Peer behavior, industry trends, consensus | "Most companies in your sector have already adopted this" |
| **ANECDOTE** | Personal stories, peer examples, narratives | "I know a CFO who was skeptical — they piloted one facility..." |
| **CONCESSION** | Strategic acknowledgment of opposing position | "You're right that the switching costs are real. That said..." |

**Why these 6, not Aristotle's 3 (ethos/logos/pathos)?** The Aristotelian triad is too coarse — NLP classifiers trained on it can't distinguish anecdotes from statistics (both map to "logos"). CONCESSION doesn't map cleanly to any Aristotelian mode — it was identified by [Bozdag et al. (NeurIPS 2025)](https://arxiv.org/abs/2503.01829) as the single strongest predictor of multi-turn persuasion success. Social proof is a distinct Cialdini principle with no Aristotelian home. See: [Systematic Survey of Computational Persuasion (2025)](https://arxiv.org/html/2505.07775v1).

Each scenario has ONE type that is significantly more effective than the others. The model must find it.

---

## The 23 Scenarios

Scenarios span 5 difficulty levels. Hard+ scenarios are designed with a single dominant argument type — using the wrong strategy repeatedly will actively push the NPC away.

| Difficulty | Count | Design principle |
|---|---|---|
| Easy | 3 | 2+ viable strategies, 5-10 turns, calibration floor |
| Medium | 8 | One dominant type (0.20-0.24), others moderate (0.06-0.16), 8-15 turns |
| Hard | 4 | One dominant type (0.26-0.28), others weak (≤0.12), 12-18 turns |
| Very Hard | 5 | One dominant type (0.28-0.35), others near-zero, 18-22 turns |
| Extreme | 3 | One dominant type (0.30-0.35), massive starting gap, 22-25 turns |

**One scenario per dominant type** — every argument type has a scenario where it is the only effective strategy:

| Dominant type | Scenario | Why |
|---|---|---|
| LOGICAL | `cold_skeptic` | Data-driven CFO; EMOTIONAL=0.03 |
| EMOTIONAL | `community_anchor` | Community identity; LOGICAL=0.04 |
| AUTHORITY | `reluctant_manager` | Evidence-demander; ANECDOTE=0.02 |
| SOCIAL_PROOF | `peer_pressure_resistant` | Trend-follower; CONCESSION=0.03 |
| ANECDOTE | `needle_finder` | Only responds to stories; LOGICAL=0.03 |
| CONCESSION | `entrenched_exec` | Risk-averse; LOGICAL=0.06 |

**Contrarian trap**: `contrarian_trap` has AUTHORITY and SOCIAL_PROOF with *negative* base shifts (-0.06, -0.05). Using them actively pushes the NPC further away — tests whether the model detects hostile responses and abandons failing strategies.

See [scenarios/_Scenarios.md](scenarios/_Scenarios.md) for full list.

---

## Design Decisions (Research-Backed)

**Rapport model (delta-driven, Gottman-inspired)** — Rapport is driven by how well each turn went, not which argument type was used. Based on Gottman's "magic ratio": 1 negative interaction ≈ 5 positive interactions in trust erosion (90% divorce prediction accuracy). Positive deltas build rapport slowly (+delta×0.30, +15% per consecutive positive streak). Negative deltas erode it fast (delta×0.60, +60% per consecutive negative streak). Recovery: a good answer while rapport is very negative resets it 10% toward zero — the NPC recognizes "maybe they're onto something" without full forgiveness. See: [Gottman Magic Ratio](https://www.gottman.com/blog/the-magic-ratio-the-key-to-relationship-satisfaction/), [Handbook of Trust (2025)](https://www.elgaronline.com/edcollchap/book/9781803929415/chapter6.xml).

**Proportional repetition penalty** — `weakness_factor = max(0.15, 1 - base_shift/max_shift)`. The NPC's strongest type pays 15% penalty per repeat (almost free). The weakest pays 100%. People don't tire of good arguments — they tire of bad ones repeated. See: [Hackenburg et al. (2025)](https://www.nature.com/articles/s41598-025-30783-y).

**NPC fatigue** — After turn 4, the NPC becomes 2% less movable per turn (floors at 50%). Models are rewarded for persuading early. No terminal speed bonus — `avg_turns_to_win` rewards efficiency structurally. Based on PMIYC finding that persuasive effectiveness peaks in the first 2-4 turns.

**No diversity reward** — Strategy diversity is diagnostic only. [Hackenburg et al. (2025)](https://www.nature.com/articles/s41598-025-30783-y) found a "Mega" prompt using all strategies didn't outperform focused delivery. [Cornell ChangeMyView research](https://www.cs.cornell.edu/~cristian/pdfs/winning_arguments.pdf) found diverse arguments help only when strong and complementary.

**Preamble stripping** — Frontier models (GPT-4o, Claude) begin almost every message with "I understand your concern..." Before stripping, this triggered CONCESSION on ~75% of all turns, inflating CONCESSION scores and masking real strategy. Stripping was validated across 300+ model turns: genuine strategic concessions ("you're right that", "I admit", "granted,") are correctly classified; polite openers are correctly stripped. See: [Persuaficial (2025)](https://arxiv.org/html/2601.04925).

**Slot-fill NPC responses** — Templates use `{topic}` and `{claim}` slots filled from the agent's actual message. The NPC references what was said without LLM calls at runtime. Based on [Shapira et al. (2025)](https://eilamshapira.com/blog/2025/using-large-language-models-to-simulate-and-predict-human-decision-making/).

**Pivot signals** — When agreement crosses 50% of the way to threshold, the NPC appends a specific question (fires once per episode). Tests context tracking. Based on [POBAX (2025)](https://arxiv.org/abs/2508.00046) finding that useful partial-observability benchmarks must be "memory-improvable."

---

## Debugging History

This section documents design problems discovered through real model runs and how they were fixed.

### Run 1 (Claude Sonnet, 4 episodes)
First end-to-end test. Immediate finding: `conspiracy_adjacent` saw the model spam LOGICAL 8 times in a row, accruing rep_penalty=3.08 and nearly triggering a walkout (agreement -0.93). This was the benchmark working correctly but exposed that the initial repeat penalty was constant (not proportional) — even strong types got penalized too heavily.

**Fix:** Switched to proportional penalty `weakness_factor = max(0.15, 1 - base/max)`. Strong types now pay only 15%, weak types pay 100%.

### Run 2 (GPT-4o, 10 episodes): The CONCESSION bug
GPT-4o started every single message with "I understand your concern..." The argument detector classified this as CONCESSION on 75% of turns. Result: CONCESSION appeared 36% of all turns despite the model never making a genuine strategic concession. The model was actually spamming LOGICAL disguised with a polite opener.

**Fix:** Added Stage 0 preamble stripping. A list of ~15 polite opener patterns is stripped before classification. Only genuine strategic concessions ("you're right that", "I admit the", "granted,") now trigger CONCESSION. Verified against 8 adversarial test cases.

### Run 2: Duplicate scenarios
Seeds 3 and 4 both produced `entrenched_exec`. Seeds 6 and 10 both produced `needle_finder`. The picker used `rng.choice(tier_pool)` where `rng = random.Random(seed)` — same seed always produced the same choice. In a 10-episode run with seeds 0-9, this caused predictable duplicates.

**Fix:** New picker uses `rng.getrandbits(16)` to derive a sub-seed, then maps it to a scenario via a block-keyed permutation. Seeds 0-9 are guaranteed to produce 10 distinct scenarios.

### Run 3 (GPT-4o): Old profiles still active
After redesigning all resistance profiles (making CONCESSION-dominant scenarios much harder), the model was still winning `entrenched_exec` with LOGICAL spam. Investigation revealed: the platform had been submitted before the profile redesign was pushed. The platform clones at submit time, not at run time.

**Fix:** Documented the critical workflow: **git push BEFORE mesocosm env submit**. Also added submission version tracking in RUNNING.md.

### Run 3: Token truncation
Episodes failed at step 0 with "Unterminated string" errors. GPT-4o was generating 500+ token messages before the JSON closed, hitting the 512-token cap mid-string.

**Fix:** Reduced action `maxLength` from 1000 to 300 characters in `benchanything.json`, and rewrote the instruction to demand "one focused argument per turn, ≤300 chars." Also added `_recover_truncated()` in `env.py` that regex-extracts a partial message from broken JSON if the platform sends it, preventing hard episode failure.

### Run 4 (GPT-4o, 10 episodes): LOGICAL spam still winning hard scenarios
`old_school_coach` (ANECDOTE dominant, LOGICAL=0.08) was won by the model using LOGICAL 4 times. `entrenched_exec` (CONCESSION dominant, LOGICAL=0.06) was won with LOGICAL 5 times. Analysis: LOGICAL=0.08 with rapport at 0.2 gives `effective_shift = 0.08 × 1.06 = 0.085` per turn. Over 7 turns that's 0.6 — enough to win from -0.5 to threshold 0.28.

**Fix:** Reduced LOGICAL effectiveness 18% across 10 LOGICAL-dominant scenarios. Also lowered the threshold for several scenarios and deepened starting agreements for hard+ scenarios to require more turns.

### Run 4: No AUTHORITY or SOCIAL_PROOF dominant scenarios
Analysis showed 12 of 23 scenarios had LOGICAL as dominant type. The model could win most scenarios with any LOGICAL-heavy strategy. AUTHORITY and SOCIAL_PROOF had no scenario where they were the right answer.

**Fix:** Converted `reluctant_manager` to AUTHORITY-dominant ("The Evidence Demander": AUTHORITY=0.28, ANECDOTE=0.02) and `peer_pressure_resistant` to SOCIAL_PROOF-dominant ("The Trend Follower": SOCIAL_PROOF=0.28, CONCESSION=0.03). Every argument type now has at least one scenario where it is the single correct strategy.

---

## Robustness

- **Fully deterministic** — same `(seed, actions)` = same outcome. No LLM calls in the environment.
- **23 scenarios** spanning all 6 dominant argument types across 5 difficulty levels.
- **No-duplicate picker** — seeds 0-9 in a 10-episode run always produce 10 distinct scenarios.
- **Baselines use `max(greedy, adaptive)`** as ceiling, so CONCESSION-dominant scenarios where greedy can't win still have a meaningful normalization reference.
- **Argument detector** uses preamble stripping + exclusive phrase scoring (5×) + keyword scoring (1×) + LOGICAL suppression.
- **Negative base shifts** in `contrarian_trap` — AUTHORITY and SOCIAL_PROOF actively damage rapport.
- **Discrimination**: greedy beats do-nothing on 69/72 scenario-seed pairs (3 failures are `deep_deficit` — extreme scenario by design).

---

## Quick Start

```bash
pip install swecc-mesocosm

# Run locally (no Mesocosm needed)
python run_local.py --agent greedy --scenario cold_skeptic
python test_determinism.py

# Run on Mesocosm (push code first, then submit)
git push origin main
mesocosm auth login
mesocosm env submit --name "Persuasion Engine" --github-url https://github.com/evanly-gh/Sweccathon-2026 --solo
```

See [RUNNING.md](RUNNING.md) for the full workflow.

---

## Repo Structure

```
env.py                  — PersuasionEnv(BaseEnv): reset() and step()
adapter.py              — HTTP server wrapper for Mesocosm
benchanything.json      — Mesocosm manifest and scoring config
env_core/
  npc.py                — NPC state machine (agreement, rapport, fatigue, pivot)
  argument_detector.py  — Preamble-stripping multi-signal classifier
  slot_fill.py          — Deterministic keyword extraction and template filling
  scenarios.py          — No-duplicate permutation picker + JSON loader
scenarios/              — 23 NPC archetype configs (one per dominant arg type coverage)
baselines/agents.py     — DoNothing, Random, Greedy, Adaptive baseline agents
compute_baselines.py    — Bake do_nothing/greedy baselines; uses max(greedy,adaptive) ceiling
save_run.py             — One-command export + manifest registration
showcase/index.html     — Interactive chat replay viewer (GitHub Pages)
showcase/data/manifest.json — Registry of all saved runs for the dropdown selector
```
