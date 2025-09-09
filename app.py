import os
import json
import streamlit as st
from agent.openai_agent import Agent
from affinity.client_v2 import AffinityV2

st.set_page_config(page_title="Affinity AI Agent (v2)", page_icon="🤖", layout="centered")
st.title("🤖 Affinity AI Agent — v2 only")

# --- Secrets / env
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
AFFINITY_V2_BEARER = st.secrets.get("AFFINITY_V2_BEARER") or os.getenv("AFFINITY_V2_BEARER")

if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY not set. Add it to Streamlit secrets or your environment.")
    st.stop()
if not AFFINITY_V2_BEARER:
    st.error("AFFINITY_V2_BEARER not set. Add it to Streamlit secrets or your environment.")
    st.stop()

# --- Initialize API client
v2 = AffinityV2(api_key=AFFINITY_V2_BEARER)
agent = Agent(openai_api_key=OPENAI_API_KEY, affinity_v2=v2)

# --- Diagnostics
with st.expander("Diagnostics"):
    def _flag(ok: bool) -> str:
        return "✅" if ok else "❌"
    st.write(f"OpenAI key loaded: {_flag(bool(OPENAI_API_KEY))}")
    st.write(f"Affinity v2 key loaded: {_flag(bool(AFFINITY_V2_BEARER))}")
    if st.button("Test Affinity v2 /auth/whoami"):
        try:
            st.json(v2.whoami())
        except Exception as e:
            st.error("whoami failed — see details below")
            st.exception(e)

# --- Chat state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": agent.system_prompt},
        {"role": "assistant", "content": "Hi! I can read notes, find list/company IDs, and update list fields via Affinity v2. Create actions (add company, add note, add to list) are not exposed in v2 per the docs you shared; I'll tell you what to do when you try them."},
    ]

# Render history (skip system)
for m in st.session_state.messages:
    if m["role"] == "system":
        continue
    with st.chat_message("assistant" if m["role"] == "assistant" else "user"):
        if isinstance(m["content"], str):
            st.markdown(m["content"])
        else:
            st.json(m["content"])  # for structured tool output

# Input
user_input = st.chat_input("Ask me to e.g. 'Find the list id for My Companies' or 'Set Stage for list entry 123' or 'Show notes for company 456'.")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                final_msg, tool_events = agent.run(st.session_state.messages)
                for evt in tool_events:
                    with st.expander(f"{evt['name']}"):
                        st.json(evt)
                st.markdown(final_msg)
            except Exception as e:
                st.error("The agent encountered an unexpected error. Check your keys and logs.")
                st.exception(e)
    st.session_state.messages.append({"role": "assistant", "content": final_msg if 'final_msg' in locals() else "(failed to produce a response)"})
