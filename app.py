from __future__ import annotations
import os
import asyncio
from typing import Dict, List

import streamlit as st
from agents import Runner

from affinity_client import AffinityAPI
from agent_tools import AFFINITY as _GLOBAL_AFFINITY, find_company_ids  # noqa
from agent_tools import add_company, add_note, read_notes, find_list_ids, add_company_to_list, change_field_in_list
from agent_tools import AFFINITY as GLOBAL_AFFINITY  # for explicit set
from agent_setup import build_agent

st.set_page_config(page_title="Affinity Agent", page_icon="🤖")

st.title("🤖 Affinity Agent (OpenAI Agents SDK)")
st.caption("Chat with an agent that can take actions in Affinity on your behalf.")

# --- Secrets / Keys --------------------------------------------------------
openai_key = st.secrets.get("OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
affinity_key = st.secrets.get("AFFINITY_API_KEY", None) or os.getenv("AFFINITY_API_KEY")
openai_model = st.secrets.get("OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
zhipu_key = st.secrets.get("ZHIPUAI_API_KEY", None) or os.getenv("ZHIPUAI_API_KEY")

with st.sidebar:
    st.header("Configuration")
    openai_model = st.text_input("Model (supports LiteLLM syntax)", value=openai_model)
    openai_key = st.text_input("OpenAI API Key (for OpenAI models or tracing)", value=openai_key or "", type="password")
    zhipu_key = st.text_input("ZhipuAI API Key (for GLM via LiteLLM)", value=zhipu_key or "", type="password")
    affinity_key = st.text_input("Affinity API Key", value=affinity_key or "", type="password")
    st.markdown("""
**Tip:** For GLM via LiteLLM, set the model to `litellm/zhipuai/glm-4.5` and provide a ZhipuAI key.
- LiteLLM providers use their own API keys (e.g., ZHIPUAI_API_KEY).
- OpenAI key is optional unless you’re using OpenAI models or enabling trace export.
    """)

using_litellm = (openai_model or "").strip().lower().startswith("litellm/")
# Require Affinity key always; require an appropriate model key based on provider
if not affinity_key:
    st.warning("Add your Affinity API key in the sidebar to begin.")
    st.stop()

if using_litellm and not zhipu_key:
    st.warning("Using LiteLLM model. Add your ZhipuAI API key in the sidebar.")
    st.stop()

if not using_litellm and not openai_key:
    st.warning("Add your OpenAI API key (or switch to a LiteLLM model and provide its key).")
    st.stop()

# Export keys to env for the Agents SDK & our client
os.environ["OPENAI_MODEL"] = openai_model
os.environ["AFFINITY_API_KEY"] = affinity_key

# For LiteLLM providers, set their env key. For ZhipuAI, LiteLLM expects ZHIPUAI_API_KEY.
if using_litellm and zhipu_key:
    os.environ["ZHIPUAI_API_KEY"] = zhipu_key

# OpenAI key can be used for OpenAI models and/or trace export
if openai_key:
    os.environ["OPENAI_API_KEY"] = openai_key


# Bind our Affinity client to the global used by the tools module
GLOBAL_AFFINITY = AffinityAPI(affinity_key)

# Build the agent (uses tools decorated with @function_tool)
agent = build_agent()

# --- Chat State ------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages: List[Dict[str, str]] = []

# Render chat history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

user_input = st.chat_input("Ask me to add a company, add a note, manage lists, etc.")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Build a short rolling context for the agent input (keeps things simple)
    history_text = "\n".join([
        f"{m['role'].capitalize()}: {m['content']}" for m in st.session_state.messages[-6:]
    ])

    # Run the agent synchronously in Streamlit
    async def run_agent(prompt: str):
        return await Runner.run(agent, input=prompt, max_turns=8)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        try:
            result = asyncio.run(run_agent(history_text))
            final = str(result.final_output)
        except Exception as e:
            final = f"❌ Error: {e}"
        placeholder.markdown(final)
        st.session_state.messages.append({"role": "assistant", "content": final})

st.divider()
with st.expander("Quick actions (examples)"):
    st.markdown(
        "- *Find company IDs:* `find_company_ids(query=""Acme"" )`\n"
        "- *Find list IDs:* `find_list_ids(list_name=""Target Accounts"")`\n"
        "- *Add company:* `add_company(name=""Acme Corp"", domain=""acme.com"")`\n"
        "- *Add note:* `add_note(content=""Spoke with buyer"", organization_id=123)`\n"
        "- *Add company to list:* `add_company_to_list(list_id=456, organization_id=123)`\n"
        "- *Change field in list:* `change_field_in_list(list_id=456, organization_id=123, field_name_or_id=""Status"", value=""Prospect"")`\n"
    )

st.caption("Built with Streamlit, Affinity API, and the OpenAI Agents SDK.")
