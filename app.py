import os
import json
import streamlit as st
from agent.openai_agent import Agent
from affinity.client_v2 import AffinityV2
from affinity.client_v1 import AffinityV1

st.set_page_config(page_title="Affinity AI Agent", page_icon="🤖", layout="centered")
st.title("🤖 Affinity AI Agent")

# --- Secrets / env
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
AFFINITY_V2_BEARER = st.secrets.get("AFFINITY_V2_BEARER") or os.getenv("AFFINITY_V2_BEARER")
# Optional: legacy v1 for create actions
AFFINITY_V1_KEY = st.secrets.get("AFFINITY_V1_KEY") or os.getenv("AFFINITY_V1_KEY")

if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY not set. Add it to Streamlit secrets or your environment.")
    st.stop()
if not AFFINITY_V2_BEARER:
    st.warning("AFFINITY_V2_BEARER not set. Read-only and field updates will fail. Set it in secrets.")

# --- Initialize API clients
v2 = AffinityV2(api_key=AFFINITY_V2_BEARER)
v1 = AffinityV1(api_key=AFFINITY_V1_KEY) if AFFINITY_V1_KEY else None
agent = Agent(openai_api_key=OPENAI_API_KEY, affinity_v2=v2, affinity_v1=v1)

# --- Chat stated
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": agent.system_prompt},
        {"role": "assistant", "content": "Hi! I can create companies, add/read notes, manage lists, and update fields in Affinity. What would you like to do?"},
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
user_input = st.chat_input("Ask me to e.g. 'Add Acme to My Companies' or 'Set Stage to Lead for entry 123 on List 77'.")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            final_msg, tool_events = agent.run(st.session_state.messages)
            # Show any tool event summaries
            for evt in tool_events:
                with st.expander(f"{evt['name']}"):
                    st.json(evt)
            st.markdown(final_msg)
    st.session_state.messages.append({"role": "assistant", "content": final_msg})
