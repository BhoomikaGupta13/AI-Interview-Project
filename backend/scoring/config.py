# backend/scoring/config.py

SCORE_DIR = "storage/scores"
TRANSCRIPT_BASE = "audio_test_outputs"

# ── BGE model (ADDED BACK TO FIX IMPORT ERROR) ─────────────────────────────
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"

# ── Score bands ────────────────────────────────────────────────────────────
BANDS = [
    (8.5, "Strong"),
    (7.0, "Good"),
    (5.5, "Average"),
    (0.0, "Weak"),
]

# ── Dynamic Weights per Question Type (Must sum to 1.0 per type) ───────────
DYNAMIC_WEIGHTS = {
    "skill": {"similarity": 0.30, "llm": 0.60, "depth": 0.10},
    "project": {"similarity": 0.10, "llm": 0.30, "depth": 0.60},
    "experience": {"similarity": 0.10, "llm": 0.30, "depth": 0.60},
    "research": {"similarity": 0.20, "llm": 0.40, "depth": 0.40},
    "default": {"similarity": 0.20, "llm": 0.50, "depth": 0.30},
}

# ── Per-question-type scale weights for final session aggregation ─────────
QUESTION_TYPE_WEIGHTS = {
    "project": 1.4,
    "skill": 1.2,
    "experience": 1.0,
    "research": 1.0,
    "patent": 1.0,
    "achievement": 0.8,
    "general": 1.0,
}
