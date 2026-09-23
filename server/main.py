"""Phase 5 built the streaming server. Phase 6 adds accounts (Supabase Auth)
and a per-user, human-browsable transcript log (Postgres via Supabase) —
distinct from agent/conversation_memory.py's Pinecone store, which is the
AI's own fuzzy, by-meaning recall, not something a person reads directly.

The agent, Pinecone memory store, and both Supabase clients are all built
once in `lifespan` and reused across every request, same reasoning as
Phase 5: rebuilding any of this per-request would be needlessly slow.
"""

import json
import traceback
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.config import ANTHROPIC_API_KEY, FRONTEND_URL
from agent.conversation_memory import build_conversation_memory_store
from agent.core import build_agent, run_turn
from agent.supabase_clients import build_auth_client, build_service_client
from agent.transcripts import save_transcript_turn
from supabase import AuthApiError


class ChatRequest(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: str
    password: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # A safe fingerprint of the key actually in use — never the key itself —
    # so a deployed "API key is invalid" can be checked against the key list
    # at console.anthropic.com, which shows keys as "sk-ant-api03-...XXXX".
    print(
        f"Startup: ANTHROPIC_API_KEY {ANTHROPIC_API_KEY[:13]}...{ANTHROPIC_API_KEY[-4:]} "
        f"({len(ANTHROPIC_API_KEY)} chars)"
    )
    agent, tools = await build_agent()
    print(f"Startup: connected tools: {[t['name'] if isinstance(t, dict) else t.name for t in tools]}")
    app.state.agent = agent
    app.state.memory_store = build_conversation_memory_store()
    app.state.auth_client = build_auth_client()
    app.state.service_client = build_service_client()
    yield


app = FastAPI(lifespan=lifespan)

# The frontend runs on a different origin than this API — locally that's
# Vite's dev server (localhost:5173), and in production it's the deployed
# Vercel URL (FRONTEND_URL) — browsers block cross-origin requests by
# default unless the server explicitly allows the calling origin.
allowed_origins = ["http://localhost:5173"]
if FRONTEND_URL:
    allowed_origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    # The Vercel frontend (a public site) calls this backend at 127.0.0.1 (a
    # private/loopback address) — Chrome's Private Network Access policy
    # blocks that with "Disallowed CORS private-network" on the preflight
    # unless the server opts in explicitly with this header.
    allow_private_network=True,
)


# No /auth/signup route on purpose — this app is single-user (or
# invite-only, if that changes later). Accounts can still be created
# directly in the Supabase dashboard (Authentication → Users → Add user),
# just never through this website itself.
@app.post("/auth/login")
async def login(request: LoginRequest):
    try:
        result = app.state.auth_client.auth.sign_in_with_password(
            {"email": request.email, "password": request.password}
        )
    except AuthApiError as exc:
        # Untested until Phase 8's deployment testing turned up a live 500
        # here: a wrong email/password previously fell through as an
        # unhandled exception (a generic 500) instead of a normal 401.
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"access_token": result.session.access_token, "user_id": result.user.id}


def get_current_user_id(authorization: str = Header(...)) -> str:
    """A FastAPI dependency: every /chat request must prove who it's from.
    Verified against Supabase itself (auth.get_user), not decoded locally —
    so a forged or expired token is rejected the same way Supabase would
    reject it directly."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        user_response = app.state.auth_client.auth.get_user(token)
    except AuthApiError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_response.user.id


@app.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)) -> StreamingResponse:
    async def event_stream():
        final_text = ""
        try:
            async for event in run_turn(app.state.agent, app.state.memory_store, user_id, request.message):
                if event["type"] == "final_answer":
                    final_text = event["text"]
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            # By the time this runs the 200 status has already been sent, so
            # an uncaught error here just cuts the stream off silently — the
            # browser sees an empty reply and the user sees nothing at all
            # (how Phase 8's invalid Render API key first showed up). Send
            # the error as a normal event instead so the chat can display it.
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'warning', 'message': f'Agent error: {exc}'})}\n\n"
            return

        # Same graceful-degradation reasoning as run_turn's own memory save:
        # the answer already streamed above, so a Postgres hiccup here
        # should be reported, not allowed to crash the request.
        try:
            save_transcript_turn(app.state.service_client, user_id, "user", request.message)
            save_transcript_turn(app.state.service_client, user_id, "assistant", final_text)
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'warning', 'message': f'Failed to save transcript: {exc}'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
