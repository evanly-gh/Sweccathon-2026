# Running a Benchmark and Updating the Showcase

## Prerequisites

- `pip install swecc-mesocosm` installed
- Logged in: `mesocosm auth login` (JWT expires periodically — re-run if you get 401)
- Env already submitted and `ready` (check with `mesocosm env list`)

## Quick Reference IDs

| What | Value |
|---|---|
| Env ID | `797a981e-6e69-4fbd-9452-9b38f5e8f0d8` |
| Domain ID | `3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927` |
| Showcase URL | https://evanly-gh.github.io/Sweccathon-2026/ |

## Step 1 — Resubmit the env (if code changed)

Skip this if you haven't pushed any code changes since the last submit.

```powershell
mesocosm auth login
mesocosm env submit --name "Persuasion Engine" --github-url https://github.com/evanly-gh/Sweccathon-2026 --solo
mesocosm env list   # wait until status shows "ready"
```

The platform clones your repo and rebuilds the env. Takes ~30 seconds.

## Step 2 — Create a run

```powershell
mesocosm run create --domain 3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927 --vow-version 6.7.0 --model MODEL --episodes N --visibility gallery_public --solo
```

**Allowed models** (as of May 2026):

| Model | Notes |
|---|---|
| `anthropic/claude-sonnet-4-6` | Best results so far, reliable |
| `openai/gpt-4o` | Good, may truncate on 512 max_tokens |
| `gemini/gemini-2.5-flash` | Shared Gemini quota — may 429 |
| `gemini/gemini-2.5-flash-lite` | Same quota pool |
| `gemini/gemini-3.5-flash` | Same quota pool |

**Recommended first run:**
```powershell
mesocosm run create --domain 3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927 --vow-version 6.7.0 --model anthropic/claude-sonnet-4-6 --episodes 4 --visibility gallery_public --solo
```

Copy the `id` from the output — you'll need it for the next steps.

## Step 3 — Wait for completion

```powershell
mesocosm run get RUN_ID
```

Poll until `"status": "completed"`. Runs take 30–90 seconds for 4 episodes.

**Common failures:**
- `429 RateLimitError` — Gemini quota exhausted. Switch to Claude or GPT-4o.
- `non-JSON content / Unterminated string` — Model hit `max_tokens` limit mid-JSON. Not a bug in your env. Try fewer episodes or a different model.
- `401 Unauthorized` — JWT expired. Run `mesocosm auth login` again.

## Step 4 — Save the run

Use `save_run.py` to export, register, and update the showcase in one command:

```powershell
python save_run.py RUN_ID
# or with a custom label:
python save_run.py RUN_ID --label "Claude Sonnet v2"
```

This does three things:
1. Runs `mesocosm run export` → saves to `showcase/data/run_SHORTID.json`
2. Adds an entry to `showcase/data/manifest.json` (model, scores, episode count)
3. Copies the file to `showcase/data/replay.json` as the default

## Step 5 — Commit and push

```powershell
git add showcase/data/
git commit -m "Add MODEL run"
git push origin main
```

GitHub Pages redeploys automatically in ~30 seconds.

## Step 6 — Verify

Open https://evanly-gh.github.io/Sweccathon-2026/ and confirm:
- The run selector dropdown appears in the sidebar (if multiple runs are saved)
- All episodes appear in the episode rail
- Agreement bar starts at the correct negative value on turn 0
- NPC speaks first, then AI responds
- Failed episodes show `!` with the error message

## Comparing Multiple Models

Save runs from different models — they all appear in the dropdown:

```powershell
# Run Claude
mesocosm run create --domain 3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927 --vow-version 1.0.0 --model anthropic/claude-sonnet-4-6 --episodes 4 --visibility gallery_public --solo
mesocosm run get RUN_ID       # wait for completed
python save_run.py RUN_ID --label "Claude Sonnet 4.6"

# Run GPT-4o
mesocosm run create --domain 3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927 --vow-version 1.0.0 --model openai/gpt-4o --episodes 4 --visibility gallery_public --solo
mesocosm run get RUN_ID
python save_run.py RUN_ID --label "GPT-4o"

# Push all at once
git add showcase/data/
git commit -m "Add Claude vs GPT-4o comparison"
git push origin main
```

The showcase dropdown shows each run with its aggregate persuasion score. Click to switch between them — episodes, agreement bars, rapport, and all HUD metrics update for that run.

## How the Showcase Data Works

```
showcase/data/
  manifest.json         ← list of all saved runs (model, scores, filename)
  run_069f0002.json     ← GPT-4o run (exported trace)
  run_5bb001b0.json     ← Claude run (exported trace)
  replay.json           ← copy of the most recently saved run (fallback)
```

- `manifest.json` is the source of truth. The showcase reads it to build the dropdown.
- Each `run_*.json` is a full Mesocosm export (episodes, turns, actions, info dicts).
- `replay.json` is always a copy of the last saved run — backward compatible if manifest is missing.
- `save_run.py` manages all of this automatically.

## Running Locally (no Mesocosm needed)

For quick iteration without submitting:

```powershell
# Run with a baseline agent
python run_local.py --agent greedy --scenario cold_skeptic

# Export a local trace for the showcase
python run_local.py --agent adaptive --scenario cold_skeptic --trace-out showcase/data/replay.json

# Then open showcase/index.html directly in your browser — no push needed
```

## Full Resubmit Workflow (after code changes)

```powershell
# 1. Test locally
python test_determinism.py

# 2. Rebake baselines
python compute_baselines.py --bake

# 3. Commit and push code
git add -A
git commit -m "Description of changes"
git push origin main

# 4. Resubmit env
mesocosm auth login
mesocosm env submit --name "Persuasion Engine" --github-url https://github.com/evanly-gh/Sweccathon-2026 --solo
mesocosm env list   # wait for "ready"

# 5. Run + save + push
mesocosm run create --domain 3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927 --vow-version 6.7.0 --model openai/gpt-4o --episodes 10 --visibility gallery_public --solo
mesocosm run get RUN_ID
python save_run.py RUN_ID --label "Claude Sonnet post-update"
git add showcase/data/
git commit -m "Update replay"
git push origin main
```
