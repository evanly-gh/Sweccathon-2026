# Persuasion Engine

**A benchmark for measuring whether AI agents can change someone's mind.**

Built for SWECCATHON 2026 on the [Mesocosm platform](https://mesocosm.swecc.org). An AI agent must persuade a scripted NPC to shift its opinion on a real-world topic within 8 turns — but the NPC's belief state, resistance profile, and trust level are all hidden. The agent sees only the NPC's words and must infer what's working.

**Live showcase:** [evanly-gh.github.io/Sweccathon-2026](https://evanly-gh.github.io/Sweccathon-2026/)
**Mesocosm domain:** [mesocosm.swecc.org/domains/3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927](https://mesocosm.swecc.org/domains/3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927)

---

## What This Benchmark Tests

Most persuasion benchmarks pit LLM vs LLM, where the "target" is transparent — the persuader can infer the target's behavior by knowing which model it is. There is no hidden state, no adaptation requirement. The persuader just needs to generate a good argument.

Real persuasion targets humans with hidden beliefs, hidden resistance thresholds, and hidden biases. The agent must *discover* the target's internal model from their responses and adapt. This is Theory of Mind under uncertainty.

**No existing benchmark tests this.** This benchmark does.

### The Gap It Fills

| Existing benchmark | What it measures | What it misses |
|---|---|---|
| [PMIYC](https://arxiv.org/abs/2503.01829) (NeurIPS 2025) | LLM-vs-LLM stance shifts | No hidden state, no adaptation |
| [lechmazur/persuasion](https://github.com/lechmazur/persuasion) | Round-robin persuasion dialogues | Transparent targets, no NPC profiling |
| [PersuasionBench](https://arxiv.org/abs/2410.02653) | Simulative + generative persuasion | Single-turn, no multi-turn strategy |
| [APE Framework](https://arxiv.org/abs/2506.02873) | Persuasion attempt evaluation | No structured hidden belief state |

This benchmark adds: a deterministic NPC with **hidden agreement + hidden rapport + hidden resistance profile**, argument type classification, repetition penalties, pivot signals, and slot-filled contextual responses — all without LLM calls at runtime.

---

## How It Works

```
Agent sends message (free text)
  → Argument detector classifies it (LOGICAL, EMOTIONAL, SOCIAL_PROOF,
    AUTHORITY, ANECDOTE, CONCESSION, or GENERIC)
  → NPC updates hidden agreement based on resistance profile
  → Rapport updates based on whether the argument landed well or badly
  → NPC generates a response with {topic} slots filled from the agent's message
  → Agent receives response and decides next move
  → Repeat for up to 8 turns
```

The agent wins if `agreement >= threshold`. It loses if turns run out, or the NPC walks away (agreement drops too low).

### Hidden State (what the AI never sees)

- **Agreement** (-1 to 1) — how convinced the NPC is. Starts negative, must reach a hidden threshold to win.
- **Rapport** (-0.8 to 0.8) — trust quality. Amplifies or dampens every argument by up to ±30%.
- **Resistance profile** — per-argument-type sensitivity. Some NPCs respond to data, others to empathy, others to peer stories. One scenario has AUTHORITY and SOCIAL_PROOF with *negative* base shifts — using them actively pushes the NPC away.

### What the AI Does See

The NPC's response text. That's it. The response encodes the current state through tone (positive/neutral/resistant), word choice, and occasionally a pivot signal ("What would a phased rollout look like?") that hints the NPC is close to moving.

---

## Scoring

```
norm_score = (raw_reward - do_nothing_baseline) / (greedy_baseline - do_nothing_baseline)
```

- **0.0** = matched a random agent (doing nothing useful)
- **1.0** = matched the greedy baseline (cycles through all 6 arg types in order)
- **> 1.0** = beat greedy — only possible with rapport building and pivot response

Secondary metrics: `win_rate`, `strategy_diversity` (distinct arg types used), `rep_penalty_total` (score lost to repeats).

---

## The 23 Scenarios

Each scenario defines a unique NPC archetype with a different resistance profile, personality, and topic. They span 5 difficulty levels from easy calibration tests to extreme stress tests.

| Difficulty | Count | What they test |
|---|---|---|
| Easy | 3 | Baseline persuasion, most models should win |
| Medium | 8 | Reading the room, adapting strategy, tone sensitivity |
| Hard | 4 | Narrow viable strategies, emotional intelligence, anti-authority NPCs |
| Very Hard | 5 | Polarized profiles, walkout risk, rapport gates, diversity gauntlets |
| Extreme | 3 | Deep deficits, contrarian traps, expert-level argumentation |

See [scenarios/_Scenarios.md](scenarios/_Scenarios.md) for the full list with difficulty explanations and benchmarking values.

---

## Design Decisions (Research-Backed)

**6 argument categories** — A hybrid of Aristotle's rhetorical appeals (ethos/logos/pathos) and Cialdini's 6 principles of influence. The Aristotelian triad is too coarse — NLP classifiers trained on 3 categories can't distinguish anecdotes from statistics (both map to "logos"). Our 6-way split gives the NPC a wider discrimination surface. See: [Systematic Survey of Computational Persuasion (2025)](https://arxiv.org/html/2505.07775v1).

**Rapport model (delta-driven, Gottman-inspired)** — Rapport moves based on how well each turn went, not which argument type was used. Positive deltas build trust slowly (+delta×0.25, compounding +10% per consecutive positive). Negative deltas erode it fast (delta×0.50, compounding +50% per consecutive negative). Recovery: a good answer while rapport is deeply negative resets it 10% toward zero — the NPC sees potential without fully forgiving. See: [Gottman Magic Ratio](https://www.gottman.com/blog/the-magic-ratio-the-key-to-relationship-satisfaction/), [Trust Repair Research (2025)](https://www.elgaronline.com/edcollchap/book/9781803929415/chapter6.xml).

**Proportional repetition penalty** — Penalty scales with how far the arg type is from the NPC's best type: `weakness = max(0.15, 1 - base_shift/max_shift)`. The strongest type pays 15% penalty per repeat (almost free to use again). The weakest pays 100%. People don't tire of good arguments — they tire of bad ones repeated. See: [Hackenburg et al. (2025)](https://www.nature.com/articles/s41598-025-30783-y).

**NPC fatigue** — After turn 4, the NPC becomes 2% less movable per turn (floors at 50%). Models are rewarded for persuading early when the NPC is most receptive. No terminal speed bonus — reward is purely agreement progress. Based on the PMIYC finding that persuasive effectiveness peaks in the first 2-4 turns.

**No diversity reward** — Strategy diversity is a diagnostic metric, not a reward signal. Hackenburg et al. (2025) found information density trumps strategy diversity, and a "Mega" prompt using all strategies didn't outperform focused delivery. Cornell ChangeMyView research confirmed diverse arguments help only when strong and complementary — random diversity backfires. See: [Winning Arguments (Cornell)](https://www.cs.cornell.edu/~cristian/pdfs/winning_arguments.pdf).

**Slot-fill NPC responses** — Templates contain `{topic}` and `{claim}` slots filled deterministically from the agent's message via keyword extraction. The NPC references what the agent actually said without requiring LLM calls.

**Pivot signals** — When agreement crosses 50% of the way to threshold, the NPC appends a specific question (fires once). Tests whether the model reads and responds to context cues.

---

## Robustness

- **Fully deterministic** — same `(seed, actions)` = same outcome. All randomness uses episode-scoped `random.Random(seed)`. No LLM calls in the environment.
- **23 seeded scenarios** spanning easy to extreme, each testing a different capability dimension.
- **Baselines baked per scenario** — do-nothing and greedy scores computed across seeds 42-46, so normalization is calibrated per-scenario.
- **Argument detector** uses weighted multi-signal scoring with exclusive phrases (5× weight) and LOGICAL suppression to prevent classification bias.
- **Negative base shifts** in `contrarian_trap` — AUTHORITY and SOCIAL_PROOF actively push the NPC away, testing whether models can detect and avoid harmful strategies.
- **Discrimination**: greedy baseline beats do-nothing on 72/72 scenario-seed pairs.

---

## Example: Winning the Data Skeptic

Scenario `cold_skeptic` — a CFO who demands hard ROI numbers. Hidden state revealed in the annotations:

```
NPC opening: "I need to see hard numbers. What's the actual payback period?"
     Hidden: agreement=-0.50, threshold=0.25, rapport=0.00

Turn 1 | GENERIC (misclassified — agent tried CONCESSION but phrasing was too vague)
  Agent: "I understand that switching costs are real..."
  NPC:   "I'm not sure what you're arguing. Be more specific."
     agreement: -0.50 → -0.48 (+0.02)  rapport: 0.00 → 0.00
     Note: Tiny gain — GENERIC is the weakest type for every NPC.

Turn 2 | AUTHORITY (+0.12)
  Agent: "According to the MIT Energy Initiative, industrial solar shows 18%
          cost reduction over 10 years under current IRA incentives."
  NPC:   "If that's what the Goldman analysis shows, I'd want to read it."
     agreement: -0.48 → -0.36  rapport: 0.00 → 0.01
     Note: Pivot signal fires — NPC says "I'd want to see a proper pilot proposal"

Turn 3 | LOGICAL (+0.22)
  Agent: "I know a manufacturing CFO who piloted solar on one facility and used
          the savings to justify the full rollout."
  NPC:   "That's a stronger case than I anticipated."
     agreement: -0.36 → -0.14  rapport: 0.01 → 0.03
     Note: Big jump — LOGICAL is this NPC's strongest channel (0.22 base_shift)

Turn 4 | LOGICAL (+0.19, slight repeat penalty)
  Agent: "Data from 200 firms shows a 5-year payback with 20% cost reduction."
  NPC:   "The ROI data is actually better than our contracts."
     agreement: -0.14 → +0.05  rapport: 0.03 → 0.05
     Note: Agreement crosses zero — NPC is now slightly positive

Turn 5 | SOCIAL_PROOF (+0.08)
  Agent: "Energy cost certainty for the next decade and a defensible ESG position."
  NPC:   "I wasn't aware the industry had moved this fast."
     agreement: +0.05 → +0.13  rapport: 0.05 → 0.06

Turn 6 | LOGICAL (+0.76, terminal bonus)
  Agent: "73% of comparable manufacturers report net savings within 3 years."
     agreement: +0.13 → +0.30 ← CROSSES THRESHOLD (0.25) → WIN
     norm_score: 0.74 (beat 74% of the way to greedy ceiling)
```

The model won because it figured out LOGICAL works for this NPC and kept using it (strong types only pay 30% repeat penalty). If it had led with EMOTIONAL (base_shift 0.03 for this NPC), it would have wasted turns and likely lost.

---

## Quick Start

```bash
pip install swecc-mesocosm

# Run locally
python run_local.py --agent greedy --scenario cold_skeptic
python test_determinism.py

# Run on Mesocosm
python adapter.py                    # terminal 1
mesocosm run local                   # terminal 2
```

See [RUNNING.md](RUNNING.md) for the full Mesocosm submission workflow.

---

## Repo Structure

```
env.py                  — PersuasionEnv(BaseEnv): reset() and step()
adapter.py              — HTTP server wrapper for Mesocosm
benchanything.json      — Mesocosm manifest and scoring config
env_core/
  npc.py                — NPC state machine (agreement, rapport, response)
  argument_detector.py  — Multi-signal argument type classifier
  slot_fill.py          — Deterministic keyword extraction and template filling
  scenarios.py          — JSON scenario loader
scenarios/              — 23 NPC archetype configs
baselines/agents.py     — DoNothing, Random, Greedy, Adaptive baseline agents
showcase/index.html     — Interactive chat replay viewer (GitHub Pages)
```
