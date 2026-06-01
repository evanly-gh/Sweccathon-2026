"""
Argument type classifier — multi-signal weighted scoring.

Classifies the agent's persuasive message into one of 7 categories.
Uses three detection stages:
  1. Strip polite preambles ("I understand...", "I appreciate...")
     that would falsely trigger CONCESSION
  2. Score exclusive high-confidence phrases (5x weight)
  3. Score broad keywords (1x weight, length-normalised)

The CONCESSION category only fires when the agent genuinely acknowledges
the other side's position as a STRATEGIC MOVE — not when it's just
being polite before making a different kind of argument.

Research basis: Walton's argumentation schemes (60+ types, simplified
to 6+1 for this benchmark), SemEval persuasion detection shared tasks,
Frontiers persuasion survey (2024). The distinction between polite
preamble and strategic concession is based on the finding that LLMs
default to politeness markers that don't represent genuine strategic
choice (Persuaficial benchmark, 2025).
"""

from __future__ import annotations

import re

# ── Stage 0: Preamble stripping ──────────────────────────────────────────────
# These phrases are polite openings, NOT strategic concessions. Strip them
# before classification so they don't trigger CONCESSION falsely.
_PREAMBLE_PATTERNS = [
    r"^i\s+(?:completely\s+)?understand\s+(?:your|the|that|how)\b[^.!?]{0,80}[.!?,]\s*",
    r"^i\s+appreciate\s+(?:your|the|that)\b[^.!?]{0,60}[.!?,]\s*",
    r"^(?:thank\s+you|thanks)\s+for\b[^.!?]{0,60}[.!?,]\s*",
    r"^i\s+hear\s+you[^.!?]{0,40}[.!?,]\s*",
    r"^(?:that's\s+a\s+(?:great|good|fair|valid)\s+(?:point|question|concern))[^.!?]{0,40}[.!?,]\s*",
    r"^(?:you\s+raise\s+(?:a\s+)?(?:good|valid|fair|important)\s+(?:point|concern))[^.!?]{0,40}[.!?,]\s*",
]


def _strip_preamble(text: str) -> str:
    """Remove polite opening phrases that don't indicate strategic intent."""
    stripped = text
    for pattern in _PREAMBLE_PATTERNS:
        stripped = re.sub(pattern, "", stripped, count=1, flags=re.IGNORECASE)
    return stripped.strip() or text  # fall back to original if entire message was a preamble


# ── Stage 1: Exclusive high-confidence phrases (5x weight) ───────────────────
# These phrases are strong enough to dominate classification on their own.
# Each is specific to one strategy and rarely appears in other contexts.

EXCLUSIVE_PHRASES: dict[str, list[str]] = {
    "CONCESSION": [
        # Strategic concession: agent explicitly agrees with OPPONENT'S position
        # before pivoting. Must contain acknowledgment of the other side being RIGHT.
        "you're right that", "you're right about", "you raise a valid",
        "i admit that", "i admit the", "i admit ",
        "i acknowledge that", "that's a fair criticism",
        "i concede that", "i agree that you", "you make a fair point",
        "granted,", "while it's true that", "while it's true ",
        "i can see why you'd", "i won't pretend that",
        "that's a legitimate concern", "that's a valid concern",
    ],
    "ANECDOTE": [
        "i know someone", "i know a", "my friend", "my colleague",
        "let me tell you about", "there was a person",
        "i've seen firsthand", "i once", "i remember when",
        "consider this case", "picture this",
        "a story about", "in my experience",
        "let me share", "i heard from", "i talked to",
    ],
    "SOCIAL_PROOF": [
        "most people", "the majority of", "survey shows",
        "poll found", "growing consensus", "public opinion",
        "widely adopted", "commonly accepted",
        "increasingly popular", "industry standard",
        "everyone is moving to", "the trend is clear",
    ],
    "AUTHORITY": [
        "according to", "research by", "study by",
        "published in", "peer-reviewed", "experts at",
        "scientists at", "endorsed by", "recommended by",
        "official guidance", "government report",
    ],
    "EMOTIONAL": [
        "think about your family", "imagine how you'd feel",
        "the human cost", "people are suffering",
        "fear for", "hope for",
        "what would you feel if", "it breaks my heart",
        "think of the children", "lives are at stake",
        "the pain of", "the loss of",
    ],
}

# ── Stage 2: Broad keyword banks (1x weight, length-normalised) ──────────────

KEYWORDS: dict[str, list[str]] = {
    "LOGICAL": [
        "data", "study", "studies", "evidence", "statistic",
        "percent", "percentage", "%", "therefore", "thus", "hence",
        "analysis", "findings", "demonstrate", "measured", "proven",
        "conclusion", "cost-benefit", "roi", "efficiency",
        "compared to", "shows that", "correlat",
    ],
    "EMOTIONAL": [
        "feel", "feelings", "imagine", "fear", "scared", "hope",
        "worried", "family", "children", "heart", "care", "suffer",
        "pain", "loss", "anxiety", "tragic", "harm", "hurt",
        "desperate", "compassion", "empathy",
    ],
    "SOCIAL_PROOF": [
        "everyone", "community", "norm", "neighbors", "peers",
        "colleagues", "society", "trend", "popular", "adopted",
        "widespread",
    ],
    "AUTHORITY": [
        "expert", "scientist", "doctor", "official", "report",
        "government", "university", "institute", "leading",
        "specialist", "credential", "fda", "nhs", "cdc",
    ],
    "ANECDOTE": [
        "for example", "for instance", "story", "case",
        "recently", "last year", "personally", "experience",
        "scenario", "situation",
    ],
    "CONCESSION": [
        # Only structural concession markers — NOT politeness
        "although", "despite", "nevertheless", "even though",
        "on the other hand", "that said,", "having said that",
    ],
}

ARG_TYPES = ["LOGICAL", "EMOTIONAL", "SOCIAL_PROOF", "AUTHORITY", "ANECDOTE", "CONCESSION", "GENERIC"]

_EXCLUSIVE_WEIGHT = 5
_KEYWORD_WEIGHT = 1
_LENGTH_NORM_WORDS = 50


def detect(message: str) -> str:
    """
    Classify the agent's message into one of 7 argument types.

    Three stages:
      0. Strip polite preambles (prevents "I understand" → CONCESSION)
      1. Score exclusive phrases (high confidence, 5x weight)
      2. Score broad keywords (1x weight, length-normalised)
      3. Pick highest; suppress LOGICAL if another type has exclusive match
    """
    raw_text = message.lower()

    # Stage 0: strip preamble — classify based on the SUBSTANCE, not the greeting
    text = _strip_preamble(raw_text)

    word_count = max(len(text.split()), 1)
    length_factor = min(1.0, _LENGTH_NORM_WORDS / word_count)

    scores: dict[str, float] = {}

    # Stage 1: exclusive phrases (high weight)
    for arg_type, phrases in EXCLUSIVE_PHRASES.items():
        for phrase in phrases:
            if phrase in text:
                scores[arg_type] = scores.get(arg_type, 0) + _EXCLUSIVE_WEIGHT

    # Stage 2: keywords (length-normalised)
    for arg_type, kws in KEYWORDS.items():
        kw_hits = sum(1 for kw in kws if kw in text)
        if kw_hits > 0:
            scores[arg_type] = scores.get(arg_type, 0) + kw_hits * _KEYWORD_WEIGHT * length_factor

    if not scores:
        return "GENERIC"

    best = max(scores, key=lambda t: scores[t])

    # Stage 3: suppress LOGICAL dominance — if LOGICAL wins but another type
    # has an exclusive phrase match, prefer the phrase match. This prevents
    # factual-sounding text from always landing on LOGICAL.
    if best == "LOGICAL":
        exclusive_alternatives = [
            t for t, s in scores.items()
            if t != "LOGICAL" and s >= _EXCLUSIVE_WEIGHT
        ]
        if exclusive_alternatives:
            best = max(exclusive_alternatives, key=lambda t: scores[t])

    return best
