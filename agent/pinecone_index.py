"""Ensures the one shared Pinecone index exists. The document knowledge
store and conversation memory store both live in this index, kept apart by
namespace rather than by separate indexes — free-tier accounts are capped
on index count, and a namespace gives the same isolation Chroma's separate
collections did in Phases 2-3."""

from pinecone import Pinecone, ServerlessSpec

from agent.config import EMBEDDING_DIMENSION, PINECONE_API_KEY, PINECONE_INDEX_NAME


def ensure_index_exists() -> None:
    pc = Pinecone(api_key=PINECONE_API_KEY)
    if not pc.has_index(PINECONE_INDEX_NAME):
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
