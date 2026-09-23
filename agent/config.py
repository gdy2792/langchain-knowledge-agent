"""Central config: resolves paths and secrets once, so every other module
just imports values instead of re-reading the environment."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _resolve_cli_project_dir() -> Path | None:
    """The sibling project only exists on the original dev machine, never
    in a deployed environment (Phase 8) — so this is optional, not
    required. It's kept only as a local-dev convenience (see below), since
    Phase 8 vendored copies of the actual MCP servers into mcp_servers/."""
    raw = os.getenv("CLI_PROJECT_DIR", "../cli_project_working")
    path = Path(raw)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path if path.exists() else None


CLI_PROJECT_DIR = _resolve_cli_project_dir()

# Reuse the Anthropic key from the sibling project during local development
# if this project's own .env doesn't set it yet, so the same secret doesn't
# have to be duplicated in two places. `override=False` means this
# project's own .env always wins. Skipped entirely when CLI_PROJECT_DIR
# isn't present (e.g. in a deployed environment), where ANTHROPIC_API_KEY
# must just be set directly instead.
if CLI_PROJECT_DIR is not None:
    load_dotenv(CLI_PROJECT_DIR / ".env", override=False)

# Stripped of surrounding whitespace and quotes: python-dotenv removes quotes
# from a local .env value automatically, but a hosting dashboard like
# Render's stores exactly what was pasted — so a key copied from a .env
# line (`"sk-ant-..."`) arrives with literal quotes and Anthropic rejects it
# as invalid (Phase 8's "API key is invalid" on Render, despite a new key).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip().strip("\"'").strip()
if not ANTHROPIC_API_KEY:
    fallback_hint = f" or in {CLI_PROJECT_DIR}/.env" if CLI_PROJECT_DIR else ""
    raise RuntimeError(
        f"ANTHROPIC_API_KEY is not set in this project's .env{fallback_hint}. "
        "Copy .env.example to .env and fill it in."
    )

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
if not VOYAGE_API_KEY:
    raise RuntimeError(
        "VOYAGE_API_KEY is not set. Copy .env.example to .env and fill it in "
        "(free-tier key: https://www.voyageai.com/)."
    )

KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
if not PINECONE_API_KEY:
    raise RuntimeError(
        "PINECONE_API_KEY is not set. Copy .env.example to .env and fill it "
        "in (free tier: https://www.pinecone.io/)."
    )

# One shared index, split by namespace — Pinecone's equivalent of Chroma's
# separate collections from Phases 2-3. voyage-3.5's embeddings are
# 1024-dimensional (confirmed with a real embed_query call, not assumed),
# which the index's dimension must match exactly.
PINECONE_INDEX_NAME = "langchain-knowledge-agent"
EMBEDDING_DIMENSION = 1024
DOCUMENT_CHUNKS_NAMESPACE = "document-chunks"
CONVERSATION_MEMORY_NAMESPACE = "conversation-memory"

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
for _name, _value in [
    ("SUPABASE_URL", SUPABASE_URL),
    ("SUPABASE_ANON_KEY", SUPABASE_ANON_KEY),
    ("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_SERVICE_ROLE_KEY),
]:
    if not _value:
        raise RuntimeError(
            f"{_name} is not set. Copy .env.example to .env and fill it in "
            "(create a free project at https://www.supabase.com/)."
        )

# The deployed frontend's URL (Phase 8, Vercel) — CORS needs to explicitly
# allow it, and it isn't known until after that deploy exists, so it's a
# plain optional env var rather than something set in code ahead of time.
# localhost:5173 (Vite's dev server) is always allowed, regardless, for
# local development.
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
