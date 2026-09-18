# LangChain Agent + Vector Knowledge Store — Implementation Plan

## Context

This is a **separate project** from `cli_project_working`, deliberately kept apart so that project stays on its native Anthropic-SDK/MCP architecture while this one is a hands-on vehicle for learning LangChain (industry-standard, provider-agnostic agent framework — see the earlier discussion on why it's a genuinely different skill from Anthropic's own tooling) and vector-database-backed memory/retrieval.

**Goals for this project:**
1. A working LangChain agent, built with current (not deprecated) LangChain/LangGraph patterns.
2. A **document knowledge store**: ingest files, chunk them, embed them, and let the agent retrieve relevant chunks (RAG) instead of hallucinating.
3. **Conversation memory**: the agent can semantically recall things discussed in earlier sessions, not just the current conversation's turns.
4. **Keep the existing MCP servers** (`weather_server.py`, `finance_news_server.py`, `mcp_server.py` from `cli_project_working`) as the agent's tools — connected via LangChain's official MCP integration, not rewritten.
5. Built the way a senior engineer would build it: typed, tested, secrets never committed, graceful degradation when an external service fails, incremental phases each ending in something runnable — not a single big-bang implementation.

Two variants are laid out below for reference — **Variant A (local, Chroma)**, the fast path to a working, learnable system, and **Variant B (deployed, Pinecone)**, full production treatment. **Given a real time crunch, the chosen path is a lean hybrid (below): validate the core agent/RAG/memory logic locally and minimally, then build straight into the deployed (Pinecone) stack — never finishing Variant A as its own separate deliverable.** Rationale: the deployment layer (backend, auth, frontend, CI/CD) has zero equivalent in Variant A regardless of how much of it you build, so there's no time saved finishing A's polish/front-end/test phases before moving on — but validating the LangChain-agent-specific logic (new to you) in a bare script first avoids debugging it simultaneously with auth/network/browser issues later.

## Chosen Path (Lean → Deployed)

| Phase | Goal | Est. time | Check yourself |
|---|---|---|---|
| 0 — Scaffolding | Same as Variant A Phase 0 below, but include `langchain-pinecone` alongside `langchain-chroma` from the start (Chroma used only for this phase's local validation, Pinecone is the real target) | 0.5–1 hr | `python -c "import langchain, langgraph, chromadb"` runs clean |
| 1 — MCP tools + basic agent (validate) | Same as Variant A Phase 1 — prove `langchain-mcp-adapters` + `create_react_agent` work against the real MCP servers | 2–4 hrs | Real, tool-backed weather answer |
| 2 — Document knowledge store (validate, local Chroma) | Same as Variant A Phase 2, kept intentionally minimal — just enough to prove chunk/embed/retrieve works, not full polish | 3–4 hrs | Retrieves the right chunk from one ingested file |
| 3 — Conversation memory (validate, local Chroma) | Same as Variant A Phase 3, minimal | 2–3 hrs | Cross-session recall works once |
| 4 — Port storage to Pinecone | Swap the Chroma-backed calls from Phases 2–3 for Pinecone equivalents (two namespaces); this is genuinely new work, not a copy-paste | 2–4 hrs | Same Phase 2/3 checks pass against Pinecone instead of Chroma |
| 5 — FastAPI backend | Same as Variant B Phase 4 | 4–6 hrs | Streamed, tool-and-retrieval-backed answer via `curl` |
| 6 — Auth + persistence | Same as Variant B Phase 5 (Supabase, isolated from `cli_project_working`'s project) | 4–6 hrs | Two accounts, isolated data |
| 7 — React frontend | Same as Variant B Phase 6 | 6–10 hrs | Full local sign-in-and-chat loop |
| 8 — CI/CD + deploy | Same as Variant B Phase 7 | 4–6 hrs | Public URL works end-to-end |
| 9 — Tests, typing, docs, hardening | Same as Variant B Phase 8 | 4–6 hrs | `pytest` green in CI |

**Total: ~32–50 hours** — this is more than Variant B's standalone 28–43 hours, not less, because Phases 2–3's local-Chroma work gets partly rebuilt in Phase 4. The time this path buys you isn't a shorter total — it's catching agent/RAG/memory design mistakes in a 2-minute script run instead of a multi-service deployed stack.

## Shared Architecture (both variants)

- **LLM integration**: `langchain-anthropic`'s `ChatAnthropic` wraps Claude — this is LangChain's supported Anthropic binding, not a community shim.
- **Tool integration**: `langchain-mcp-adapters` connects to your existing MCP servers the same way `cli_project_working/mcp_client.py` already does (stdio subprocess), then exposes their tools as native LangChain `Tool` objects via `.get_tools()`. **Zero changes needed to the MCP servers themselves.**
- **Agent construction**: LangGraph's prebuilt `create_react_agent(model, tools)` — LangChain's current recommended way to build a tool-calling agent loop (successor to the older, now-deprecated `AgentExecutor`). Using the current pattern matters both for the plan to actually work and for it to reflect current best practice.
- **Two separate vector-store collections/namespaces** (per our earlier discussion on why not to pool them):
  - `document_chunks` — the knowledge store. Chunked file text, embedded, retrieved via a `retriever` tool the agent can call.
  - `conversation_memory` — embedded past conversation turns, tagged with `conversation_id`/`timestamp`, for cross-session recall.
- **Embeddings**: Voyage AI (Anthropic's recommended embeddings partner — Anthropic has no first-party embeddings API). Needs its own free-tier API key.
- **Short-term vs. long-term memory split**: LangGraph's built-in checkpointer handles the *current* session's turn-by-turn state (cheap, no vector search needed); the vector store is only for genuine cross-session recall ("what did we discuss last week"). Don't vector-search within the same session — that's what the checkpointer is for.
- **Engineering practices applied throughout**: type hints checked with `mypy`, `pytest` with fakes/mocks for Claude/MCP/embeddings/vector-store calls (no live external calls in unit tests), structured logging, `.env`-based secrets with a committed `.env.example`, a standalone idempotent re-ingest script (the vector store is a derived index — treat it as disposable/rebuildable, per our earlier discussion), and a README documenting the architecture and setup.

---

## Variant A: Local (Chroma)

Fastest path to a real, working system. Runs entirely on your machine — no cloud accounts beyond Anthropic + Voyage AI API keys.

| Phase | Goal | Est. time | Check yourself |
|---|---|---|---|
| 0 — Scaffolding | `pyproject.toml`/`uv init`, deps (`langchain`, `langchain-anthropic`, `langchain-mcp-adapters`, `langgraph`, `langchain-chroma`, `chromadb`, `langchain-voyageai`, `python-dotenv`, `pytest`, `mypy`, `ruff`), `.env.example`, `.gitignore`, `git init`, README skeleton | 0.5–1 hr | `python -c "import langchain, langgraph, chromadb"` runs clean |
| 1 — MCP tools via LangChain | Point `langchain-mcp-adapters`' `MultiServerMCPClient` at the three existing MCP servers (same stdio spawn pattern as `mcp_client.py`), convert to tools, build a bare `create_react_agent` with no memory/RAG yet | 2–4 hrs | Script asks "what's the weather in Chicago" and gets a real, tool-backed answer |
| 2 — Document knowledge store | Ingestion script: chunk files (`RecursiveCharacterTextSplitter`) from a `knowledge/` folder, embed via Voyage AI, upsert into a persisted Chroma `document_chunks` collection; add a `retriever` tool alongside the MCP tools | 4–6 hrs | Ask a question whose answer only exists in one ingested file — agent retrieves and answers correctly, and doesn't hallucinate when the answer isn't there |
| 3 — Conversation memory | Separate `conversation_memory` Chroma collection; after each turn, embed and store with metadata; before each new turn, retrieve top-k relevant past turns from *other* sessions | 3–5 hrs | Start a fresh session, ask "what did I ask about last time" — correctly recalled by meaning, not exact wording |
| 4 — Front end + resilience | Simple CLI REPL (or minimal Streamlit); wrap external calls (Voyage/Chroma/MCP subprocess) so a failure degrades gracefully instead of crashing | 2–3 hrs | Kill the network mid-conversation — agent reports a clean error instead of an unhandled exception |
| 5 — Tests, typing, docs | `pytest` unit tests (mocked MCP/embeddings/LLM), `mypy`/`ruff` clean, README with architecture + setup | 3–4 hrs | `pytest` green, `mypy .` clean |

**Total: ~15–23 hours** — roughly 3–5 half-day sessions, or 1–2 weeks part-time (evenings/weekends).

---

## Variant B: Deployed (Pinecone + web app)

Same core agent logic as Variant A, with Pinecone from the start instead of Chroma, plus a full deployment layer mirroring the `cli_project_working` web-app plan (FastAPI backend, React frontend, hosted).

| Phase | Goal | Est. time | Check yourself |
|---|---|---|---|
| 0 — Scaffolding + Pinecone | Same deps as Variant A but `langchain-pinecone` instead of `langchain-chroma`; create Pinecone account/free-tier project with two namespaces (`document-chunks`, `conversation-memory`) | 1–2 hrs | Pinecone console shows both namespaces created |
| 1 — MCP tools + basic agent | Same as Variant A Phase 1 | 2–4 hrs | Same check as A |
| 2 — Document knowledge store (Pinecone) | Same ingestion/chunking design as A, upserting to a Pinecone namespace instead of local Chroma | 4–6 hrs | Same check as A |
| 3 — Conversation memory (Pinecone) | Same design as A, targeting the other namespace | 3–5 hrs | Same check as A |
| 4 — FastAPI backend | Mirrors `cli_project_working`'s `server/` pattern: a `lifespan` hook connects MCP clients once at startup, streaming endpoint (SSE), request/response schemas | 4–6 hrs | `curl` a chat request, get a real streamed, tool-and-retrieval-backed answer |
| 5 — Auth + persistence (optional but recommended) | Reuse the Supabase Auth + Postgres pattern from the `cli_project_working` plan (new Supabase project, kept isolated from that one) for accounts + conversation transcripts | 4–6 hrs | Two test accounts only see their own conversations |
| 6 — React frontend | Chat UI as its own small app (kept separate from `cli_project_working`'s frontend so this project is independently deployable/demoable) | 6–10 hrs | Full local loop: sign in, chat, see retrieval/tool events |
| 7 — CI/CD + deploy | GitHub Actions (lint/type/test), Vercel (frontend) + Render/Fly (backend); Pinecone is already cloud-hosted, no separate vector-DB deploy step | 4–6 hrs | Public URL works end-to-end from a phone on cellular data |
| 8 — Tests, typing, docs, hardening | Same as Variant A Phase 5, plus an auth test and a "Pinecone call fails → graceful degradation, not a crash" test | 4–6 hrs | `pytest` green in CI; forced Pinecone failure doesn't crash a request |

**Total: ~28–43 hours** — roughly 1–2 weeks of solid part-time work, more realistically 3–4 weeks at an evenings/weekends pace given the added auth/frontend/deploy surface.

---

## Sequencing Recommendation

**Superseded by the "Chosen Path" section above** — kept here as the reasoning for why Variant A exists at all: its Phases 0–3 are nearly identical in *design* to Variant B's (same agent, same chunking/retrieval logic — only the vector-store backend differs), so validating them locally first is never wasted effort even under time pressure, just not worth polishing into a full separate deliverable when the real target is deployed.
