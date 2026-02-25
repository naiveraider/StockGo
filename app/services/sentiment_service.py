from __future__ import annotations

import re


_POS = {
    "beat",
    "beats",
    "surge",
    "surges",
    "soar",
    "soars",
    "record",
    "upgrade",
    "upgraded",
    "growth",
    "profit",
    "profits",
    "strong",
    "rise",
    "rises",
    "gain",
    "gains",
    "bull",
}

_NEG = {
    "miss",
    "misses",
    "plunge",
    "plunges",
    "drop",
    "drops",
    "fall",
    "falls",
    "downgrade",
    "downgraded",
    "lawsuit",
    "probe",
    "investigation",
    "weak",
    "warning",
    "cuts",
    "cut",
    "decline",
    "declines",
    "bear",
    "delay",
    "delays",
}


def score_sentiment(text: str) -> tuple[str, float, str]:
    """
    Tiny rule-based sentiment for headlines.
    Returns: (label, score in [-1,1], model_name)
    """
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    if not tokens:
        return "NEU", 0.0, "lexicon_v1"
    pos = sum(1 for t in tokens if t in _POS)
    neg = sum(1 for t in tokens if t in _NEG)
    score = (pos - neg) / max(1, pos + neg)
    if score >= 0.2:
        return "POS", float(score), "lexicon_v1"
    if score <= -0.2:
        return "NEG", float(score), "lexicon_v1"
    return "NEU", float(score), "lexicon_v1"

