import json
import re
from app.services.llm_service import generate_response

LANG_NAMES = {"c": "C", "cpp": "C++", "python": "Python", "java": "Java", "csharp": "C#", "javascript": "JavaScript", "go": "Go"}


def _extract_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def analyzer_agent(code: str, language: str = "c", execution_result: dict = None) -> dict:
    lang_name = LANG_NAMES.get(language, language.upper())

    # Ground the LLM in the real compiler verdict to stop hallucination
    exec_context = ""
    if execution_result and not str(execution_result.get("compile_error") or "").startswith("Sandbox failure"):
        if execution_result.get("compile_error"):
            exec_context = (
                f"COMPILER VERDICT: FAILED TO COMPILE.\n"
                f"Compiler error: {execution_result['compile_error']}\n"
                f"Only report syntax errors that match the compiler output above. Do not add extras.\n"
            )
        else:
            runtime_out = execution_result.get("runtime_output") or "(no stdout)"
            exec_context = (
                f"COMPILER VERDICT: COMPILED AND RAN SUCCESSFULLY. stdout={runtime_out}\n"
                f"Because this code compiled, syntax_errors MUST be an empty list [].\n"
                f"Do NOT invent any syntax errors.\n"
            )

    prompt = f"""You are a precise {lang_name} static analysis tool. Report only CONFIRMED, DEFINITE issues.

{exec_context}
RULES:
1. Only report issues 100% certain and present in the exact code shown. No speculation.
2. Do NOT flag theoretical risks ("could overflow", "might fail") — only things that WILL cause a problem.
3. Do NOT flag missing error handling (unchecked scanf, no overflow guard) — these are optional patterns, not bugs.
4. Do NOT invent issues. An empty list [] is a correct and valid result.
5. Do NOT flag style preferences or variable naming.
6. Simple correct code should have ALL THREE lists empty.

Return STRICT JSON ONLY — no markdown, no text outside the braces:
{{
    "syntax_errors": [],
    "logical_errors": [],
    "inefficiencies": [],
    "summary": "one sentence summary of code quality"
}}

{lang_name} code:
{code}
"""

    response = generate_response(prompt, "llama-3.3-70b-versatile", 400)
    cleaned = _extract_json(response)

    try:
        parsed = json.loads(cleaned)
        return {
            "syntax_errors":  parsed.get("syntax_errors", []),
            "logical_errors": parsed.get("logical_errors", []),
            "inefficiencies": parsed.get("inefficiencies", []),
            "summary":        parsed.get("summary", "Analysis completed.")
        }
    except Exception:
        return {
            "syntax_errors": [],
            "logical_errors": [],
            "inefficiencies": [],
            "summary": f"Analysis error — raw response: {response[:300]}"
        }