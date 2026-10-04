"""Prints the raw HTTP requests/responses LangChain sends to Anthropic.

Builds a mini agent the same way agent/core.py does (ChatAnthropic +
create_agent), with one fake local tool, so you can see the agent loop:
call 1 -> Claude asks to use a tool, call 2 -> we send back the tool result.
The API key header is redacted before printing.

Run from the project root:  .venv/bin/python show_anthropic_calls.py"""

import json

import httpx2

_original_send = httpx2.Client.send


def _logging_send(self, request, **kwargs):
    if "anthropic.com" in str(request.url):
        print("\n" + "=" * 70)
        print(f">>> REQUEST: {request.method} {request.url}")
        for name in ("x-api-key", "anthropic-version", "content-type"):
            value = request.headers.get(name)
            if value:
                print(f"    {name}: {'sk-ant-...(hidden)' if name == 'x-api-key' else value}")
        print(json.dumps(json.loads(request.content), indent=2))
    response = _original_send(self, request, **kwargs)
    if "anthropic.com" in str(request.url):
        response.read()
        print(f"\n<<< RESPONSE: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    return response


httpx2.Client.send = _logging_send

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

from agent.config import ANTHROPIC_API_KEY, CLAUDE_MODEL


@tool
def search_knowledge_base(query: str) -> str:
    """Search the project's knowledge base for facts."""
    return "The project mascot is a heron named Pip."


model = ChatAnthropic(model=CLAUDE_MODEL, api_key=ANTHROPIC_API_KEY, max_tokens=300)
agent = create_agent(model, [search_knowledge_base])
result = agent.invoke({"messages": [("user", "Use the knowledge base: what is the project mascot?")]})
print("\n" + "=" * 70)
print("FINAL ANSWER:", result["messages"][-1].text)
