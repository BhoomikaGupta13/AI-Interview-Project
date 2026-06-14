# backend/scoring/pipeline.py

import os
import json
import traceback
import re

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


def _sanitize_transcription(question: str, raw_answer: str) -> str:
    """
    Uses a lightweight LLM call to correct Speech-to-Text acoustic glitches,
    phonetic typos, and repeated phrase loops before evaluation.
    """
    if not raw_answer.strip() or len(raw_answer.split()) < 4:
        return raw_answer

    from backend.utils.llm_client import ask_llm

    prompt = f"""You are an advanced Audio Transcription Post-Processor for a technical interview system.
The candidate's answer was transcribed from audio and contains phonetic glitches, repeated sentence loops, and acoustic errors.

Context Question: {question}
Glitched Raw Transcript: "{raw_answer}"

Tasks:
1. Fix words that sound phonetically similar to technical terms but were transcribed wrong (e.g., 'scabal' -> 'scalable', 'stole' -> 'stored', 'John Ray' -> 'genre', 'fleeing' -> 'frame', 'sea ghost' -> 'XGBoost').
2. Remove broken, identical phrase loops caused by audio capture glitches (e.g. loops of 'I'm going to turn it to you now').
3. Smooth out grammar, but keep the candidate's original intent, vocabulary choice, and exact level of detail. Do NOT add new technical concepts or make the answer smarter than it is.

Return ONLY the clean, corrected transcript text. No preamble, no explanation.
"""
    return ask_llm(prompt).strip()


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
            processed_answer = _sanitize_transcription(question, echo_cleaned)
            print(f"  [Sanitized Text]: {processed_answer[:60]}...")

            word_count = len(processed_answer.split())

            if word_count < 4:
                print(
                    f"  [Short-Circuit] Answer is too trivial ({word_count} words). Skipping model calls."
                )
                return {
                    "question_no": question_no,
                    "question_type": q_type,
                    "question": question,
                    "answer": answer,
                    "status": "success",
                    "score": 1.0,
                    "band": "Weak",
                    "similarity": 1.0,
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
