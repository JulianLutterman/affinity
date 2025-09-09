from typing import List, Dict, Any, Tuple
from openai import OpenAI
from agent.tools import TOOL_SCHEMAS, dispatch_tool
import json

SYSTEM_PROMPT = (
    "You are an AI agent that operates Affinity via tools."
    " Be concise. If you need an ID (list/company/list-entry/field), try to find it via tools."
    " Always confirm actions you perform and return IDs affected."
    " Prefer v2 endpoints for reads and field updates. Use v1 fallback for creates if available."
)

class Agent:
    def __init__(self, openai_api_key: str, affinity_v2, affinity_v1=None, model: str = "gpt-5"):
        self.client = OpenAI(api_key=openai_api_key)
        self.affinity_v2 = affinity_v2
        self.affinity_v1 = affinity_v1
        self.model = model
        self.system_prompt = SYSTEM_PROMPT

    def run(self, messages: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        tool_events: List[Dict[str, Any]] = []

        # Seed conversation for Chat Completions
        chat_messages: List[Dict[str, Any]] = []
        for m in messages:
            if m["role"] == "system":
                chat_messages.append({"role": "system", "content": m["content"]})
            elif m["role"] == "user":
                chat_messages.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                chat_messages.append({"role": "assistant", "content": m["content"]})

        while True:
            # Ask the model
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=chat_messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
            msg = resp.choices[0].message

            # If the model wants to call tools, append the assistant message WITH tool_calls,
            # then append the tool results, and loop.
            if msg.tool_calls:
                # 1) Append the assistant message (with tool_calls) so that 'tool' responses are valid
                assistant_with_calls = {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,  # "function"
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
                chat_messages.append(assistant_with_calls)

                # 2) Execute each tool and append its 'tool' response
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args_json = tc.function.arguments
                    result = dispatch_tool(name, args_json, v2=self.affinity_v2, v1=self.affinity_v1)
                    tool_events.append({"name": name, "args": args_json, "result": result})

                    # Ensure content is a string
                    content_str = result if isinstance(result, str) else json.dumps(result)

                    chat_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": name,
                        "content": content_str,
                    })

                # 3) Continue loop — model now sees the assistant tool_calls + tool results
                continue

            # Otherwise, return the model's final answer
            final = msg.content or "(no content)"
            return final, tool_events
