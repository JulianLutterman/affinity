from __future__ import annotations
import os
from typing import List

from agents import Agent

from agent_tools import (
    add_company,
    find_company_ids,
    add_note,
    read_notes,
    find_list_ids,
    add_company_to_list,
    change_field_in_list,
)


def build_agent() -> Agent:
    """Configure the Affinity Agent with tools and instructions."""
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    instructions = (
        "You are an Affinity operations agent. You can add organizations, add/read notes, manage lists, "
        "and change list field values. Use tools when you need to take actions. "
        "Only perform actions explicitly requested by the user. If a required parameter is missing, ask for it. "
        "Be concise."
    )

    agent = Agent(
        name="Affinity Agent",
        model=model,
        instructions=instructions,
        tools=[
            add_company,
            find_company_ids,
            add_note,
            read_notes,
            find_list_ids,
            add_company_to_list,
            change_field_in_list,
        ],
    )
    return agent
