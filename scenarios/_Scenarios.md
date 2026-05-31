# Scenarios

23 NPC archetypes across 5 difficulty levels. Each scenario is a JSON file defining a unique persuasion challenge.

## Scenario Fields

| Field | Description |
|---|---|
| `starting_agreement` | How opposed the NPC starts (-1 = maximally opposed) |
| `threshold` | Agreement level needed to win |
| `close_threshold` | Agreement level where NPC walks out (default -0.95) |
| `resistance_profile` | Which argument types move them, and by how much |
| `repetition_penalty` | How much each repeat of a weak arg type costs |
| `pivot_threshold` | When the NPC drops a hint that they're warming up |
| `response_templates` | Pre-written NPC responses with `{topic}` and `{claim}` slots |
| `difficulty_explanation` | Why this scenario is this difficulty level |
| `benchmarking_value` | What specific capability this scenario tests |

The AI never sees `resistance_profile`, `agreement`, `rapport`, or `threshold` — only the NPC's response text.

## Difficulty Levels

| Level | Count | Characteristics |
|---|---|---|
| Easy | 3 | Short gap, multiple viable strategies, most models should win |
| Medium | 8 | Moderate gap, requires reading the NPC and adapting |
| Hard | 3 | Long gap, narrow effective strategies, models must avoid traps |
| Very Hard | 5 | Extreme parameters — polarized profiles, high penalties, walkout risk, rapport gates |
| Extreme | 4 | Near-impossible without perfect strategy — deep deficits, negative base shifts, expert-level NPCs |

## All 23 Scenarios

### Easy
- **`open_mind`** — The Cautious Optimist. Almost everything works. Calibration floor.
- **`first_gen_student`** — The First-Gen Student. Must address both finances and imposter syndrome.
- **`skeptical_patient`** — The Skeptical Patient. Must address specific side-effect concerns.

### Medium
- **`cold_skeptic`** — The Data Skeptic. Responds to LOGICAL. Baseline data-driven test.
- **`anxious_parent`** — The Anxious Parent. Responds to EMOTIONAL. Empathy-first test.
- **`peer_pressure_resistant`** — The Autonomy Defender. SOCIAL_PROOF backfires. Respect autonomy.
- **`reluctant_manager`** — The Reluctant Manager. LOGICAL and ANECDOTE equally strong. Balance test.
- **`traditionalist_farmer`** — The Traditionalist Farmer. ANECDOTE strongest. Audience adaptation.
- **`policy_holdout`** — The Policy Holdout. Must answer specific operational questions.
- **`ethical_shopper`** — The Ethical Shopper. Resents guilt. Tone sensitivity test.
- **`overworked_researcher`** — The Overworked Researcher. Genuine ethical ambiguity.
- **`old_school_coach`** — The Old-School Coach. Must frame change as supplementary.

### Hard
- **`community_anchor`** — The Community Guardian. EMOTIONAL/SOCIAL_PROOF needed, not data.
- **`burned_investor`** — The Burned Investor. Personal trauma. Emotional intelligence test.
- **`conspiracy_adjacent`** — The Low-Trust Contrarian. CONCESSION strongest; AUTHORITY nearly useless.
- **`flat_terrain`** — The Balanced Mind. All types ~0.08. No magic bullet. Strategic breadth.

### Very Hard
- **`entrenched_exec`** — The Risk-Averse Executive. Must lead with risk acknowledgment.
- **`needle_finder`** — The Needle Finder. Only ANECDOTE works (0.30). Find the one channel.
- **`hair_trigger`** — The Hair Trigger. Walks out at -0.85. Two bad turns = game over.
- **`penalty_gauntlet`** — The Penalty Gauntlet. 0.18 rep penalty. Must use 6+ arg types.
- **`rapport_gate`** — The Trust Gate. Threshold unreachable without rapport amplification.

### Extreme
- **`deep_deficit`** — The Deeply Opposed. Starts at -0.85. Must cover 1.05 points. No wasted turns.
- **`contrarian_trap`** — The Contrarian Trap. AUTHORITY and SOCIAL_PROOF have NEGATIVE shifts.
- **`high_bar`** — The High Bar. Threshold 0.45. NPC knows the literature. Expert-level argumentation required.
