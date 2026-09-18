"""Cross-session conversation memory: a separate Pinecone namespace (ported
from a separate local Chroma collection in Phase 4) from the document
knowledge store (agent/knowledge_store.py), so a document search never
accidentally returns a snippet of a past conversation.

Every turn is also tagged with `user_id` (Phase 6), and recall always
filters by it — without that filter, one user's question could surface
another user's private conversation history, since Pinecone otherwise
searches across everyone's turns by meaning alone.

Short-term memory (the current session's own turn-by-turn back-and-forth)
belongs to LangGraph's checkpointer, not this module — this is only for
recalling *other* sessions' conversations by meaning.
"""

import uuid
from datetime import UTC, datetime

from langchain_core.documents import Document
from langchain_pinecone import PineconeVectorStore
from langchain_voyageai import VoyageAIEmbeddings

from agent.config import (
    CONVERSATION_MEMORY_NAMESPACE,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    VOYAGE_API_KEY,
)
from agent.pinecone_index import ensure_index_exists


def build_conversation_memory_store() -> PineconeVectorStore:
    ensure_index_exists()
    embeddings = VoyageAIEmbeddings(model="voyage-3.5", voyage_api_key=VOYAGE_API_KEY)
    return PineconeVectorStore(
        index_name=PINECONE_INDEX_NAME,
        embedding=embeddings,
        namespace=CONVERSATION_MEMORY_NAMESPACE,
        pinecone_api_key=PINECONE_API_KEY,
    )


def save_turns(
    store: PineconeVectorStore,
    conversation_id: str,
    user_id: str,
    turns: list[tuple[str, str]],
) -> None:
    """Saves multiple turns (role, text) in a single embedding call rather
    than one call per turn — Voyage's free tier is rate-limited per
    *request*, not per text embedded, and Voyage supports embedding several
    texts in one call, so batching the user+assistant turns together here
    cuts our call count instead of just working around the limit."""
    now = datetime.now(UTC).isoformat()
    documents = [
        Document(
            page_content=text,
            metadata={
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": role,
                "timestamp": now,
            },
        )
        for role, text in turns
    ]
    store.add_documents(documents, ids=[uuid.uuid4().hex for _ in documents])


def recall_related_turns(
    store: PineconeVectorStore, user_id: str, query: str, k: int = 4
) -> list[Document]:
    """Finds past turns related to `query` by meaning, scoped to this user's
    own turns only — never another user's, regardless of how relevant."""
    return store.similarity_search(query, k=k, filter={"user_id": user_id})


def format_memory_context(turns: list[Document]) -> str:
    if not turns:
        return ""
    lines = [
        f"- ({doc.metadata.get('timestamp', 'unknown time')}) "
        f"{doc.metadata.get('role', 'unknown')}: {doc.page_content}"
        for doc in turns
    ]
    return (
        "Relevant excerpts from earlier conversations (use only if relevant "
        "to the current question; ignore otherwise):\n" + "\n".join(lines)
    )
