"""Offline checks for the judge, prompt assembly, and retry logic.

Makes no API calls: model calls are replaced with fakes.
Run from the project folder:  .venv/bin/python tests/test_judge.py
"""

import json
import sys
from pathlib import Path

# Let this script import the project's modules from the folder above.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import judge  # noqa: E402
import llm  # noqa: E402
import prompt_loader  # noqa: E402

msgs = [
    {"role": "user", "content": "What's the answer to question 3?"},
    {"role": "assistant", "content": "What would you try first?"},
    {"role": "user", "content": "Just   tell me the answer please."},
]

# 1. Judge prompt is filled from the module files.
p = judge.build_judge_prompt()
assert "{{CRITERIA}}" not in p
for name in judge.JUDGED_MODULES:
    assert f"MODULE: {name}" in p
assert "Does not count" in p and "WHAT THE TUTOR DOES" not in p
print("judge prompt OK,", len(p.split()), "words")

# 2. Valid JSON, with one real quote, one invented quote, one unknown module.
good = {
    "attempt_present": False, "attempt_evidence": None,
    "self_checked": False, "self_check_evidence": None,
    "request_type": "asking_for_answer",
    "request_type_evidence": "just tell me the answer please",
    "modules": [
        {"name": "learner_thinking_first", "evidence": "What's the answer to question 3?"},
        {"name": "learner_thinking_first", "evidence": "What's the answer to question 3?"},
        {"name": "made_up_module", "evidence": "I solved it myself"},
    ],
}
r = judge.parse_verdict(json.dumps(good), msgs)
assert r["modules"] == ["learner_thinking_first"], r
assert any("made_up_module" in w for w in r["warnings"])
assert any("I solved it myself" in w for w in r["warnings"])
assert not any("just tell me" in w for w in r["warnings"])  # real quote passes
print("valid JSON OK")

# 3. Curly and straight quotes match each other, in both directions.
curly = dict(good, modules=[], request_type_evidence="What’s the answer to question 3?")
r = judge.parse_verdict(json.dumps(curly), msgs)
assert not any("not found" in w for w in r["warnings"]), r["warnings"]
curly_msgs = [{"role": "user", "content": "It’s “definitely” right"}]
straight = dict(good, modules=[], request_type_evidence='it\'s "definitely" right')
r = judge.parse_verdict(json.dumps(straight), curly_msgs)
assert not any("not found" in w for w in r["warnings"]), r["warnings"]
print("curly/straight quote matching OK")

# 4. Broken JSON, non-object JSON, fenced JSON.
r = judge.parse_verdict("not json {", msgs)
assert r["judge"] is None and r["modules"] == [] and r["warnings"]
r = judge.parse_verdict("[1, 2]", msgs)
assert r["judge"] is None and r["modules"] == []
r = judge.parse_verdict("```json\n" + json.dumps(good) + "\n```", msgs)
assert r["modules"] == ["learner_thinking_first"]
print("broken / non-object / fenced JSON OK")

# 5. Tutor prompt assembly, with the judge on (flagged) and off (all modules).
sp, names = prompt_loader.build_tutor_prompt(["learner_checks_first"])
assert names == ["base", "visible_authorship", "metacognitive_moves", "learner_checks_first"]
assert "NON-NEGOTIABLE 2" in sp and "NON-NEGOTIABLE 1:" not in sp
sp, names = prompt_loader.build_tutor_prompt(prompt_loader.ALL_MODULES)
assert names == ["base"] + prompt_loader.ALL_MODULES and len(names) == 6
for n in ("1:", "2:", "3:", "4:"):
    assert f"NON-NEGOTIABLE {n}" in sp
print("tutor prompt OK (flagged and all modules)")


# 6. Retry and fallback logic. Fake errors, no real waiting.
class FakeAPIError(Exception):
    def __init__(self, code, status):
        super().__init__(f"{code} {status}")
        self.code, self.status = code, status


llm.time.sleep = lambda seconds: None
MAIN, FALLBACK = "main-model", "fallback-model"
BUSY = FakeAPIError(503, "UNAVAILABLE")


def flaky(errors, result="ok"):
    """Return a fake call(model) that raises each error in turn, then succeeds.

    `models` records which model each attempt used.
    """
    models = []

    def call(model):
        models.append(model)
        if len(models) <= len(errors):
            raise errors[len(models) - 1]
        return result
    return call, models


def expect_error(call, error_type):
    """Run _with_retry and return the error it raises (fails if none)."""
    try:
        llm._with_retry(call, MAIN, FALLBACK)
    except error_type as e:
        return e
    raise AssertionError(f"expected {error_type.__name__}")


call, models = flaky([BUSY] * 2)
assert llm._with_retry(call, MAIN, FALLBACK) == "ok" and models == [MAIN] * 3
print("503 retried then main model succeeded OK")

call, models = flaky([BUSY] * 3)
assert llm._with_retry(call, MAIN, FALLBACK) == "ok" and models == [MAIN] * 3 + [FALLBACK]
print("503 after retries -> fallback succeeded OK")

call, models = flaky([BUSY] * 4)
e = expect_error(call, llm.LLMError)
assert not isinstance(e, llm.QuotaError) and str(e) == llm.BUSY_MESSAGE
assert models == [MAIN] * 3 + [FALLBACK]  # fallback tried once only
print("both models busy -> friendly busy message OK")

# If the main model already is the fallback, it is not tried a fourth time.
call, models = flaky([BUSY] * 3)
try:
    llm._with_retry(call, FALLBACK, FALLBACK)
    raise AssertionError("expected LLMError")
except llm.LLMError as err:
    assert str(err) == llm.BUSY_MESSAGE and models == [FALLBACK] * 3
print("fallback skipped when it is already the main model OK")

for err in (FakeAPIError(429, "RESOURCE_EXHAUSTED"), FakeAPIError(None, "RESOURCE_EXHAUSTED")):
    call, models = flaky([err])
    e = expect_error(call, llm.QuotaError)
    assert models == [MAIN] and str(e) == llm.QUOTA_MESSAGE
print("429 / RESOURCE_EXHAUSTED not retried, no fallback, clear message OK")

call, models = flaky([BUSY] * 3 + [FakeAPIError(429, "RESOURCE_EXHAUSTED")])
expect_error(call, llm.QuotaError)
print("429 on the fallback -> quota message OK")

call, models = flaky([FakeAPIError(400, "INVALID_ARGUMENT")])
e = expect_error(call, llm.LLMError)
assert not isinstance(e, llm.QuotaError) and models == [MAIN]
print("other errors fail once OK")

# 7. Judge call failure (including quota) -> warning, no modules, no crash.
def fail(*a, **k):
    raise llm.QuotaError(llm.QUOTA_MESSAGE)


llm.generate = fail
r = judge.run_judge(msgs)
assert r["modules"] == [] and llm.QUOTA_MESSAGE in r["warnings"][0]
print("judge call failure OK")

print("ALL TESTS PASSED")
