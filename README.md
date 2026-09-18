# langchain-knowledge-agent

A LangChain + LangGraph agent with a Pinecone-backed document knowledge store
(RAG), cross-session conversation memory, per-user accounts (Supabase Auth +
Postgres), a FastAPI backend, and a React chat frontend — built incrementally,
phase by phase. See [`PLAN.md`](./PLAN.md) for the full architecture and
rationale.

This is a **single-user app by design**: there is no public signup route.
Accounts are created directly in the Supabase dashboard.

## Architecture

- **Agent**: `agent/core.py` — a LangGraph `create_react_agent` with tools for
  weather/documents (MCP, vendored in `mcp_servers/`), document knowledge-base
  search (Pinecone), and live web search (Anthropic's server-side tool).
- **Memory**: `agent/conversation_memory.py` — cross-session recall via
  Pinecone, scoped per-user.
- **Backend**: `server/main.py` — FastAPI, streams responses as
  Server-Sent Events, requires a Supabase login token on `/chat`.
- **Frontend**: `frontend/` — a small Vite + React chat UI.

## Local setup

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY, VOYAGE_API_KEY, PINECONE_API_KEY,
                        # SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
uv sync
uv run python ingest.py   # populate the document knowledge base from knowledge/*.txt
```

Run `supabase/schema.sql` once in your Supabase project's SQL Editor to create
the `conversations` table before starting the server.

**Backend** (Terminal 1):
```bash
uv run uvicorn server.main:app
```

**Frontend** (Terminal 2):
```bash
cd frontend && npm install && npm run dev
```

Then open `http://localhost:5173` and log in with an account created in your
Supabase dashboard (Authentication → Users → Add user).

## Status

Phases 0-7 complete (scaffolding through the React frontend). Currently on
Phase 8 (CI/CD + deploy).
