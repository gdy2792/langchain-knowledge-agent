"""Wraps the document knowledge store as a tool the agent can call — same
`Tool` shape the MCP tools have, so the agent doesn't treat retrieval any
differently from calling the weather server."""

from langchain.tools import tool
from langchain_pinecone import PineconeVectorStore


def build_retriever_tool(store: PineconeVectorStore):
    @tool
    def search_knowledge_base(query: str) -> str:
        """Search the internal document knowledge base for facts relevant
        to the query. Use this for questions about internal project details,
        notes, or facts that wouldn't be public knowledge."""
        # Unlike agent/core.py's own recall/save steps, a failure in here
        # happens *inside* LangGraph's tool-execution node, not in our own
        # code around agent.astream() — an uncaught exception here doesn't
        # cleanly propagate as a normal Python error, it was observed to
        # hang the whole request instead. Returning a plain string (what a
        # tool is expected to produce either way) sidesteps that entirely.
        try:
            results = store.similarity_search(query, k=3)
        except Exception as exc:
            return f"Knowledge base search is temporarily unavailable ({exc}). Answer without it, or ask the user to try again shortly."
        if not results:
            return "No relevant documents found."
        return "\n\n".join(
            f"[source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
            for doc in results
        )

    return search_knowledge_base
