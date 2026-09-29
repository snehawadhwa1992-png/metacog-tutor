"""The judge step: reads the conversation and decides which modules to include.

The judge's criteria come only from the "When this applies" sections of the
module files, inserted into prompts/judge.txt at runtime.
"""

import json

import llm
from prompt_loader import load_prompt, when_this_applies

# The only modules the judge may flag. The other two are always included.
JUDGED_MODULES = ["learner_thinking_first", "learner_checks_first", "no_inflated_ability"]

REQUEST_TYPES = {
    "asking_for_answer",
    "asking_to_understand_concept",
    "asking_for_check",
    "sharing_work",
    "stating_confidence",
    "other",
}

EVIDENCE_FIELDS = ["attempt_evidence", "self_check_evidence", "request_type_evidence"]


def build_judge_prompt():
    """Fill judge.txt's {{CRITERIA}} marker with the three modules' criteria."""
    criteria = "\n\n".join(
        f"MODULE: {name}\n{when_this_applies(name)}" for name in JUDGED_MODULES
    )
    return load_prompt("judge.txt").replace("{{CRITERIA}}", criteria)


def format_transcript(messages):
    """Turn the chat into one labeled text block for the judge to read."""
    return "\n\n".join(
        f"{'Learner' if m['role'] == 'user' else 'Tutor'}: {m['content']}"
        for m in messages
    )


def _normalize(text):
    """Lowercase, collapse whitespace, and treat curly quotes as straight ones."""
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    return " ".join(text.split()).lower()


def find_unverified_quotes(verdict, messages):
    """Return evidence quotes that do not appear in any learner message."""
    learner_text = _normalize(" ".join(m["content"] for m in messages if m["role"] == "user"))
    quotes = [verdict.get(field) for field in EVIDENCE_FIELDS]
    quotes += [m.get("evidence") for m in verdict.get("modules") or [] if isinstance(m, dict)]
    return [
        q for q in quotes
        if isinstance(q, str) and q.strip() and _normalize(q) not in learner_text
    ]


def parse_verdict(raw, messages):
    """Safely parse the judge's reply. Never raises.

    Returns a dict with:
      judge:    the parsed JSON (or None if it could not be parsed)
      raw:      the judge's raw text, for debugging when parsing fails
      modules:  validated list of module names to include
      warnings: messages to show in the sidebar
    """
    result = {"judge": None, "raw": raw, "modules": [], "warnings": []}

    # Strip a Markdown code fence in case the model added one anyway.
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()

    try:
        verdict = json.loads(text)
    except ValueError:
        result["warnings"].append("The judge did not return valid JSON, so no modules were flagged this turn.")
        return result
    if not isinstance(verdict, dict):
        result["warnings"].append("The judge's JSON was not an object, so no modules were flagged this turn.")
        return result
    result["judge"] = verdict

    # Keep only known module names, each at most once.
    entries = verdict.get("modules") or []
    if not isinstance(entries, list):
        result["warnings"].append("The judge's 'modules' field was not a list, so it was ignored.")
        entries = []
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else entry
        if name in JUDGED_MODULES:
            if name not in result["modules"]:
                result["modules"].append(name)
        else:
            result["warnings"].append(f"The judge named an unknown module ({name!r}), so it was ignored.")

    if verdict.get("request_type") not in REQUEST_TYPES:
        result["warnings"].append(f"Unknown request type: {verdict.get('request_type')!r}.")

    # Flag quotes the judge may have invented. This does not change the modules.
    for quote in find_unverified_quotes(verdict, messages):
        result["warnings"].append(f"Evidence not found in learner text: \"{quote}\"")

    return result


def run_judge(messages):
    """Run the judge on the conversation. Never raises for API or JSON problems."""
    try:
        raw = llm.generate(
            build_judge_prompt(),
            [{"role": "user", "content": format_transcript(messages)}],
            json_output=True,
        )
    except llm.LLMError as e:
        return {
            "judge": None,
            "raw": None,
            "modules": [],
            "warnings": [f"The judge call failed, so no modules were flagged this turn. {e}"],
        }
    return parse_verdict(raw, messages)
