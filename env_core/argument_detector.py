"""
Argument type classifier — multi-signal weighted scoring.

Uses keyword density, exclusive signal phrases, and position weighting
to correctly classify argument intent rather than surface vocabulary.
Avoids the "LOGICAL by default" trap from keyword count alone.
"""

from __future__ import annotations

import re

# Exclusive high-confidence phrases — if any match, they heavily dominate
EXCLUSIVE_PHRASES: dict[str, list[str]] = {
    "CONCESSION": [
        "i understand your", "i see your point", "you're right that", "fair point",
        "i admit", "i acknowledge", "that's a valid", "i can see why",
        "while it's true", "i hear you", "that said,", "granted,",
        "i agree that", "you raise a good", "valid concern",
    ],
    "ANECDOTE": [
        "i know someone", "my friend", "my colleague", "let me tell you",
        "there was a person", "i've seen firsthand", "i witnessed",
        "i once", "i remember when", "i heard from", "a story about",
        "consider this case", "picture this", "imagine a person who",
    ],
    "SOCIAL_PROOF": [
        "most people", "majority of", "survey shows", "poll found",
        "growing consensus", "public opinion", "many people agree",
        "widely adopted", "commonly accepted", "increasingly popular",
    ],
    "AUTHORITY": [
        "according to", "research by", "study by", "published in",
        "peer-reviewed", "experts at", "scientists at", "professor",
        "endorsed by", "recommended by", "official guidance",
        "government report", "cdc says", "who recommends",
    ],
    "EMOTIONAL": [
        "think about your family", "imagine how you'd feel", "loved ones",
        "it breaks my heart", "the human cost", "suffering",
        "fear for", "hope for", "compassion", "empathy",
        "think of the children", "what would you feel if",
    ],
}

# Broad keyword banks — used for secondary scoring
KEYWORDS: dict[str, list[str]] = {
    "LOGICAL": [
        "data", "study", "studies", "research", "evidence", "statistic",
        "percent", "percentage", "%", "therefore", "thus", "hence",
        "analysis", "findings", "demonstrate", "measured", "proven",
        "conclusion", "logically", "cost-benefit", "roi", "efficiency",
        "compared to", "shows that", "fact", "facts",
    ],
    "EMOTIONAL": [
        "feel", "feelings", "imagine", "fear", "scared", "hope", "worried",
        "family", "children", "heart", "care", "suffer", "pain", "loss",
        "anxiety", "devastat", "tragic", "harm", "hurt", "desperate", "tears",
    ],
    "SOCIAL_PROOF": [
        "everyone", "community", "norm", "standard", "neighbors", "peers",
        "colleagues", "society", "trend", "increasingly", "popular", "adopted",
    ],
    "AUTHORITY": [
        "expert", "scientist", "doctor", "official", "authority", "report",
        "government", "university", "institute", "organization", "leading",
        "specialist", "credential", "fda", "nhs", "who",
    ],
    "ANECDOTE": [
        "for example", "for instance", "story", "case", "example",
        "recently", "last year", "personally", "situation", "experience",
        "what if", "scenario",
    ],
    "CONCESSION": [
        "although", "despite", "however", "nevertheless", "even though",
        "understandable", "reasonable", "of course",
    ],
}

ARG_TYPES = list(KEYWORDS.keys()) + ["GENERIC"]

# Weight for exclusive phrase hit vs keyword count
_EXCLUSIVE_WEIGHT = 5
_KEYWORD_WEIGHT = 1
# Normalise keyword score by message length to avoid rewarding verbosity
_LENGTH_NORM_WORDS = 50


def detect(message: str) -> str:
    """
    Return the dominant argument type in the message.

    Scoring:
    1. Each exclusive phrase match = 5 points for that type
    2. Each keyword match = 1 point (normalised by message length)
    3. Type with highest total wins; GENERIC on tie/zero
    """
    text = message.lower()
    word_count = max(len(text.split()), 1)
    length_factor = min(1.0, _LENGTH_NORM_WORDS / word_count)

    scores: dict[str, float] = {}

    # Exclusive phrase matching (high weight, phrase-boundary aware)
    for arg_type, phrases in EXCLUSIVE_PHRASES.items():
        for phrase in phrases:
            if phrase in text:
                scores[arg_type] = scores.get(arg_type, 0) + _EXCLUSIVE_WEIGHT

    # Keyword matching (length-normalised)
    for arg_type, kws in KEYWORDS.items():
        kw_hits = sum(1 for kw in kws if kw in text)
        if kw_hits > 0:
            scores[arg_type] = scores.get(arg_type, 0) + kw_hits * _KEYWORD_WEIGHT * length_factor

    if not scores:
        return "GENERIC"

    # If two types are within 1 point of each other, prefer the exclusive-phrase winner
    best = max(scores, key=lambda t: scores[t])
    best_score = scores[best]

    # Suppress LOGICAL dominance: if LOGICAL wins but another type has an
    # exclusive phrase match, prefer the other type (avoids the bias where
    # any factual-sounding text scores LOGICAL)
    if best == "LOGICAL":
        exclusive_alternatives = [
            t for t, s in scores.items()
            if t != "LOGICAL" and s >= _EXCLUSIVE_WEIGHT
        ]
        if exclusive_alternatives:
            best = max(exclusive_alternatives, key=lambda t: scores[t])

    return best
