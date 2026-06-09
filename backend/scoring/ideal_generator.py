import re
from backend.utils.llm_client import ask_llm


def generate_key_concepts(question: str, profile: dict) -> str:
    """
    Returns a short paragraph listing the CONCEPTS a correct answer should
    cover — written in plain descriptive language, not as a model answer.
    """
    skills = ", ".join(profile.get("skills", [])[:8])

    # ── FIXED LINE ────────────────────────────────────────────────────────────
    # Handles both situations: if project is a dictionary or just a raw string
    raw_projects = profile.get("projects", [])[:4]
    project_names = [
        p.get("name", "") if isinstance(p, dict) else str(p) for p in raw_projects
    ]
    projects = ", ".join(project_names)
    # ──────────────────────────────────────────────────────────────────────────

    prompt = f"""You are evaluating a technical interview answer.

Question: {question}

Candidate background — Skills: {skills} | Projects: {projects}

Write a SHORT paragraph (3-5 sentences) that describes the KEY CONCEPTS
a correct answer to this question must cover.

Rules:
- Do NOT write a sample answer.
- Do NOT write what the candidate should say word-for-word.
- DO describe the underlying ideas, principles, or facts that show understanding.
- If it is a project question, list the technical aspects (architecture,
  tech choices, challenges, outcomes) that indicate real hands-on work.
- Be specific to this exact question.

Return ONLY the concept paragraph, no preamble.
"""
    return ask_llm(prompt).strip()
