import json
import re

from backend.utils.llm_client import (
    ask_llm
)


def extract_json(text):

    text = re.sub(
        r"```json",
        "",
        text
    )

    text = re.sub(
        r"```",
        "",
        text
    )

    match = re.search(

        r"\[.*\]",

        text,

        re.DOTALL
    )

    if match:

        return match.group()

    raise Exception(
        "No JSON found"
    )


def generate_questions(

    profile,

    blueprint
):

    prompt = f"""

Candidate Profile:

{profile}

Question Distribution:

{blueprint}

Generate interview questions.

Rules:

Projects:
Ask architecture
tech stack
challenges

Skills:
Ask concept and conceptual depth

Experience:
Ask work details

Research Publication:
If exists ask exactly 1 question

Patent:
If exists ask exactly 1 question

Do NOT ask duplicate questions.

Return STRICT JSON ARRAY.

Example:

[
"Question 1",
"Question 2"
]

ONLY JSON

"""

    result = ask_llm(
        prompt
    )

    cleaned = extract_json(
        result
    )

    return json.loads(
        cleaned
    )