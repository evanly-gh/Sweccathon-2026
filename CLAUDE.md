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

### Determinism constraint

All randomness must use the episode-scoped `random.Random(seed)` instance — never `random.random()`, `time`, or global RNG. Same `(seed, actions)` sequence must replay identically. `test_determinism.py` asserts this.

### Showcase

`showcase/index.html` is a self-contained vanilla JS replay viewer. It reads `showcase/data/replay.json` (exported via `mesocosm run export`) or falls back to demo data. Deployed to GitHub Pages via `.github/workflows/pages.yml` from the `showcase/` folder.
Live URL: `https://evanly-gh.github.io/Sweccathon-2026/`
