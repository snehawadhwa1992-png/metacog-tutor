"""Streamlit chat interface for the Metacognitive AI Tutor (foundation stage).

Run with:  streamlit run app.py
"""

from pathlib import Path

import streamlit as st

import llm

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name):
    """Read a prompt text file from the /prompts folder."""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


st.set_page_config(page_title="Metacognitive AI Tutor")
st.title("Metacognitive AI Tutor")

# Stop early with a clear message if the API key is missing.
try:
    llm.get_api_key()
except llm.MissingAPIKeyError as e:
    st.error(str(e))
    st.info("You can copy .env.example to .env if the .env file does not exist.")
    st.stop()

# Placeholder sidebar: judge output and learner state will appear here later.
with st.sidebar:
    st.header("Tutor internals")
    st.caption("Judge output and learner state will appear here in a later stage.")

# Chat history lives in the session, so it resets when the page is reloaded.
if "messages" not in st.session_state:
    st.session_state.messages = []

# Show the conversation so far.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle a new learner message.
if user_text := st.chat_input("Type your message"):
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                reply = llm.generate(load_prompt("base.txt"), st.session_state.messages)
            except llm.LLMError as e:
                st.error(str(e))
                # Drop the unanswered message so the history stays consistent.
                st.session_state.messages.pop()
                st.stop()
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
