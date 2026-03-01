import json
import re
from app.services.llm_service import generate_response
from app.memory.memory_store import get_all_language_memory

LANG_NAMES = {"c": "C", "cpp": "C++", "python": "Python", "java": "Java", "csharp": "C#"}


def mistake_fixer_agent(user_id: str = "default_user", language: str = "c") -> dict:
    lang_name = LANG_NAMES.get(language, language.upper())

    full_memory = get_all_language_memory(user_id) or {}
    lang_memory = full_memory.get("by_language", {}).get(language, {})
    common_mistakes = lang_memory.get("common_mistakes", [])

    if not common_mistakes:
        return {
            "no_data": True,
            "questions": [],
            "mistakes_targeted": [],
            "language": lang_name
        }

    mistakes_str = "\n".join(f"- {m}" for m in common_mistakes)

    prompt = f"""You are a strict {lang_name} coding mentor reviewing a student's recurring mistake history.

Observed recurring {lang_name} mistakes:
{mistakes_str}

Generate exactly 5 targeted diagnostic exercises that directly address these mistakes.

Each exercise must:
- Address one of the listed mistakes specifically
- Ask the student to identify, explain, or fix a broken {lang_name} code snippet
- Be concise and direct

Return STRICT JSON ONLY — no markdown, no text outside JSON:
{{
    "questions": [
        {{
            "question": "Full exercise text with a short broken {lang_name} snippet if relevant",
            "targets": "Which mistake from the list this addresses"
        }}
    ]
}}

Rules: Exactly 5 questions. Valid JSON only.
"""

    # Upgraded model + enough tokens so all 5 questions are never truncated
    response = generate_response(prompt, "llama-3.3-70b-versatile", 1200)
    response = response.strip()
    response = re.sub(r"^```json\s*", "", response, flags=re.MULTILINE)
    response = re.sub(r"^```\s*", "", response, flags=re.MULTILINE)
    response = re.sub(r"```\s*$", "", response, flags=re.MULTILINE)
    response = response.strip()

    match = re.search(r"\{.*\}", response, re.DOTALL)
    if match:
        response = match.group(0)

    try:
        data = json.loads(response)
        questions = data.get("questions", [])
        if not isinstance(questions, list):
            questions = []

        cleaned = []
        for q in questions[:5]:
            if isinstance(q, dict) and "question" in q:
                cleaned.append({
                    "question": str(q.get("question", "")),
                    "targets":  str(q.get("targets", ""))
                })

        return {
            "no_data":           False,
            "questions":         cleaned,
            "mistakes_targeted": common_mistakes,
            "language":          lang_name
        }

    except json.JSONDecodeError:
        return {
            "no_data":           False,
            "questions":         [],
            "mistakes_targeted": common_mistakes,
            "language":          lang_name,
            "error":             "Failed to generate questions. Please try again."
        }