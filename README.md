# Metacognitive AI Tutor

A chat-based AI tutor prototype for higher-education learners. It is designed
to keep the learner as the author and verifier of their own thinking.

**Current stage: foundation only.** The app is a basic chat that sends
messages to Google Gemini. The tutor logic (judge, critique, learner state)
comes in later stages.

## Setup

Requires Python 3.10+ and a free Gemini API key from
https://aistudio.google.com/apikey.

```bash
git clone https://github.com/snehawadhwa1992/metacog-tutor.git
cd metacog-tutor
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and paste your key after `GEMINI_API_KEY=`.

## Run

```bash
.venv/bin/streamlit run app.py
```

The app opens at http://localhost:8501. It only listens on localhost, and
Streamlit usage statistics are turned off (see `.streamlit/config.toml`).

## Project layout

- `app.py`: Streamlit chat interface
- `llm.py`: the single function all model calls go through
- `prompts/`: prompt text files (no prompts are hardcoded in Python)

## Known limits

- Not yet tested with real learners.
- Individual differences (anxiety, neurodivergence, prior experience) are not
  yet accounted for; the same behaviors apply to everyone for now.
