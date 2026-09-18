"""Phase 1 gave us a bare MCP-tool-calling agent. Phase 2 added a retriever
tool backed by the local document knowledge store. Phase 3 adds cross-session
conversation memory (agent/conversation_memory.py): every question+answer is
embedded and stored, and relevant past turns are recalled before each new
question — separate from LangGraph's own short-term, same-session memory,
which we don't use here since main.py only ever runs one turn per process."""

import uuid

# main.py has no login flow — it's a debug/validation script, not something
# real users touch — so it tags its memory with this fixed placeholder
# instead of a genuine Supabase user id. It's a plain string, not a UUID,
# since Pinecone metadata doesn't enforce any particular format (unlike the
# Postgres `conversations.user_id` column the server writes to, which does).
LOCAL_CLI_USER_ID = "local-cli-user"

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from agent.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from agent.conversation_memory import (
    build_conversation_memory_store,
    format_memory_context,
    recall_related_turns,
    save_turns,
)
from agent.knowledge_store import build_document_store
from agent.mcp_tools import build_mcp_client
from agent.retriever_tool import build_retriever_tool

# Anthropic's server-side web search — unlike every other tool here, Claude
# runs this one itself (Anthropic's own servers do the actual searching);
# we just declare it, we never execute it. That's why it's a plain dict,
# not a LangChain @tool-decorated function like search_knowledge_base.
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}


async def build_agent():
    """Returns (agent, tools). Exposed separately so tests can build an
    agent from a fake tool list without spawning real MCP subprocesses."""
    mcp_client = build_mcp_client()
    mcp_tools = await mcp_client.get_tools()

    document_store = build_document_store()
    retriever_tool = build_retriever_tool(document_store)

    tools = [*mcp_tools, retriever_tool, WEB_SEARCH_TOOL]
    model = ChatAnthropic(model=CLAUDE_MODEL, api_key=ANTHROPIC_API_KEY)
    agent = create_react_agent(model, tools)
    return agent, tools


async def run_turn(agent, memory_store, user_id: str, query: str):
    """Runs one turn, yielding structured events as they happen. Shared by
    `ask()` below (prints them to a terminal) and the Phase 5 FastAPI server
    (streams them over HTTP as Server-Sent Events) — same logic, two front
    doors, so the two never drift apart from each other."""
    conversation_id = uuid.uuid4().hex

    # Recall happens *before* this session's own turns are saved below, so
    # only genuinely earlier sessions can ever be found here. Wrapped because
    # an embedding-service hiccup (e.g. Voyage's free-tier rate limit) here
    # shouldn't prevent answering the question at all — just skip recall.
    try:
        past_turns = recall_related_turns(memory_store, user_id, query)
    except Exception as exc:
        past_turns = []
        yield {"type": "warning", "message": f"Memory recall unavailable: {exc}"}
    memory_context = format_memory_context(past_turns)
    if memory_context:
        yield {"type": "memory_recalled", "context": memory_context}
    agent_input = f"{memory_context}\n\nCurrent question: {query}" if memory_context else query

    final_text = ""
    async for step in agent.astream(
        {"messages": [("user", agent_input)]},
        stream_mode="updates",
    ):
        for node_output in step.values():
            for message in node_output.get("messages", []):
                if getattr(message, "tool_calls", None):
                    for call in message.tool_calls:
                        yield {"type": "tool_call", "name": call["name"], "args": call["args"]}
                elif message.type == "tool":
                    # .text, not .content: MCP tool results (e.g. weather)
                    # come back as a list of content blocks, not a plain
                    # string — the exact same shape issue already fixed
                    # once below for AI messages. Left as .content, this
                    # serializes to JSON as an array of objects, which
                    # crashes the React frontend when it tries to render
                    # it as text ("Objects are not valid as a React child").
                    yield {"type": "tool_result", "name": message.name, "content": message.text}
                elif message.type == "ai" and message.content:
                    # .text pulls just the text block(s) out of message.content,
                    # which can be a list of blocks (e.g. a "thinking" block
                    # alongside the reply) rather than a plain string.
                    final_text = message.text

    yield {"type": "final_answer", "text": final_text}

    # The answer is already delivered at this point — a failure here should
    # degrade to "this turn won't be recalled later," not crash the request.
    try:
        save_turns(
            memory_store,
            conversation_id,
            user_id,
            [("user", query), ("assistant", final_text)],
        )
    except Exception as exc:
        yield {"type": "warning", "message": f"Failed to save this turn to memory: {exc}"}


async def ask(query: str) -> str:
    """One-shot CLI entry point (used by main.py): builds a fresh agent,
    runs one turn, prints each step as it happens, returns the final text."""
    agent, tools = await build_agent()
    # Server-side tools (e.g. WEB_SEARCH_TOOL) are plain dicts, not
    # LangChain objects, so they carry their name under ["name"] instead
    # of .name.
    tool_names = [t.name if hasattr(t, "name") else t["name"] for t in tools]
    print(f"Connected tools: {tool_names}")
    memory_store = build_conversation_memory_store()

    final_text = ""
    async for event in run_turn(agent, memory_store, LOCAL_CLI_USER_ID, query):
        if event["type"] == "memory_recalled":
            print(f"MEMORY RECALLED:\n{event['context']}")
        elif event["type"] == "tool_call":
            print(f"TOOL CALL: {event['name']}({event['args']})")
        elif event["type"] == "tool_result":
            print(f"TOOL RESULT ({event['name']}): {event['content']}")
        elif event["type"] == "final_answer":
            final_text = event["text"]
        elif event["type"] == "warning":
            print(f"WARNING: {event['message']}")

    return final_text
