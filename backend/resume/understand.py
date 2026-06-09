import json
import re

from backend.utils.llm_client import ask_llm


def extract_json(text):

    text = text.strip()

    text = re.sub(r"```json", "", text)
    text = re.sub(r"```",     "", text)

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise Exception("No JSON found in LLM response")

    raw = match.group()

    # Fix invalid JSON escape sequences.
    # Resumes often contain Windows paths (C:\Users), LaTeX (\textbf),
    # or other backslash sequences that the LLM copies verbatim into JSON.
    # Valid JSON escapes are: \" \\ \/ \b \f \n \r \t \uXXXX
    # Anything else must be double-escaped.
    raw = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)

    return raw


def understand_resume(text):

    prompt = f"""

Extract resume information.

Return STRICT VALID JSON ONLY.

Format:

{{
"skills":[],

"projects":[],

"experience":[],

"education":[],

"certifications":[],

"achievements":[],

"research_publications":[],

"patents":[],

"co_curricular":[]

}}

Rules:

Achievements:
Hackathons
Competitions
Awards
Leadership roles

Research Publications:
Published papers
Conference papers
Journal papers

Patents:
Filed patents
Granted patents

Co Curricular:
Clubs
Leadership
Volunteering
Technical communities

Resume:

{text}

ONLY JSON

NO markdown

NO explanation

"""

    result = ask_llm(prompt)

    try:

        cleaned = extract_json(result)
        parsed  = json.loads(cleaned)
        return parsed

    except Exception as e:

        print("\nRAW MODEL OUTPUT:\n")
        print(result)
        raise Exception(f"JSON parse failed: {e}")