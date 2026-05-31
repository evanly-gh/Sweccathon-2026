# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**Persuasion Engine** — a SWECCATHON 2026 benchmark for the [Mesocosm platform](https://mesocosm.swecc.org). An AI agent must change a scripted NPC's mind on a real-world topic within 8 turns. The NPC has a **hidden belief state and resistance profile** — the agent must infer which of 6 argument types (EMOTIONAL, LOGICAL, SOCIAL_PROOF, AUTHORITY, ANECDOTE, CONCESSION) work from the NPC's reply language, and avoid repeating them (each repeat incurs a growing penalty). Tests Theory of Mind under partial observability.

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

# Start the HTTP adapter (terminal 1) + local Mesocosm run (terminal 2)
python adapter.py
mesocosm run local --manifest benchanything.json --env-url http://localhost:8765

# Submit to Mesocosm platform
mesocosm auth login
mesocosm env submit --name "Persuasion Engine" --github-url https://github.com/evanly-gh/Sweccathon-2026 --solo
mesocosm env list   # wait for "ready", note domain_id
mesocosm run create --domain DOMAIN_ID --vow-version 1.0.0 --model gemini/gemini-3.1-flash-lite --episodes 8 --visibility gallery_public --solo
mesocosm run export RUN_ID -o showcase/data/replay.json
```

Install: `pip install swecc-mesocosm` (provides `bench_common`, `fastapi`, `uvicorn`).

## Architecture

### Data flow per turn

```
agent message (str)
  → argument_detector.detect()       # keyword scoring → one of 7 arg types
  → NPC.update(arg_type)             # hidden state update → (delta, response_text)
  → PersuasionEnv.step()             # reward, norm_score, termination
  → StepResult(observation, reward, terminated, info)
```

### Key files

**`env.py`** — `PersuasionEnv(BaseEnv)`. `reset(seed, scenario)` picks a scenario and initialises the NPC. `step(action)` extracts the message, classifies it, updates the NPC, computes reward and `norm_score`, and returns `StepResult`. **All `info` dict values must be strings** (Mesocosm platform constraint).

**`env_core/npc.py`** — `NPC` class. Holds hidden `agreement` float (−1 to 1), `threshold` (win condition), per-arg-type `resistance_profile` (base shift magnitudes), and `repetition_penalty`. `update(arg_type)` computes `delta = base_shift - (penalty × repeats)`, clamps agreement, and picks a response template by tone (`positive/neutral/resistant` based on delta size). No LLM calls — fully deterministic given the seeded `random.Random`.

**`env_core/argument_detector.py`** — `detect(message)` keyword scorer. Returns the arg type with the most keyword hits; falls back to `GENERIC`. GENERIC gets the lowest base_shift across all NPC profiles, so vague outputs are penalised naturally.

**`env_core/scenarios.py`** — loads and caches JSON configs from `scenarios/`. `get_scenario(name, rng)` returns a config dict or picks randomly.

**`scenarios/*.json`** — one file per NPC archetype. Each defines: `starting_agreement`, `threshold`, `repetition_penalty`, `resistance_profile` (per arg type → float), `response_templates` (per arg type → per tone → list of strings), and baked `do_nothing_baseline` / `greedy_baseline` (set by `compute_baselines.py --bake`).

**`adapter.py`** — thin wrapper: `serve(PersuasionEnv, host, port)`. Must be at repo root (Mesocosm clones the repo and runs it from root).

**`benchanything.json`** — Mesocosm manifest. Scoring metrics use `terminal_field` pointing to `info` keys: `norm_score`, `won`, `diversity`, `rep_penalty_total`.

### Scoring

`norm_score = (raw_reward - do_nothing_baseline) / (greedy_baseline - do_nothing_baseline)`

- 0 = matched do-nothing, 1.0 = matched greedy ceiling, >1.0 = beat greedy.
- Terminal win bonus: `+0.5 + 0.05 × turns_remaining`.
- Baselines are pre-computed per scenario across seeds 42–46 and stored in the scenario JSON.

### Adding a new scenario

1. Copy any existing `scenarios/*.json`, give it a new `id` and `display_name`.
2. Tune `starting_agreement`, `threshold`, `resistance_profile` weights, and `response_templates`.
3. Run `python compute_baselines.py --bake` to update `do_nothing_baseline` and `greedy_baseline`.

### Design Decisions (research-backed)

**6 argument categories** — Hybrid of Aristotle's rhetorical appeals (ethos/logos/pathos) and Cialdini's 6 principles of influence. Pure Aristotle (3 categories) is too coarse — NLP classifiers trained on the triad can't distinguish anecdotes from statistics (both map to "logos"). Our 6-way split gives the NPC a wider discrimination surface. CONCESSION is separated because Bozdag et al. (NeurIPS 2025, PMIYC) found it was the single strongest predictor of multi-turn persuasion success — collapsing it into "ethos" hides the signal. Social proof doesn't cleanly map to any Aristotelian mode. See: [Systematic Survey of Computational Persuasion (2025)](https://arxiv.org/html/2505.07775v1), [Cross-Domain Persuasion Detection (ACL 2025)](https://aclanthology.org/2025.starsem-1.30.pdf).

**Rapport model (delta-driven, negativity-biased)** — Based on Gottman's "magic ratio" research: 1 negative interaction ≈ 5 positive interactions in trust erosion (predicted divorce with 90% accuracy). Negativity bias is one of the most replicated findings in psychology (Rozin & Royzman, 2001). Our rapport model: positive deltas raise rapport slowly (+delta×0.15, max 0.8), negative deltas drop it faster (delta×0.4, compounding after 2+ consecutive negatives). This matches Gottman's "emotional bank account" — deposits are small and steady, withdrawals are large and cascading. See: [Gottman Magic Ratio](https://www.gottman.com/blog/the-magic-ratio-the-key-to-relationship-satisfaction/), [Negativity Bias (Rozin & Royzman)](https://journals.sagepub.com/doi/10.1207/S15327957PSPR0504_2).

**Repeat penalty (conditional)** — Strong argument types (base_shift ≥ 0.10) incur only 30% of the normal repeat penalty. Weak types (< 0.10) get full penalty. Rationale: people don't tire of hearing good arguments — they tire of hearing bad ones repeated. Validated by the PMIYC finding that persuasive effectiveness decays only when new strategy is not introduced, not when effective strategy continues.

**Slot-fill NPC responses** — Templates contain `{topic}` and `{claim}` slots filled deterministically from the agent's message via keyword extraction. This makes the NPC feel responsive without introducing LLM non-determinism. Based on Shapira et al. (2025) finding that LLMs as data generators for small models outperform LLMs as direct classifiers. See: [Using LLMs to Simulate Human Decision-Making](https://eilamshapira.com/blog/2025/using-large-language-models-to-simulate-and-predict-human-decision-making/).

**Pivot signal** — When agreement crosses 50% of the way to threshold, the NPC appends a specific question (fires once). Models that detect and respond to it score higher. Based on POBAX (2025) finding that useful partial-observability benchmarks must be "memory-improvable" — agents with better state tracking should demonstrably outperform agents without it. See: [POBAX: Benchmarking Partial Observability in RL](https://arxiv.org/abs/2508.00046).

### Determinism constraint

All randomness must use the episode-scoped `random.Random(seed)` instance — never `random.random()`, `time`, or global RNG. Same `(seed, actions)` sequence must replay identically. `test_determinism.py` asserts this.

### Showcase

`showcase/index.html` is a self-contained vanilla JS replay viewer. It reads `showcase/data/replay.json` (exported via `mesocosm run export`) or falls back to demo data. Deployed to GitHub Pages via `.github/workflows/pages.yml` from the `showcase/` folder.
Live URL: `https://evanly-gh.github.io/Sweccathon-2026/`
