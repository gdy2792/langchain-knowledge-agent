"""The literal, per-user conversation transcript log, in Postgres via
Supabase — separate from agent/conversation_memory.py's Pinecone store.
Pinecone is the AI's own fuzzy, by-meaning recall of a few relevant past
turns; this is the exact, ordered record a human could browse, tagged by
`user_id` so it's never visible to anyone but its owner.
"""

from supabase import Client


def save_transcript_turn(client: Client, user_id: str, role: str, content: str) -> None:
    client.table("conversations").insert(
        {"user_id": user_id, "role": role, "content": content}
    ).execute()


def recent_transcript_turns(client: Client, user_id: str, limit: int = 10) -> list[dict]:
    """The user's most recent turns, newest first — across all of their
    chats, by time rather than by meaning (which is what Pinecone recall is
    for). Always filtered by user_id: the service-role client bypasses Row
    Level Security, so this filter is the only thing keeping users apart."""
    response = (
        client.table("conversations")
        .select("role, content, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data
