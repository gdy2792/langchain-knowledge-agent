"""A tool for "what did I ask last time?"-style questions. Pinecone recall
(agent/conversation_memory.py) finds past turns *similar in meaning* to the
current question, which is the wrong tool for "most recent" — this reads
the Supabase transcript log (agent/transcripts.py) in time order instead.

The tool needs to know whose history to read, but that must never be
something Claude chooses (or could be talked into changing) — so user_id
arrives through LangGraph's per-run context, set by our own code in
run_turn, not as a tool argument."""

from dataclasses import dataclass

from langchain.tools import ToolRuntime, tool

from agent.transcripts import recent_transcript_turns
from supabase import Client


@dataclass
class UserContext:
    user_id: str


def build_history_tool(client: Client):
    @tool
    def recent_conversation_history(runtime: ToolRuntime[UserContext], limit: int = 10) -> str:
        """Look up the user's most recent messages and replies, newest first,
        across all of their chats (including earlier ones). Use this when the
        user asks what they asked or said recently, last time, or before —
        questions about recency, not about a topic."""
        limit = max(1, min(limit, 50))
        # Same reasoning as search_knowledge_base: return a string rather
        # than raise, since an exception inside a tool can hang the request.
        try:
            turns = recent_transcript_turns(client, runtime.context.user_id, limit)
        except Exception as exc:
            return f"Conversation history is temporarily unavailable ({exc})."
        if not turns:
            return "No earlier messages found."
        return "\n".join(f"- ({t['created_at']}) {t['role']}: {t['content']}" for t in turns)

    return recent_conversation_history
