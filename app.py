"""Streamlit chat interface for the Metacognitive AI Tutor.

Each learner turn: judge call, then the tutor call with the assembled prompt.

Run with:  streamlit run app.py
"""

import streamlit as st

import judge
import llm
import prompt_loader

# Set to True to run the judge call before each tutor reply (two calls per turn).
# When False, the tutor gets base.txt plus all five modules in one call, which
# uses less of the free-tier quota.
JUDGE_ENABLED = False

st.set_page_config(page_title="Metacognitive AI Tutor")
st.title("Metacognitive AI Tutor")

# Stop early with a clear message if the API key is missing.
try:
    llm.get_api_key()
except llm.MissingAPIKeyError as e:
    st.error(str(e))
    st.info("You can copy .env.example to .env if the .env file does not exist.")
    st.stop()


def render_sidebar():
    """Show the latest turn's judge output and which modules were included."""
    with st.sidebar:
        st.header("Tutor internals")
        st.markdown(f"**Judge: {'on' if JUDGE_ENABLED else 'off'}**")
        turn = st.session_state.get("last_turn")
        if not turn:
            st.caption("Details will appear here after your first message.")
            return

        for warning in turn["warnings"]:
            st.warning(warning)

        st.subheader("Modules included")
        st.markdown("\n".join(f"- {name}" for name in turn["modules_used"]))

        if not JUDGE_ENABLED:
            return

        st.subheader("Judge output")
        if turn["judge"] is not None:
            st.json(turn["judge"])
        elif turn["raw"]:
            st.caption("Raw judge reply (could not be parsed):")
            st.code(turn["raw"])
        else:
            st.caption("No judge output this turn.")


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
            if JUDGE_ENABLED:
                # 1. Judge: decides which of the three optional modules apply.
                verdict = judge.run_judge(st.session_state.messages)
                modules = verdict["modules"]
            else:
                # Judge off: no judge call, send all five modules.
                verdict = {"judge": None, "raw": None, "modules": [], "warnings": []}
                modules = prompt_loader.ALL_MODULES

            # 2. Tutor: base + always-on modules + flagged (or all) modules.
            system_prompt, modules_used = prompt_loader.build_tutor_prompt(modules)
            st.session_state.last_turn = {**verdict, "modules_used": modules_used}
            try:
                reply = llm.generate(system_prompt, st.session_state.messages)
            except llm.LLMError as e:
                st.error(str(e))
                # Drop the unanswered message so the history stays consistent.
                st.session_state.messages.pop()
                reply = None
        if reply is not None:
            st.markdown(reply)

    if reply is not None:
        st.session_state.messages.append({"role": "assistant", "content": reply})

# Drawn last so it reflects the turn that just ran.
render_sidebar()
