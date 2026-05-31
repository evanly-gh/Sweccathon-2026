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

## Step 4 — Export the replay

```powershell
mesocosm run export RUN_ID -o showcase/data/replay.json
```

This writes the full trace (every turn of every episode) to `showcase/data/replay.json`.

## Step 5 — Commit and push

```powershell
git add showcase/data/replay.json
git commit -m "Update replay — MODEL, N episodes"
git push origin main
```

GitHub Pages redeploys automatically in ~30 seconds.

## Step 6 — Verify

Open https://evanly-gh.github.io/Sweccathon-2026/ and confirm:
- All episodes appear in the left rail
- Agreement bar starts at the correct negative value on turn 0
- NPC speaks first, then AI responds
- Failed episodes show `!` with the error message

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

# 5. Run + export + push replay
mesocosm run create --domain 3a7286d6-b6f5-4bca-9e8d-b94f9d9ea927 --vow-version 1.0.0 --model anthropic/claude-sonnet-4-6 --episodes 4 --visibility gallery_public --solo
mesocosm run get RUN_ID
mesocosm run export RUN_ID -o showcase/data/replay.json
git add showcase/data/replay.json
git commit -m "Update replay"
git push origin main
```
