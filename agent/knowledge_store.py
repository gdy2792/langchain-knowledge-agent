"""The document knowledge store: chunked, embedded text from `knowledge/`,
now living in Pinecone (ported from local Chroma in Phase 4) under the
`document-chunks` namespace of the shared index.
"""

from langchain_pinecone import PineconeVectorStore
from langchain_voyageai import VoyageAIEmbeddings

from agent.config import (
    DOCUMENT_CHUNKS_NAMESPACE,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    VOYAGE_API_KEY,
)
from agent.pinecone_index import ensure_index_exists


def build_document_store() -> PineconeVectorStore:
    """Opens the `document-chunks` namespace of the shared Pinecone index,
    creating the index first if it doesn't exist yet. Safe to call
    repeatedly."""
    ensure_index_exists()
    embeddings = VoyageAIEmbeddings(model="voyage-3.5", voyage_api_key=VOYAGE_API_KEY)
    return PineconeVectorStore(
        index_name=PINECONE_INDEX_NAME,
        embedding=embeddings,
        namespace=DOCUMENT_CHUNKS_NAMESPACE,
        pinecone_api_key=PINECONE_API_KEY,
    )
