"""Idempotent ingestion script for the document knowledge store.

Reads every file in `knowledge/`, splits it into overlapping chunks, embeds
them, and (re)writes them into the `document-chunks` namespace of the
Pinecone index. The vector store is a derived index, not a source of
truth — so this script always clears the namespace first and rebuilds it
from scratch, rather than trying to diff what's already there. Re-run it
any time `knowledge/` changes.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone.exceptions import NotFoundException

from agent.config import KNOWLEDGE_DIR
from agent.knowledge_store import build_document_store


def load_documents() -> list[Document]:
    documents = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        documents.append(Document(page_content=text, metadata={"source": path.name}))
    return documents


def main() -> None:
    documents = load_documents()
    if not documents:
        print(f"No .txt files found in {KNOWLEDGE_DIR} — nothing to ingest.")
        return

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(documents)

    store = build_document_store()

    try:
        store.delete(delete_all=True)
    except NotFoundException:
        pass  # namespace doesn't exist yet on a first-ever run — nothing to clear

    store.add_documents(chunks)

    print(f"Ingested {len(documents)} file(s) -> {len(chunks)} chunk(s):")
    for path in sorted({d.metadata["source"] for d in documents}):
        print(f"  - {path}")


if __name__ == "__main__":
    main()
