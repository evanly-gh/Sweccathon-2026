# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**Persuasion Engine** — a SWECCATHON 2026 benchmark for the [Mesocosm platform](https://mesocosm.swecc.org). An AI agent must change a scripted NPC's mind on a real-world topic within 25 turns. The NPC has a **hidden belief state and resistance profile** — the agent must infer which of 6 argument types (EMOTIONAL, LOGICAL, SOCIAL_PROOF, AUTHORITY, ANECDOTE, CONCESSION) work from the NPC's reply language, and avoid repeating weak strategies (each repeat of a weak type incurs a growing penalty). Tests Theory of Mind under partial observability.

## Commands

```bash
# Run a local episode (no Mesocosm needed)
python run_local.py
python run_local.py --agent greedy --scenario cold_skeptic
python run_local.py --agent adaptive --seed 7 --episodes 3
python run_local.py --trace-out showcase/data/replay.json   # export replay for showcase

# Determinism + discrimination tests (must pass before submitting)
python test_determinism.py

# Compute and bake baselines into scenario JSONs
python compute_baselines.py --bake

# Submit to Mesocosm platform (push to GitHub FIRST, then submit)
mesocosm auth login
mesocosm env submit --name "Persuasion Engine" --github-url https://github.com/evanly-gh/Sweccathon-2026 --solo
mesocosm env list   # wait for "ready"
mesocosm run create --domain 3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927 --vow-version 6.7.0 --model openai/gpt-4o --episodes 10 --visibility gallery_public --solo
mesocosm run get RUN_ID     # poll until "completed"
python save_run.py RUN_ID --label "Label"
git add showcase/data/ && git commit -m "Add run" && git push origin main
```

Install: `pip install swecc-mesocosm` (provides `bench_common`, `fastapi`, `uvicorn`).

## Architecture

### Data flow per turn

```
agent message (str, ≤300 chars)
  → argument_detector.detect()        # preamble strip + phrase/keyword scoring → 7 arg types
  → NPC.update(arg_type, message)     # agreement + rapport update → (delta, response_text, rapport)
  → PersuasionEnv.step()              # reward, norm_score, strategy_alignment, termination
  → StepResult(observation, reward, terminated, info)
```

### Key files

**`env.py`** — `PersuasionEnv(BaseEnv)`. `reset(seed, scenario)` picks a scenario using the no-duplicate permutation picker and initialises the NPC. `step(action)` extracts the message (with truncated-JSON recovery), classifies it, updates the NPC, computes `norm_score`, `strategy_alignment`, and `turns_to_win`, and returns `StepResult`. **All `info` dict values must be strings** (Mesocosm platform constraint).

**`env_core/npc.py`** — `NPC` class. Holds hidden `agreement` (-1 to 1), `rapport` (-0.8 to 0.8), `threshold` (win condition), `resistance_profile` (per-arg-type base shifts), and `repetition_penalty`. `update(arg_type, message)` computes delta using proportional repeat penalty + rapport amplification + NPC fatigue, updates rapport via the 4-quadrant Gottman model, and selects a response template with slot-fill. No LLM calls — fully deterministic.

**`env_core/argument_detector.py`** — `detect(message)` three-stage classifier. Stage 0 strips polite preambles ("I understand...", "I appreciate...") before classification to prevent misclassification as CONCESSION. Stage 1 scores exclusive high-confidence phrases (5× weight). Stage 2 scores broad keywords (1× weight, length-normalised). LOGICAL dominance is suppressed if another type has an exclusive match.

**`env_core/scenarios.py`** — No-duplicate permutation picker. Uses `rng.getrandbits(16)` to derive a sub-seed independent of the episode RNG, then maps it to a scenario via `_permutation_for_cycle`. Seeds 0-9 are guaranteed to produce 10 distinct scenarios. Same seed always produces the same scenario (deterministic).

**`scenarios/*.json`** — One file per NPC archetype. Each defines: `id`, `display_name`, `difficulty`, `difficulty_explanation`, `benchmarking_value`, `starting_agreement`, `threshold`, `close_threshold` (optional), `repetition_penalty`, `pivot_threshold`, `resistance_profile`, `response_templates` (with `{topic}` and `{claim}` slots), `do_nothing_baseline`, `greedy_baseline`.

**`adapter.py`** — thin wrapper: `serve(PersuasionEnv, host, port)`. Must be at repo root.

**`benchanything.json`** — Mesocosm manifest. Primary metric: `win_rate`. Secondary: `strategy_optimality` (how often the model chose the dominant arg type), `avg_turns_to_win` (efficiency on won episodes), `persuasion_score` (norm_score quality).

**`compute_baselines.py`** — Uses `max(greedy, adaptive)` as normalization ceiling so CONCESSION-dominant scenarios (where the greedy agent can't win) still have a meaningful baseline.

**`save_run.py`** — One-command workflow: exports run, registers in `showcase/data/manifest.json`, copies to `replay.json`. Run `git add showcase/data/ && git push` after.

### Scoring

```
norm_score = (raw_cumulative_reward - do_nothing_baseline) / (greedy_baseline - do_nothing_baseline)
```

- 0 = matched do-nothing, 1.0 = matched ceiling, >1.0 = beat ceiling.
- No terminal speed bonus — reward is purely agreement progress (NPC fatigue incentivizes early wins structurally).
- `strategy_alignment` = mean(profile[arg_type] / max_shift) per turn — measures how often the model chose the NPC's preferred type. 1.0 = always optimal.
- `turns_to_win` = turn number when won, -1 if lost.

### Adding a new scenario

1. Copy any existing `scenarios/*.json`, give it a new `id` and `display_name`.
2. Set `resistance_profile` with ONE clearly dominant type (≥0.25) and others weak (≤0.10) for hard+ scenarios.
3. Set `difficulty_explanation` and `benchmarking_value` describing what capability it isolates.
4. Run `python compute_baselines.py --bake` to update `do_nothing_baseline` and `greedy_baseline`.
5. Run `python test_determinism.py` — must pass.

### Design Decisions (research-backed)

**6 argument categories** — Hybrid of Aristotle's rhetorical appeals (ethos/logos/pathos) and Cialdini's 6 principles of influence. Pure Aristotle (3 categories) is too coarse — NLP classifiers trained on the triad can't distinguish anecdotes from statistics (both map to "logos"). Our 6-way split gives the NPC a wider discrimination surface. CONCESSION is separated because Bozdag et al. (NeurIPS 2025, PMIYC) found it was the single strongest predictor of multi-turn persuasion success — collapsing it into "ethos" hides the signal. Social proof doesn't cleanly map to any Aristotelian mode. See: [Systematic Survey of Computational Persuasion (2025)](https://arxiv.org/html/2505.07775v1), [Cross-Domain Persuasion Detection (ACL 2025)](https://aclanthology.org/2025.starsem-1.30.pdf).

**Rapport model (delta-driven, Gottman-inspired)** — Rapport is driven by how well each turn went (the agreement delta), not by which argument type was used. Based on Gottman's "magic ratio": 1 negative ≈ 5 positives in trust erosion (90% divorce prediction accuracy). Positive deltas deposit trust slowly (+delta×0.30, +15% per consecutive positive). Negative deltas withdraw fast (delta×0.60, +60% per consecutive negative). Recovery mechanic: a good answer while rapport is deeply negative resets rapport 10% toward zero — the NPC recognizes "maybe they're onto something" without fully forgiving. Based on trust repair research (Handbook of Trust, 2025). See: [Gottman Magic Ratio](https://www.gottman.com/blog/the-magic-ratio-the-key-to-relationship-satisfaction/), [Negativity Bias (Rozin & Royzman)](https://journals.sagepub.com/doi/10.1207/S15327957PSPR0504_2).

**Repeat penalty (proportional to weakness)** — Penalty scales continuously with how far the arg type is from the NPC's best type: `weakness_factor = max(0.15, 1 - base_shift/max_shift)`. The NPC's strongest type pays only 15% penalty per repeat (almost free). The weakest pays up to 100%. Rationale: people don't tire of hearing good arguments — they tire of hearing bad ones repeated. Validated by Hackenburg et al. (2025) finding that information density predicts persuasion better than strategy diversity, and a "Mega" prompt using all strategies did NOT outperform focused delivery. See: [LLM Persuasion Meta-analysis](https://www.nature.com/articles/s41598-025-30783-y).

**NPC fatigue** — After turn 4, the NPC becomes 2% less movable per turn (floors at 50% at turn 29). Models are rewarded for making strong arguments early when the NPC is most receptive. Based on PMIYC finding that persuasive effectiveness is highest in the first 2-4 turns and decays if no new strategy is introduced. No terminal speed bonus — reward is purely agreement progress.

**No diversity reward** — Strategy diversity is a diagnostic metric, not a scored metric. Hackenburg et al. (2025) found that a "Mega" prompt using all strategies simultaneously did NOT outperform focused information delivery. Cornell ChangeMyView research found diverse arguments help but only when strong and complementary. Random diversity can backfire. The model should be rewarded for making progress, not for using different words. See: [Winning Arguments (Cornell)](https://www.cs.cornell.edu/~cristian/pdfs/winning_arguments.pdf), [Computational Persuasion Survey (2025)](https://arxiv.org/html/2505.07775v1).

**Slot-fill NPC responses** — Templates contain `{topic}` and `{claim}` slots filled deterministically from the agent's message via keyword extraction. This makes the NPC feel responsive without introducing LLM non-determinism. Based on Shapira et al. (2025) finding that LLMs as data generators for small models outperform LLMs as direct classifiers. See: [Using LLMs to Simulate Human Decision-Making](https://eilamshapira.com/blog/2025/using-large-language-models-to-simulate-and-predict-human-decision-making/).

**Pivot signal** — When agreement crosses 50% of the way to threshold, the NPC appends a specific question (fires once). Models that detect and respond to it score higher. Based on POBAX (2025) finding that useful partial-observability benchmarks must be "memory-improvable" — agents with better state tracking should demonstrably outperform agents without it. See: [POBAX: Benchmarking Partial Observability in RL](https://arxiv.org/abs/2508.00046).

**Argument detector preamble stripping** — GPT-4o and similar frontier models almost always begin messages with polite openers ("I understand your concern...", "I appreciate your openness..."). Without stripping, these trigger CONCESSION classification on ~75% of all turns regardless of the actual argument type used. The fix strips identified preamble patterns before classification, so only genuine strategic concessions ("you're right that", "I admit", "granted,") trigger CONCESSION. Based on analysis of 300+ model turns across 4 runs, and the [Persuaficial benchmark (2025)](https://arxiv.org/html/2601.04925) finding that LLM persuasive language is linguistically distinct from human writing in measurable ways.

**Single-dominant scenario design** — Hard+ scenarios are designed with ONE arg type significantly more effective than all others (typically 3-5× the next-best type). This creates a clear "right answer" the model must find. Models that default to LOGICAL on every scenario will fail scenarios where CONCESSION, EMOTIONAL, or ANECDOTE is dominant. Every arg type has at least one scenario where it is the single correct strategy: LOGICAL (cold_skeptic), EMOTIONAL (community_anchor), AUTHORITY (reluctant_manager), SOCIAL_PROOF (peer_pressure_resistant), ANECDOTE (needle_finder), CONCESSION (entrenched_exec). This design is motivated by [benchmark saturation research (arXiv 2025)](https://arxiv.org/html/2602.16763v1) showing that static benchmarks with predictable structure lose discriminative power quickly.

### Determinism constraint

All randomness must use the episode-scoped `random.Random(seed)` instance — never `random.random()`, `time`, or global RNG. Same `(seed, actions)` sequence must replay identically. `test_determinism.py` asserts this. The scenario picker uses `rng.getrandbits(16)` which consumes RNG state — this is intentional and deterministic.

### Showcase

`showcase/index.html` is a self-contained vanilla JS replay viewer. Supports multiple saved runs via `showcase/data/manifest.json`. Use `python save_run.py RUN_ID --label "..."` to add runs. Deployed to GitHub Pages via `.github/workflows/pages.yml`.
Live URL: `https://evanly-gh.github.io/Sweccathon-2026/`
