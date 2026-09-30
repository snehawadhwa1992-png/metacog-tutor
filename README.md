# Metacognitive AI Tutor

A chat-based AI tutor prototype for higher-education learners. It keeps the
learner as the author and verifier of their own thinking. Its goal is a
lasting change in how the learner thinks, not the quality of any single answer
produced in a session. A polished answer that leaves the learner no more
capable than before counts as a failure.

Designed by [Sneha Wadhwa](https://github.com/snehawadhwa1992-png), built with
[Claude Code](https://claude.com/claude-code).

**Status:** working prototype. The chat, prompt assembly, judge step, and error
handling are built. See [Testing so far](#testing-so-far) for exactly what has
been tested and how.


## Design decisions

The guiding question behind every reply: can the learner generate, inspect,
compare, challenge, justify, improve, and transfer an answer, rather than just
receive one?

### The four non-negotiables

All four apply on every turn at the same time. They are not steps taken in
order.

**1. The learner's thinking comes first.** If the learner hasn't made a real
attempt (a claim, a step, or a piece of reasoning) anywhere in the
conversation, the tutor doesn't give the complete answer, even when asked
directly. It offers the smallest useful move that helps them begin. Explaining
a concept the learner hasn't met yet is allowed, because that is different
from giving the answer to the task.
*Why:* the generation effect and productive struggle. Producing an answer
yourself tends to be remembered and understood better than reading one.

**2. The learner checks their own work before the tutor does.** Before
evaluating the learner's work, the tutor asks them to check it first, for
example by predicting whether it is right and why. Then it gives its own
check and says openly that it is checking.
*Why:* metacognitive monitoring and calibration. Learners improve when they
practice judging their own work and compare that judgment with feedback.

**3. Support must not make the learner look more capable than they are.**
Success with the tutor's help is not treated as independent mastery. The
tutor periodically steps back its support, bases any statement about mastery
on work the learner did without help, and asks the learner to justify stated
confidence.
*Why:* illusions of competence and fading scaffolds. Guided success can feel
like understanding, so support has to be withdrawn to see what the learner
can do alone.

**4. Whose idea is whose stays visible.** The tutor asks for the learner's
idea before adding its own, marks every substantive idea it contributes as
its own, and asks the learner what they added or changed before treating
shared work as final.
*Why:* source monitoring and ownership of ideas. People readily misremember
where an idea came from, and learners should know which thinking was theirs.

### The metacognitive moves

The tutor uses four kinds of moves:
- **Inquiry:** a question that invites the learner to notice or check their
  own thinking.
- **Reflection:** describing the learner's reasoning back to them so they see
  its shape.
- **Self-explanation:** asking the learner to explain their reasoning before
  or after an attempt.
- **Choice points:** offering real alternative approaches and asking the
  learner to pick one and justify it.

Rules: task progress comes first; no more than one question-only reply in a
row; every question has a clear purpose; and the tutor says plainly when it
changes approach.
*Why:* self-explanation and reflection. Explaining and examining your own
reasoning helps build understanding that transfers to new problems. The
question-only limit guards against questioning that stalls real progress.


## Architecture

```
app.py            Streamlit chat UI and sidebar; JUDGE_ENABLED switch
prompt_loader.py  Loads prompt files and assembles the tutor prompt
judge.py          Judge call, safe JSON parsing, evidence quote check
llm.py            The one function all model calls go through
prompts/          All prompt text (none is hardcoded in Python)
tests/            Offline tests (no API calls)
```

### Prompt assembly

All prompt text lives in `/prompts`:
- `base.txt`: who the tutor is, tone, honesty rules, the care boundary, and a
  one-sentence summary of each non-negotiable. Always sent.
- One module per non-negotiable, plus `metacognitive_moves.txt`. Each module
  has a "When this applies" section (with "Does not count" examples) and a
  "What the tutor does" section.
- `judge.txt`: the judge's instructions.

`visible_authorship.txt` and `metacognitive_moves.txt` are always sent with
`base.txt`, because they govern what the tutor itself is about to say, which
a judge running beforehand cannot see. The other three modules are added
when the judge flags them.

### The judge step (currently off)

When on, each turn makes a judge call before the tutor call. The judge reads
the conversation and returns JSON: whether a real attempt is present, whether
the learner has self-checked, the type of the latest request, which of the
three optional modules to include, and a quote from the learner as evidence
for each judgment.

The judge's criteria are not written in `judge.txt`. They are loaded at
runtime from the "When this applies" sections of the module files, so each
rule has one source of truth. If the judge's reply can't be parsed, or the
call fails, the turn continues with no flagged modules and a warning in the
sidebar.

**Evidence quote check:** the code checks that every quote the judge gives
actually appears in the learner's messages (ignoring spacing, capitals, and
curly versus straight quotes). Quotes it can't find are flagged in the
sidebar, so an invented quote is visible rather than silently trusted.

**Why it's off:** the judge doubles the model calls per turn, which uses up
the Gemini free tier quickly. With `JUDGE_ENABLED = False` (top of `app.py`),
the tutor gets `base.txt` plus all five modules in one call, and the sidebar
shows "Judge: off". The judge code stays in the repo; set
`JUDGE_ENABLED = True` to switch it back on. The judge has been built and
tested offline only.

### Error handling

In `llm.py`:
- **503 (service busy):** retried up to 2 times, after 2 and 4 seconds.
- **Still busy after retries:** one attempt on a lighter fallback model
  (`FALLBACK_MODEL`, set at the top of `llm.py`). If that is busy too, the
  learner sees "The AI service is busy right now. Please wait a moment and try
  again."
- **429 / RESOURCE_EXHAUSTED (quota used up):** never retried and never sent
  to the fallback, since retrying only uses more quota. The learner sees "Free
  usage limit reached, please wait and try again."
- **Missing API key:** the app shows a clear message instead of crashing.

The retry and fallback logic has been tested offline with simulated errors.
The fallback model has not yet been called live.


## Next steps

- **Learner state**, tracked in code for the session:
  - a contribution ledger (learner ideas vs. tutor ideas);
  - a log of assisted vs. independent attempts;
  - a count of consecutive question-only tutor replies, so the one-in-a-row
    limit is enforced in code rather than left to the model.
- **Critique call:** when the judge flags that a non-negotiable is under
  strain, a second pass reviews the tutor's draft (assumptions, evidence,
  overstatement) and revises it before sending.

Both depend on the judge being on. The judge supplies the per-turn signals
(whether an attempt or self-check happened, with learner quotes as evidence)
that the ledger and log would record, and the critique call is triggered by
the judge's "under strain" flag, which will be added with it. Without the
judge, there is nothing reliable to record or to trigger on.


## Quickstart

You need Python (tested with 3.14), git, and a free Gemini API key from
[Google AI Studio](https://aistudio.google.com/apikey).

```bash
git clone https://github.com/snehawadhwa1992-png/metacog-tutor.git
cd metacog-tutor
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and paste your key after `GEMINI_API_KEY=`. The `.env` file is
excluded from git and never committed.

```bash
.venv/bin/streamlit run app.py
```

The app opens at http://localhost:8501. It only listens on localhost, and
Streamlit usage statistics are turned off (`.streamlit/config.toml`).

The default model is set in `llm.py`. To use a different one, add
`GEMINI_MODEL=<model name>` to `.env`.

### Tests

Offline checks for the judge, prompt assembly, and error handling. They make
no API calls.

```bash
.venv/bin/python tests/test_judge.py
```


## Testing so far

- **Live:** three conversations with the base prompt only (before the modules
  were added): a request with no attempt, asking again for the answer, and
  asking for a concept explanation. All three behaved as intended.
- **Offline only:** the judge (JSON parsing, module validation, quote check),
  prompt assembly, and the retry and fallback logic (`tests/test_judge.py`).


## Known limits

- Not yet tested with real learners.
- Individual differences (anxiety, neurodivergence, prior experience) are not
  yet accounted for; the same behaviors apply to everyone for now.
- Possible drift in long conversations: the whole conversation is resent on
  every turn, and the tutor may follow the rules less consistently as the
  history grows.
- Free-tier rate limits: heavy use can hit the Gemini quota, and the service
  is sometimes busy. The app shows a clear message in both cases.
