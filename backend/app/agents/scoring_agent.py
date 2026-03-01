import json
import re
from app.services.llm_service import generate_response

LANG_NAMES = {"c": "C", "cpp": "C++", "python": "Python", "java": "Java", "csharp": "C#"}


def scoring_agent(code: str, language: str = "c", analysis: dict | None = None) -> dict:
    lang_name = LANG_NAMES.get(language, language.upper())

    # Only pass confirmed issues into scoring context — skip empty/hallucinated lists
    analysis_context = ""
    if analysis:
        real_issues = []
        if analysis.get("syntax_errors"):
            real_issues.append(f"Syntax errors: {'; '.join(analysis['syntax_errors'])}")
        if analysis.get("logical_errors"):
            real_issues.append(f"Logical errors: {'; '.join(analysis['logical_errors'])}")
        if analysis.get("inefficiencies"):
            real_issues.append(f"Inefficiencies: {'; '.join(analysis['inefficiencies'])}")
        if real_issues:
            analysis_context = "\n\nConfirmed issues from static analysis:\n" + "\n".join(real_issues)

    prompt = f"""You are an expert {lang_name} code evaluator. Score the code across four dimensions.

IMPORTANT: Be accurate and fair. Do not penalise code for missing optional defensive patterns (e.g. unchecked scanf, no overflow guard). Only penalise for actual confirmed problems.

Score each dimension 0–10 (integers). overall_score may be a decimal.

Return STRICT JSON ONLY — no markdown, no text outside JSON:
{{
    "syntax_score": 0-10,
    "logic_score": 0-10,
    "clarity_score": 0-10,
    "robustness_score": 0-10,
    "overall_score": 0-10
}}

{lang_name} code to score:
{code}{analysis_context}
"""

    response = generate_response(prompt, "llama-3.3-70b-versatile", 256)

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

        def clamp(v):
            return max(0, min(10, v)) if isinstance(v, (int, float)) else 0

        return {
            "syntax_score":     clamp(data.get("syntax_score", 0)),
            "logic_score":      clamp(data.get("logic_score", 0)),
            "clarity_score":    clamp(data.get("clarity_score", 0)),
            "robustness_score": clamp(data.get("robustness_score", 0)),
            "overall_score":    clamp(data.get("overall_score", 0)),
        }
    except json.JSONDecodeError:
        return {"error": "Invalid JSON returned by scoring agent.", "raw_response": response}