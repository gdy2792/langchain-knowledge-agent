"""Phase 1 gave us a bare MCP-tool-calling agent. Phase 2 added a retriever
tool backed by the local document knowledge store. Phase 3 adds cross-session
conversation memory (agent/conversation_memory.py): every question+answer is
embedded and stored, and relevant past turns are recalled before each new
question. Short-term, same-conversation memory (so a follow-up like "and the
second one?" makes sense) is LangGraph's checkpointer: each chat window gets
a thread id, and the agent sees that thread's whole back-and-forth."""

import asyncio
import uuid

# main.py has no login flow — it's a debug/validation script, not something
# real users touch — so it tags its memory with this fixed placeholder
# instead of a genuine Supabase user id. It's a plain string, not a UUID,
# since Pinecone metadata doesn't enforce any particular format (unlike the
# Postgres `conversations.user_id` column the server writes to, which does).
LOCAL_CLI_USER_ID = "local-cli-user"

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import InMemorySaver

from agent.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from agent.conversation_memory import (
    build_conversation_memory_store,
    format_memory_context,
    recall_related_turns,
    save_turns,
)
from agent.history_tool import UserContext, build_history_tool
from agent.knowledge_store import build_document_store
from agent.mcp_tools import build_mcp_client
from agent.retriever_tool import build_retriever_tool
from agent.supabase_clients import build_service_client

# Anthropic's server-side web search — unlike every other tool here, Claude
# runs this one itself (Anthropic's own servers do the actual searching);
# we just declare it, we never execute it. That's why it's a plain dict,
# not a LangChain @tool-decorated function like search_knowledge_base.
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}

# Seconds to wait before each retry of a failed long-term-memory save.
# Voyage's free tier allows 3 requests/minute, so a rate-limited save
# usually succeeds once the minute rolls over.
SAVE_RETRY_DELAYS = (25, 60)

# Saves still in progress (or waiting to retry). Held here so Python
# doesn't garbage-collect a background task before it finishes, and so the
# CLI can wait for them before exiting.
_pending_saves: set[asyncio.Task] = set()


async def build_agent():
    """Returns (agent, tools). Exposed separately so tests can build an
    agent from a fake tool list without spawning real MCP subprocesses."""
    mcp_client = build_mcp_client()
    mcp_tools = await mcp_client.get_tools()

    document_store = build_document_store()
    retriever_tool = build_retriever_tool(document_store)

    history_tool = build_history_tool(build_service_client())

    tools = [*mcp_tools, retriever_tool, history_tool, WEB_SEARCH_TOOL]
    model = ChatAnthropic(model=CLAUDE_MODEL, api_key=ANTHROPIC_API_KEY)
    # In-memory, so conversations are forgotten when the server restarts —
    # the same lifetime as the chat window itself, whose log is gone after a
    # page refresh anyway. Swapping in a Postgres checkpointer (Supabase)
    # would make them survive restarts.
    agent = create_agent(
        model, tools, checkpointer=InMemorySaver(), context_schema=UserContext
    )
    return agent, tools


async def run_turn(agent, memory_store, user_id: str, query: str, thread_id: str | None = None):
    """Runs one turn, yielding structured events as they happen. Shared by
    `ask()` below (prints them to a terminal) and the Phase 5 FastAPI server
    (streams them over HTTP as Server-Sent Events) — same logic, two front
    doors, so the two never drift apart from each other.

    Turns sharing a `thread_id` are one conversation: the agent sees all of
    that thread's earlier messages. No thread_id means a fresh conversation."""
    conversation_id = thread_id or uuid.uuid4().hex
    # Prefixed with user_id so one user can never continue another user's
    # conversation, even by sending that conversation's thread id.
    config = {"configurable": {"thread_id": f"{user_id}:{conversation_id}"}}

    # Recall skips this conversation's own turns — the checkpointer already
    # gives the agent those, in full and in order. Wrapped because an
    # embedding-service hiccup (e.g. Voyage's free-tier rate limit) here
    # shouldn't prevent answering the question at all — just skip recall.
    try:
        past_turns = recall_related_turns(memory_store, user_id, query, exclude_conversation_id=conversation_id)
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
        config,
        context=UserContext(user_id=user_id),
        stream_mode="updates",
    ):
        for node_output in step.values():
            # Some steps report no changes at all (None) rather than an
            # empty dict.
            for message in (node_output or {}).get("messages", []):
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

    # The answer is already delivered, so the save runs in the background
    # (with retries) instead of holding the reply open while it waits out a
    # rate limit.
    task = asyncio.create_task(
        _save_turns_with_retry(
            memory_store, conversation_id, user_id, [("user", query), ("assistant", final_text)]
        )
    )
    _pending_saves.add(task)
    task.add_done_callback(_pending_saves.discard)


async def _save_turns_with_retry(memory_store, conversation_id, user_id, turns) -> None:
    """A failure here only means "this turn won't be recalled later," so it's
    logged to the server console rather than shown in the chat, which has
    already finished by the time a retry happens."""
    for attempt, delay in enumerate((0, *SAVE_RETRY_DELAYS), start=1):
        await asyncio.sleep(delay)
        try:
            # save_turns makes blocking network calls — run it on a worker
            # thread so it doesn't stall every other request while it waits.
            await asyncio.to_thread(save_turns, memory_store, conversation_id, user_id, turns)
            if attempt > 1:
                print(f"Memory save succeeded on attempt {attempt}.")
            return
        except Exception as exc:
            print(f"Memory save attempt {attempt} failed: {str(exc)[:150]}")
    print("Memory save gave up — this turn won't be recalled in later chats.")


async def wait_for_pending_saves() -> None:
    """Lets a short-lived process (the CLI) finish its background saves
    before exiting, instead of cancelling them."""
    if _pending_saves:
        await asyncio.gather(*_pending_saves)


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

    await wait_for_pending_saves()
    return final_text
