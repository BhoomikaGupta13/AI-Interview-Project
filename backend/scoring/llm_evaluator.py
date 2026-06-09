# backend/scoring/llm_evaluator.py

import json
import re
from backend.utils.llm_client import ask_llm


def _parse_json(text: str) -> dict:
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON in LLM response: {text[:200]}")


def evaluate_answer(
    question: str, answer: str, profile: dict, similarity_score: float
) -> dict:
    skills = ", ".join(profile.get("skills", [])[:8])
    raw_projects = profile.get("projects", [])[:4]
    project_names = [
        p.get("name", "") if isinstance(p, dict) else str(p) for p in raw_projects
    ]
    projects = ", ".join(project_names)

    prompt = f"""You are a master technical interviewer checking a candidate's response context.

Interview question: {question}
Candidate's answer: "{answer}"
Our vector system computed a raw semantic similarity score of: {similarity_score:.4f} (on a scale of 0.0 to 1.0)

Profile Baseline:
Skills: {skills} | Projects: {projects}

YOUR CRITICAL EVALUATION RULES (SEMANTIC CALIBRATION):
1. RECOGNIZE KNOWLEDGE WITHOUT BUZZWORDS:
   - If the similarity score is relatively low (e.g. under 0.65) but you see they explained the exact mechanics accurately using their own vocabulary, reward "correctness" highly.
2. AUDIT KEYWORD SOUP & GIBBERISH:
   - If the similarity score is high (e.g. over 0.70) but you observe that the candidate generated that score simply by listing keywords out of context or dropping a brief, superficial statement fragment (e.g., "I used tfidf factorization"), you must override that high similarity. Override it by dropping the "correctness" and "completeness" criteria straight down to 1 or 2.
3. MINOR TRANSCRIPTION ERRORS:
   - Ignore slight audio transcription typos if the primary technical argument remains structurally visible.

Score each dimension out of 10:
- clarity: logical delivery of engineering concepts.
- correctness: true system accuracy. Set to a max of 2 if keywords are used incorrectly or dropped without explanation.
- completeness: did they cover the required problem constraints?

Return STRICT JSON only:
{{
  "clarity": <int 0-10>,
  "correctness": <int 0-10>,
  "completeness": <int 0-10>,
  "feedback": "<Identify if they are using buzzwords deceptively or explaining logic cleanly>",
  "strengths": ["<logical accuracy points, or empty list>"],
  "improvements": ["<concepts missing to verify authentic knowledge>"]
}}
"""
    raw = ask_llm(prompt)
    result = _parse_json(raw)

    dims = ["clarity", "correctness", "completeness"]
    llm_score = sum(result.get(d, 0) for d in dims) / (len(dims) * 10)
    result["llm_score"] = round(llm_score, 4)
    return result
