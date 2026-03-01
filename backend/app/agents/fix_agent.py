import json
import re
from app.services.llm_service import generate_response

LANG_NAMES = {"c": "C", "cpp": "C++", "python": "Python", "java": "Java", "csharp": "C#"}


def fix_agent(code: str, language: str = "c") -> str:
    lang_name = LANG_NAMES.get(language, language.upper())

    prompt = f"""You are an expert {lang_name} debugger. Analyze the code carefully.

STRICT RULES:
- Only report REAL, CONFIRMED bugs — syntax errors, logical bugs, or definite runtime crashes.
- Do NOT invent problems. Do NOT suggest stylistic improvements.
- Do NOT flag missing error-handling (e.g. unchecked scanf, no overflow check) as bugs.
- If the code is correct, return the "no bug" JSON format below.

Return STRICT JSON ONLY — no markdown, no text outside JSON:

IF A REAL BUG EXISTS:
{{
    "issue": "brief description of the confirmed bug",
    "corrected_code": "COMPLETE corrected code here",
    "explanation": "clear explanation of what was wrong and what was fixed"
}}

IF NO BUG EXISTS:
{{
    "issue": null,
    "corrected_code": null,
    "explanation": "The code is correct and does not require any fixes."
}}

corrected_code rules:
- Write the FULL corrected file, not just a snippet.
- Use \\n between lines. NEVER put a literal newline inside a quoted string.
- CORRECT: printf("Hello\\n");   WRONG: splitting "Hello\n" across two lines.

Code to analyze ({lang_name}):
{code}
"""

    # Upgraded model + more tokens so full corrected code is never cut off
    response = generate_response(prompt, "llama-3.3-70b-versatile", 800)

    response = response.strip()
    response = re.sub(r"^```json\s*", "", response, flags=re.MULTILINE)
    response = re.sub(r"^```\s*", "", response, flags=re.MULTILINE)
    response = re.sub(r"```\s*$", "", response, flags=re.MULTILINE)
    response = response.strip()

    match = re.search(r"\{.*\}", response, re.DOTALL)
    if match:
        response = match.group(0)

    try:
        parsed = json.loads(response)
        issue = parsed.get("issue")
        corrected_code = parsed.get("corrected_code")
        explanation = parsed.get("explanation")

        if not issue:
            return json.dumps({
                "issue": None, "corrected_code": None,
                "explanation": explanation or "The code is correct and does not require any fixes."
            })

        # Decode escaped newlines so frontend renders real code
        if corrected_code and isinstance(corrected_code, str):
            corrected_code = corrected_code.replace("\\n", "\n").replace("\\t", "\t")
            # Rejoin any lines incorrectly split inside string literals
            fixed_lines = []
            pending = None
            for line in corrected_code.split("\n"):
                if pending is not None:
                    pending += line
                    if pending.count('"') % 2 == 0:
                        fixed_lines.append(pending)
                        pending = None
                else:
                    if line.count('"') % 2 != 0:
                        pending = line
                    else:
                        fixed_lines.append(line)
            if pending is not None:
                fixed_lines.append(pending)
            corrected_code = "\n".join(fixed_lines)

        return json.dumps({"issue": issue, "corrected_code": corrected_code, "explanation": explanation})

    except json.JSONDecodeError:
        issue_match = re.search(r'"issue"\s*:\s*"([^"]+)"', response)
        explanation_match = re.search(r'"explanation"\s*:\s*"([^"]+)"', response)
        corrected_match = re.search(r'"corrected_code"\s*:\s*(.*?)(?=\s*"explanation")', response, re.DOTALL)

        corrected_code = None
        if corrected_match:
            corrected_code = corrected_match.group(1).strip().strip(",").strip('"')

        return json.dumps({
            "issue": issue_match.group(1) if issue_match else None,
            "corrected_code": corrected_code,
            "explanation": explanation_match.group(1) if explanation_match else "Unable to parse explanation."
        })