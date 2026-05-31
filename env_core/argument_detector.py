"""
Rule-based argument type classifier.
Maps the agent's free-text message to one of 7 categories.
No model dependency — pure keyword scoring.
"""

from __future__ import annotations

KEYWORDS: dict[str, list[str]] = {
    "EMOTIONAL": [
        "feel", "feelings", "imagine", "fear", "scared", "hope", "worried", "worry",
        "loved one", "family", "children", "heart", "care", "suffer", "pain", "loss",
        "anxiety", "devastat", "empathy", "compassion", "tragic", "harm", "hurt",
        "personal", "emotional", "desperate", "crying", "tears",
    ],
    "LOGICAL": [
        "data", "study", "studies", "research", "evidence", "statistic", "statistics",
        "percent", "percentage", "%", "because", "therefore", "thus", "hence",
        "analysis", "report", "findings", "demonstrate", "shows that", "measured",
        "proven", "conclusion", "fact", "facts", "logically", "reasonably",
        "cost-benefit", "roi", "efficiency", "result", "results", "compared to",
    ],
    "SOCIAL_PROOF": [
        "most people", "majority", "everyone", "many people", "community",
        "survey", "poll", "consensus", "widespread", "common", "norm", "standard",
        "neighbors", "peers", "colleagues", "society", "public opinion",
        "trend", "growing number", "increasingly", "popular", "adopted",
    ],
    "AUTHORITY": [
        "expert", "experts", "scientist", "scientists", "professor", "doctor",
        "official", "authority", "report", "government", "according to",
        "research by", "university", "institute", "organization", "published",
        "peer-reviewed", "study by", "leading", "specialist", "credential",
        "endorsed", "recommended by", "cdc", "who", "fda", "nhs",
    ],
    "ANECDOTE": [
        "i know someone", "my friend", "my colleague", "for example", "for instance",
        "story", "case", "example", "last year", "recently", "i've seen",
        "i witnessed", "i heard", "there was a", "consider this", "picture this",
        "imagine if", "what if", "scenario", "situation", "experience",
        "personally", "i once", "i remember", "i saw",
    ],
    "CONCESSION": [
        "i understand", "i see your point", "you're right", "fair point",
        "i admit", "i acknowledge", "that's true", "granted", "of course",
        "i agree that", "valid concern", "understandable", "reasonable to",
        "i can see why", "while it's true", "even though", "although",
        "despite", "however", "nevertheless", "that said", "i hear you",
    ],
}

ARG_TYPES = list(KEYWORDS.keys()) + ["GENERIC"]


def detect(message: str) -> str:
    """Return the dominant argument type in the message."""
    text = message.lower()
    scores: dict[str, int] = {}
    for arg_type, kws in KEYWORDS.items():
        score = sum(1 for kw in kws if kw in text)
        if score > 0:
            scores[arg_type] = score

    if not scores:
        return "GENERIC"

    # Return highest score; break ties by KEYWORDS order
    return max(scores, key=lambda t: (scores[t], -list(KEYWORDS).index(t)))
