from __future__ import annotations
import os
from typing import List
from datetime import datetime

from agents import Agent
from agent_tools import (
    add_company,
    find_company_ids,
    add_note,
    read_notes,
    find_list_ids,
    add_company_to_list,
    change_field_in_list,
    read_list_entry_fields,  # <-- add this import
)


def build_agent() -> Agent:
    """Configure the Affinity Agent with tools and instructions."""
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    today = datetime.now().strftime("%d/%m/%y")

    instructions = (
        f"Today is {today}. "
        "You are an Affinity operations agent. You can add organizations, add/read notes, manage lists, "
        "and change list field values. Use tools when you need to take actions. "
        "As a general rule, the only relevant list you should really be interacting with is the Deal Pipeline list, in which the Status field is the most important field."
        "When the user talks about 'turning down' a company, he means to change the Status field to Turned Down."
        "NEVER Add a company to a list twice in the same workflow. You're only allowed to add one company to a list ONCE."
        "Only perform actions explicitly requested by the user. If a required parameter is missing, ask for it. "
        f"When adding a note, always start that note exactly with (underlined & bold) '[JL] {today}', followed by a newline "
        "where the actual note is taken. The date here should be in exact the following format: DD/MM/YY. "
        "Sometimes the user gives some extra preferences with additions to the header, follow those instructions if the user specifically gives them."
        "That top line should ALWAYS be bolded and underlined using the markdown/HTML."
        "You may include formatting where helpful: bold, italics, and underline. "
        "If you write HTML (<strong>, <em>, <u>)"
        "the note tool will handle converting to an HTML note automatically. You are encouraged to format your notes using this HTML option."
        "Be concise. "
        "These are all the possible values that the Status field can take on: ['Qualification Pool', '1. Qualified', '2a. Senior Interest', '2b. Watch', 'SJS Watchlist ', 'NJM Watchlist', '2a. Interest (old)', '* Hearts and Minds', '3a. Consumer Meeting', '3b. SaaS Meeting', '4. Investment Committee', '5. TS Negotiation', '6. Post TS DD', '7a. Portfolio', '7b. Portfolio HP', '7c. Portfolio Micro-Seed', '8a. Portfolio Follow-on', '8b. Portfolio Decision', '9. Portfolio Exited', '0a. Turned Down', '0b. Missed', '0c. Lost']"
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
            read_list_entry_fields,  # <-- add this
        ],
    )
    return agent
