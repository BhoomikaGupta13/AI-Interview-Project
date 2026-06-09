# backend/scoring/lm_judge.py

import json
import re
from backend.utils.llm_client import ask_llm


def _parse_json(text: str) -> dict:
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON in judge response: {text[:200]}")


def judge_depth(question: str, answer: str, profile: dict) -> dict:
    if not answer.strip() or len(answer.split()) < 3:
        return {
            "architecture_depth": 0,
            "challenge_depth": 0,
            "outcome_specificity": 0,
            "tech_justification": 0,
            "depth_score": 0.0,
            "depth_feedback": "Answer was empty or omitted structural depth content entirely.",
        }

    raw_projects = profile.get("projects", [])[:4]
    standardized_projects = [
        p if isinstance(p, dict) else {"name": str(p)} for p in raw_projects
    ]
    projects_json = json.dumps(standardized_projects, indent=2)

    prompt = f"""You are a strict, senior engineering manager auditing an entry-level candidate's technical responses.
Your soul objective is parsing depth: separating surface-level phrase droppers from engineers with practical execution insights.

Question asked: {question}
Candidate spoken response text: "{answer}"
Candidate project profile: {projects_json}

CRITICAL RULES FOR GRADING PIPELINE DEPTH:
1. ANCHOR ON 'WHY' AND 'HOW', NOT COGNITIVE KEYWORDS:
   - Dropping terms like "NumPy", "OpenCV", "TFIDF", or "Cosine Similarity" inside simple 1-line fragments or detached declarations fails your engineering check. 
   - If keywords are spoken but lack contextual integration, operational execution, or architectural justification, score all criteria at 0 or 1.
2. VAGUENESS PENALIZATION:
   - Short sentences lacking explicit technical mechanics, architecture structures, edge challenges, or parameters must be graded heavily down.

Score each dimension 0-10:
- architecture_depth: conceptual structural breakdown.
- challenge_depth: detailing concrete engineering optimization roadblocks.
- outcome_specificity: concrete indicators, variables, or metrics.
- tech_justification: defending choices over alternative options.

Return STRICT JSON only:
{{
  "architecture_depth": <int 0-10>,
  "challenge_depth": <int 0-10>,
  "outcome_specificity": <int 0-10>,
  "tech_justification": <int 0-10>,
  "depth_feedback": "<State bluntly whether the candidate demonstrated engineering grasp or surface-level pattern mimicking>"
}}
"""
    raw = ask_llm(prompt)
    result = _parse_json(raw)

    dims = [
        "architecture_depth",
        "challenge_depth",
        "outcome_specificity",
        "tech_justification",
    ]
    avg = sum(result.get(d, 0) for d in dims) / (len(dims) * 10)
    result["depth_score"] = round(avg, 4)
    return result
