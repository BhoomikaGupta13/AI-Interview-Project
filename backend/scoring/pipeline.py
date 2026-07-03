# backend/scoring/pipeline.py

import os
import json
import traceback
import re
import difflib

from .config import (
    SCORE_DIR,
    TRANSCRIPT_BASE,
    QUESTION_TYPE_WEIGHTS,
    DYNAMIC_WEIGHTS,
)
from .embedder import concept_similarity
from .ideal_generator import generate_key_concepts
from .llm_evaluator import evaluate_answer
from .lm_judge import judge_depth
from .combiner import get_band

# ── DATABASE LAYER INTEGRATION ──────────────────────────────────────────────
from backend.db.database import init_db, get_conn
from backend.db.queries import save_score, save_session


def _fetch_true_username(session_id: str) -> str:
    """Queries the database directly to get the real candidate username."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT username FROM interview_sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return row[0]
    except Exception as e:
        print(f"[DB Warning] Could not look up username for session: {e}")
    return "unknown_candidate"


def _save_individual_question_scores(session_id: str, results: list):
    """
    Saves expanded scoring metrics to the questions_answers table,
    making individual question scores cleanly visible for front-end access.

    NOTE: `raw_answer`, `sanitize_used_llm`, and `sanitize_reason` (the
    fidelity-guardrail audit trail added to each result) are NOT written to
    this table — the current schema has no columns for them. They ARE
    persisted in the full JSON report written by score_session() to
    SCORE_DIR/<session_id>.json, so raw-vs-sanitized text stays auditable.
    If you want that audit trail in Postgres too, add matching columns to
    questions_answers and extend the INSERT below.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            for r in results:
                cur.execute(
                    """
                    INSERT INTO questions_answers 
                        (session_id, question_no, question_type, question_text, 
                         answer_text, question_score, question_band, feedback_text)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id, question_no) DO UPDATE 
                        SET answer_text    = EXCLUDED.answer_text,
                            question_type  = EXCLUDED.question_type,
                            question_score = EXCLUDED.question_score,
                            question_band  = EXCLUDED.question_band,
                            feedback_text  = EXCLUDED.feedback_text
                """,
                    (
                        session_id,
                        r.get("question_no"),
                        r.get("question_type", "general"),
                        r.get("question", ""),
                        r.get("answer", ""),
                        r.get("score", 0.0),
                        r.get("band", "Weak"),
                        r.get("feedback", ""),
                    ),
                )
        conn.commit()


def _word_overlap_ratio(a: str, b: str) -> float:
    """Fraction of A's words that also appear in B (order-insensitive, case-insensitive)."""
    wa = re.findall(r"[a-z0-9']+", a.lower())
    wb = set(re.findall(r"[a-z0-9']+", b.lower()))
    if not wa:
        return 1.0
    matched = sum(1 for w in wa if w in wb)
    return matched / len(wa)


def _sequence_similarity(a: str, b: str) -> float:
    """
    Order-sensitive similarity (0-1) between the two word sequences, via
    difflib's SequenceMatcher. Unlike _word_overlap_ratio, this also cares
    about word ORDER and STRUCTURE, so it catches a rewrite that reuses a
    lot of the same words but rearranges/pads them into new sentences —
    something a pure "are these words present somewhere" check can miss.
    This is the primary defense against hallucination now that corrections
    are no longer gated to a fixed vocabulary whitelist.
    """
    wa = re.findall(r"[a-z0-9']+", a.lower())
    wb = re.findall(r"[a-z0-9']+", b.lower())
    if not wa and not wb:
        return 1.0
    return difflib.SequenceMatcher(None, wa, wb).ratio()


def _validate_sanitization(raw_answer: str, sanitized: str) -> tuple:
    """
    Fidelity guardrail: makes sure the LLM 'cleanup' didn't rewrite, invent,
    or append content instead of just correcting transcription glitches.

    Returns (is_valid, reason).
    """
    raw_words = raw_answer.split()
    san_words = sanitized.split()

    if not sanitized.strip():
        return False, "empty_output"

    # The sanitized answer should never be drastically longer than the raw
    # transcript — real STT cleanup shrinks or holds length, it doesn't
    # add new sentences of content.
    length_ratio = len(san_words) / max(len(raw_words), 1)
    if length_ratio > 1.35:
        return False, f"length_expanded_{length_ratio:.2f}x"
    if length_ratio < 0.5:
        return False, f"length_collapsed_{length_ratio:.2f}x"

    # Most of the raw transcript's vocabulary should still be present.
    overlap = _word_overlap_ratio(raw_answer, sanitized)
    if overlap < 0.55:
        return False, f"low_word_overlap_{overlap:.2f}"

    # Order-sensitive check: a handful of word-level substitutions/deletions
    # keeps this ratio high; a rewrite or appended content drags it down
    # even when overlap looks okay (e.g. same words, shuffled + padded).
    seq_sim = _sequence_similarity(raw_answer, sanitized)
    if seq_sim < 0.70:
        return False, f"low_sequence_similarity_{seq_sim:.2f}"

    return True, "ok"


def _known_vocabulary(profile: dict) -> str:
    """
    Builds a short list of terms the candidate is known to use (from their
    own profile), offered to the sanitizer as SUPPORTING context — not a
    hard whitelist. Profiles are rarely exhaustive, so gating corrections
    only on this list would leave real (but undeclared) terms uncorrected.
    """
    skills = profile.get("skills", [])[:15]
    raw_projects = profile.get("projects", [])[:6]
    project_names = [
        p.get("name", "") if isinstance(p, dict) else str(p) for p in raw_projects
    ]
    terms = [t for t in (skills + project_names) if t]
    return ", ".join(terms) if terms else "(none on file)"


def _sanitize_transcription(question: str, raw_answer: str, profile: dict) -> dict:
    """
    Uses a lightweight LLM call to correct Speech-to-Text acoustic glitches,
    phonetic typos, and repeated phrase loops before evaluation.

    Corrections are grounded in whatever context is actually available —
    the interview question's own wording, the surrounding sentences, and
    (as a supporting hint, not a requirement) the candidate's declared
    skills/projects. Nothing is required to be pre-declared to get fixed;
    the real safety net is the guardrail below, which checks the LLM's
    output against the raw transcript for both word overlap AND word-order
    similarity, and falls back to the raw transcript if it looks like a
    rewrite rather than a handful of word-level fixes.

    Returns a dict: {"text": <answer used for scoring>, "raw": raw_answer,
                      "sanitized": <what the LLM returned, or None>,
                      "used_sanitized": bool, "reason": str}
    """
    if not raw_answer.strip() or len(raw_answer.split()) < 4:
        return {
            "text": raw_answer,
            "raw": raw_answer,
            "sanitized": None,
            "used_sanitized": False,
            "reason": "too_short_to_sanitize",
        }

    from backend.utils.llm_client import ask_llm

    known_terms = _known_vocabulary(profile)

    prompt = f"""You are a strict word-level transcription corrector for a technical interview system.
The candidate's answer was transcribed from audio via Speech-to-Text and may contain acoustic
mis-hearings (wrong word substituted for a similar-sounding one) and broken repeated-phrase loops
caused by audio glitches.

Context Question: {question}
Raw Transcript: "{raw_answer}"

Candidate's declared skills/projects (supporting context only — this list is NOT exhaustive,
so a real term the candidate used may be missing from it; don't refuse a correction just
because the word isn't listed here):
{known_terms}

STRICT RULES — you are a correction pass, not a writer:
1. Fix a word/short phrase ONLY when you are highly confident, from context, that it is a
   phonetic mis-transcription of a specific word the candidate actually said. Strong evidence
   for confidence includes: the correct term appears (or is clearly implied) in the Context
   Question itself, the correct term appears elsewhere in the candidate's own transcript, or it
   matches an entry in the declared skills/projects above. A close phonetic match plus contextual
   fit (e.g. "whisper mode" immediately followed by talk of transcribing audio, in an answer to a
   question about the Whisper model) is enough — you do NOT need the term to be pre-listed.
2. If you cannot point to a specific reason for confidence, leave the word EXACTLY as
   transcribed. Do not swap in a "better sounding" or "more impressive" technical term on a hunch.
3. Remove only exact/near-exact duplicate phrase loops caused by audio capture glitches
   (the same sentence or clause repeated back-to-back with no new content).
4. Do NOT add sentences, explanations, examples, or technical detail that is not already present
   in the raw transcript. Do NOT elaborate, summarize, or improve the answer.
5. Do NOT change the candidate's vocabulary, sentence structure, or level of detail beyond fixing
   clear glitches. The output word count and word order must stay close to the input.
6. If the transcript looks fine as-is, return it unchanged.

Return ONLY the corrected transcript text. No preamble, no explanation, no markdown.
"""
    try:
        sanitized = ask_llm(prompt, temperature=0.0).strip()
    except TypeError:
        # ask_llm signature may not support a temperature kwarg.
        sanitized = ask_llm(prompt).strip()

    is_valid, reason = _validate_sanitization(raw_answer, sanitized)
    if is_valid:
        return {
            "text": sanitized,
            "raw": raw_answer,
            "sanitized": sanitized,
            "used_sanitized": True,
            "reason": reason,
        }

    print(
        f"  [Sanitize Guardrail] Rejected LLM cleanup ({reason}). "
        f"Falling back to raw transcript."
    )
    return {
        "text": raw_answer,
        "raw": raw_answer,
        "sanitized": sanitized,
        "used_sanitized": False,
        "reason": reason,
    }


def _clean_echoed_question(question: str, answer: str) -> str:
    clean_ans = answer.strip()
    norm_q = re.sub(r"[^\w\s]", "", question.lower()).strip()
    norm_a = re.sub(r"[^\w\s]", "", clean_ans.lower()).strip()

    padding_patterns = [
        r"^so\s+how\s+does\s+",
        r"^so\s+can\s+you\s+",
        r"^to\s+explain\s+the\s+",
        r"^how\s+does\s+",
        r"^can\s+you\s+",
        r"^what\s+are\s+the\s+",
    ]

    if norm_a.startswith(norm_q):
        q_words = norm_q.split()
        ans_words = clean_ans.split()
        if len(ans_words) >= len(q_words):
            potential_rest = " ".join(ans_words[len(q_words) :]).strip()
            return re.sub(
                r"^(so|and|then|basically|actually)[,\s]+",
                "",
                potential_rest,
                flags=re.IGNORECASE,
            ).strip()

    for pattern in padding_patterns:
        if re.search(pattern, norm_a):
            q_snippet = norm_q[:30]
            if q_snippet in norm_a:
                loc = clean_ans.lower().find(q_snippet)
                if loc != -1:
                    truncated = clean_ans[loc + len(q_snippet) :].strip()
                    return re.sub(
                        r"^[?\s,.]+([\s]*so[\s]*|[\s]*and[\s]*)*",
                        "",
                        truncated,
                        flags=re.IGNORECASE,
                    ).strip()

    return clean_ans


def _infer_question_type(question: str) -> str:
    q = question.lower()
    if any(w in q for w in ["project", "built", "developed", "implemented", "created"]):
        return "project"
    if any(
        w in q
        for w in ["explain", "what is", "how does", "difference between", "define"]
    ):
        return "skill"
    if any(
        w in q for w in ["experience", "role", "worked", "team", "job", "internship"]
    ):
        return "experience"
    if any(w in q for w in ["research", "paper", "published", "publication"]):
        return "research"
    if "patent" in q:
        return "patent"
    if any(w in q for w in ["achiev", "award", "won", "accomplish", "recognition"]):
        return "achievement"
    return "general"


class ScoringPipeline:

    def _load_answers(self, session_id: str) -> list:
        path = os.path.join(TRANSCRIPT_BASE, session_id, "combined_answers.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No transcript found at {path}.")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _load_session(self, session_id: str) -> dict:
        path = os.path.join("storage", "sessions", f"{session_id}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Session file not found: {path}")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def score_question(
        self,
        question_no: int,
        question: str,
        answer: str,
        profile: dict,
        q_type: str = "general",
    ) -> dict:
        print(f"\n[Scoring] Q{question_no} ({q_type}): {question[:15]}...")
        try:
            echo_cleaned = _clean_echoed_question(question, answer)
            sanitize_result = _sanitize_transcription(question, echo_cleaned, profile)
            processed_answer = sanitize_result["text"]
            print(f"  [Sanitized Text]: {processed_answer[:60]}...")
            if not sanitize_result["used_sanitized"] and sanitize_result["sanitized"]:
                print(
                    f"  [Sanitize Audit] raw kept. LLM proposed: "
                    f"{sanitize_result['sanitized'][:60]}..."
                )

            word_count = len(processed_answer.split())

            if word_count == 0:
                print("  [Unanswered] Blank answer. Skipping model calls.")
                return {
                    "question_no": question_no,
                    "question_type": q_type,
                    "question": question,
                    "answer": "",
                    "raw_answer": answer,
                    "sanitize_used_llm": False,
                    "sanitize_reason": sanitize_result["reason"],
                    "status": "success",
                    "score": 0.0,
                    "band": "Unanswered",
                    "similarity": 0.0,
                    "llm_score": 0.0,
                    "depth_score": 0.0,
                    "clarity": 0,
                    "correctness": 0,
                    "completeness": 0,
                    "feedback": "Unanswered question.",
                    "strengths": [],
                    "improvements": ["Answer this question to receive a score."],
                    "depth_feedback": "Unanswered question.",
                }

            if word_count < 4:
                print(
                    f"  [Short-Circuit] Answer is too trivial ({word_count} words). Skipping model calls."
                )
                return {
                    "question_no": question_no,
                    "question_type": q_type,
                    "question": question,
                    "answer": answer,
                    "raw_answer": answer,
                    "sanitize_used_llm": sanitize_result["used_sanitized"],
                    "sanitize_reason": sanitize_result["reason"],
                    "status": "success",
                    "score": 1.0,
                    "band": "Weak",
                    "similarity": 0.0,
                    "llm_score": 0.0,
                    "depth_score": 0.0,
                    "clarity": 1,
                    "correctness": 0,
                    "completeness": 0,
                    "feedback": "Answer was brief or conversational padding only. No technical concepts addressed.",
                    "strengths": [],
                    "improvements": [
                        "Provide an answer explaining structural systems."
                    ],
                    "depth_feedback": "No technical details given.",
                }

            key_concepts = generate_key_concepts(question, profile)
            similarity = concept_similarity(processed_answer, key_concepts)
            print(f"  raw_similarity={similarity:.3f}")

            llm_result = evaluate_answer(
                question, processed_answer, profile, similarity
            )
            llm_score = llm_result["llm_score"]
            print(f"  calibrated_llm_score={llm_score:.3f}")

            # ── CALIBRATED SOFT-FLOOR FILTER FOR PARTIALLY CORRECT MINIMUMS ──
            if llm_result.get("correctness", 0) <= 2:
                # If the similarity score was already low, give it a soft baseline credit
                # instead of dropping it straight down to absolute zero.
                similarity = max(0.15, similarity)
            # ──────────────────────────────────────────────────────────────────

            judge_result = judge_depth(question, processed_answer, profile)
            depth_score = judge_result["depth_score"]
            print(f"  depth_score={depth_score:.3f}")

            weights = DYNAMIC_WEIGHTS.get(q_type, DYNAMIC_WEIGHTS["default"])
            final_raw = (
                weights["similarity"] * similarity
                + weights["llm"] * llm_score
                + weights["depth"] * depth_score
            )
            final = round(final_raw * 10, 2)
            band = get_band(final)
            print(
                f"  [Weights: Sim={weights['similarity']}, LLM={weights['llm']}, Depth={weights['depth']}] -> final={final} ({band})"
            )

            return {
                "question_no": question_no,
                "question_type": q_type,
                "question": question,
                "answer": processed_answer,
                "raw_answer": answer,
                "sanitize_used_llm": sanitize_result["used_sanitized"],
                "sanitize_reason": sanitize_result["reason"],
                "status": "success",
                "score": final,
                "band": band,
                "similarity": round(similarity * 10, 2),
                "llm_score": round(llm_score * 10, 2),
                "depth_score": round(depth_score * 10, 2),
                "clarity": llm_result.get("clarity", 0),
                "correctness": llm_result.get("correctness", 0),
                "completeness": llm_result.get("completeness", 0),
                "feedback": llm_result.get("feedback", ""),
                "strengths": llm_result.get("strengths", []),
                "improvements": llm_result.get("improvements", []),
                "depth_feedback": judge_result.get("depth_feedback", ""),
            }
        except Exception:
            err = traceback.format_exc()
            print(f"[Scoring] ERROR on Q{question_no}:\n{err}")
            return {
                "question_no": question_no,
                "question": question,
                "answer": answer,
                "status": "error",
                "error": err,
                "score": 0.0,
                "band": "Error",
            }

    def score_session(self, session_id: str) -> dict:
        os.makedirs(SCORE_DIR, exist_ok=True)
        answers_list = self._load_answers(session_id)
        session = self._load_session(session_id)
        profile = session["candidate"]

        # ── RESOLVED USERNAME PASSING ISSUE ───────────────────────────────────
        username = session.get("username") or _fetch_true_username(session_id)
        print(f"[DB] Session owned by authentic user credentials: {username}")
        if username != "unknown_candidate":
            save_session(
                session_id,
                username,
                session.get("status", "COMPLETED"),
                session.get("expires_at"),
            )
        # ──────────────────────────────────────────────────────────────────────

        results = []
        total_weight = 0.0
        weighted_sum = 0.0

        for i, item in enumerate(answers_list, start=1):
            question = item.get("question", f"Question {i}")
            raw_answer = item.get("Answer") or item.get("answer") or ""
            q_type = _infer_question_type(question)

            result = self.score_question(i, question, raw_answer, profile, q_type)
            results.append(result)

            weight = QUESTION_TYPE_WEIGHTS.get(q_type, 1.0)
            weighted_sum += result.get("score", 0.0) * weight
            total_weight += weight

        overall = round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0
        band = get_band(overall)

        report = {
            "session_id": session_id,
            "overall_score": overall,
            "band": band,
            "total_questions": len(answers_list),
            "scored": sum(1 for r in results if r.get("status") == "success"),
            "results": results,
        }

        out_path = os.path.join(SCORE_DIR, f"{session_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4)

        # ── EXPANDED DB INJECTION ─────────────────────────────────────────────
        try:
            init_db()
            save_score(session_id, username, report)

            # Save breakdown columns inside questions_answers table
            _save_individual_question_scores(session_id, results)

            # Explicitly set the denominator /10 metric to the scores database row
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE scores SET max_score_scale = 10 WHERE session_id = %s",
                        (session_id,),
                    )
                conn.commit()
            print(
                "[DB] Production score layers and question breakdowns updated cleanly."
            )
        except Exception as db_err:
            print(f"[DB] Pipeline persistence error: {db_err}")
            raise
        # ──────────────────────────────────────────────────────────────────────

        print(f"\n[Scoring] Session {session_id} done -> Overall: {overall}/10")
        return report


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        sys.exit(1)
    ScoringPipeline().score_session(sys.argv[1])
#  python -m backend.scoring.pipeline <session_id>
