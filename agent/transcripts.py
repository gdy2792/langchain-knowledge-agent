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
