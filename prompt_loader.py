"""Loads prompt files from /prompts and assembles the tutor's system prompt.

No prompt text lives in Python: everything is read from the text files.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Modules sent with base.txt on every turn. The judge runs before the tutor
# replies, so it cannot decide these (see CLAUDE.md, Architecture).
ALWAYS_MODULES = ["visible_authorship", "metacognitive_moves"]

# All five modules. When the judge is off, the tutor gets all of them every turn.
ALL_MODULES = ALWAYS_MODULES + [
    "learner_thinking_first",
    "learner_checks_first",
    "no_inflated_ability",
]

# Headings that mark the judge's criteria inside each module file.
WHEN_HEADING = "WHEN THIS APPLIES"
WHAT_HEADING = "WHAT THE TUTOR DOES"


def load_prompt(filename):
    """Read a prompt text file from the /prompts folder."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def when_this_applies(module):
    """Return a module's "When this applies" section (including "Does not count").

    This is the text between the WHEN THIS APPLIES and WHAT THE TUTOR DOES
    headings. Raises ValueError if either heading is missing, so the judge is
    never silently given empty criteria.
    """
    text = load_prompt(f"{module}.txt")
    if WHEN_HEADING not in text or WHAT_HEADING not in text:
        raise ValueError(
            f"prompts/{module}.txt must contain the headings "
            f"'{WHEN_HEADING}' and '{WHAT_HEADING}'."
        )
    start = text.index(WHEN_HEADING) + len(WHEN_HEADING)
    end = text.index(WHAT_HEADING)
    return text[start:end].strip()


def build_tutor_prompt(flagged_modules):
    """Combine base.txt, the always-on modules, and any modules the judge flagged.

    Returns (system_prompt, names_used) so the sidebar can show what was sent.
    """
    extra = [m for m in flagged_modules if m not in ALWAYS_MODULES]
    names = ["base"] + ALWAYS_MODULES + extra
    system_prompt = "\n\n\n".join(load_prompt(f"{n}.txt").strip() for n in names)
    return system_prompt, names
