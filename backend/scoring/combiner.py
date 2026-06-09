# backend/scoring/combiner.py

from .config import BANDS


def get_band(score: float) -> str:
    """
    Matches a 0.0–10.0 score against config-defined thresholds to return a label.
    """
    for threshold, label in BANDS:
        if score >= threshold:
            return label
    return "Weak"
