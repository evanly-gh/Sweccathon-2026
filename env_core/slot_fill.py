"""
Slot-fill engine for NPC response templates.

Extracts salient phrases from the agent's message and fills {slots}
in NPC response templates, making the NPC feel responsive to what
the agent actually said while remaining fully deterministic.
"""

from __future__ import annotations

import re

# Common filler words to skip when extracting key phrases
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "under",
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most",
    "other", "some", "such", "no", "only", "same", "than", "too", "very",
    "just", "because", "if", "when", "while", "although", "though",
    "show", "shows", "shown", "according", "based", "given", "using",
    "consider", "imagine", "look", "tell", "told", "asked", "believe",
    "suggest", "suggests", "indicate", "indicates", "means", "mean",
    "many", "several", "major", "simply", "really", "however",
    "research", "understand", "similarly", "potential", "important",
    "crucial", "significant", "overall", "specific", "particularly",
    "additionally", "furthermore", "moreover", "therefore",
    "this", "that", "these", "those", "it", "its", "i", "you", "your",
    "we", "our", "they", "their", "them", "my", "me", "he", "she", "his",
    "her", "who", "which", "what", "where", "how", "why", "there", "here",
    "also", "about", "up", "out", "then", "much", "even", "well", "back",
    "still", "already", "really", "actually", "think", "know", "see",
    "make", "like", "get", "go", "come", "take", "want", "say", "said",
    "don't", "doesn't", "didn't", "won't", "wouldn't", "couldn't",
    "shouldn't", "haven't", "hasn't", "isn't", "aren't", "wasn't",
})


def extract_topic_phrase(message: str) -> str:
    """
    Extract the most salient noun phrase or key claim from the agent's message.
    Returns a short phrase (2-5 words) suitable for inserting into a template.
    """
    text = message.strip()
    if not text:
        return "that"

    # Try to find quoted claims first
    quoted = re.findall(r'"([^"]{5,60})"', text)
    if quoted:
        return quoted[0].lower()

    # Try to find "about X", "regarding X", "concerning X"
    about = re.search(r'(?:about|regarding|concerning|around)\s+(.{5,40}?)(?:[,.]|\s+(?:and|but|which|that|is|are|was))', text, re.I)
    if about:
        return about.group(1).strip().lower()

    # Try noun-phrase patterns: "the X of Y", "a X in Y"
    np = re.search(r'(?:the|a|an)\s+((?:[a-zA-Z]+ ){1,3}(?:of|in|for|from|with)\s+(?:[a-zA-Z]+ ?){1,2})', text, re.I)
    if np:
        phrase = np.group(1).strip().lower()
        if len(phrase) > 5:
            return phrase

    # Extract content words, skip filler, pick strongest cluster
    words = re.findall(r"[a-zA-Z'-]+", text.lower())
    content_words = [w for w in words if w not in _STOP_WORDS and len(w) > 3]

    if not content_words:
        return "that"

    # Return 2 content words — enough for specificity, short enough for templates
    return " ".join(content_words[:2])


def extract_claim(message: str) -> str:
    """
    Extract a short paraphrase of the agent's main claim.
    Looks for sentences with strong assertion verbs.
    """
    sentences = re.split(r'[.!?]+', message.strip())
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 15 or len(sent) > 120:
            continue
        if any(v in sent.lower() for v in [
            "shows", "proves", "demonstrates", "found that", "suggests",
            "research", "data", "evidence", "percent", "study",
            "should", "must", "need to", "important", "crucial",
        ]):
            # Trim to a reasonable length
            if len(sent) > 80:
                sent = sent[:77] + "..."
            return sent.strip().lower()

    # Fallback: first content-heavy sentence
    for sent in sentences:
        sent = sent.strip()
        if 20 < len(sent) < 100:
            return sent.strip().lower()

    return "your point"


def fill_slots(template: str, message: str) -> str:
    """
    Fill {topic}, {claim}, and {point} slots in a template string
    using content extracted from the agent's message.
    """
    if "{" not in template:
        return template

    topic = extract_topic_phrase(message)
    claim = extract_claim(message)

    return (
        template
        .replace("{topic}", topic)
        .replace("{claim}", claim)
        .replace("{point}", topic)
    )
