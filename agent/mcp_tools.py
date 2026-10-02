"""Connects to the weather and document MCP servers, vendored (unchanged)
into mcp_servers/ from the sibling cli_project_working project as part of
Phase 8 — a deployed backend has no access to that sibling project's
folder, so the servers had to live inside this project to be deployable.
finance_news_server.py was left out at first (it needed an
ALPHA_VANTAGE_API_KEY that was never set) and later added back, widened
from health-insurer news to any ticker or topic, and changed to report a
missing key when called rather than crash on startup.

Each server is started with the same Python that runs the backend (not
`uv run`), since every package the servers import is already installed
there — and a host like Render may not have `uv` on its PATH at runtime.

Each server is also handed the backend's full environment. Without that,
the MCP library passes only a few safe system variables (HOME, PATH, ...)
to the subprocess, so a key set in the hosting dashboard — like
ALPHA_VANTAGE_API_KEY — never reaches it. Locally this went unnoticed
because finance_news_server.py also reads the project's .env file, which
doesn't exist on a deployed host.
"""

import os
import sys

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.config import PROJECT_ROOT

MCP_SERVERS_DIR = PROJECT_ROOT / "mcp_servers"


def _server(script: str) -> dict:
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": [script],
        "cwd": str(MCP_SERVERS_DIR),
        "env": dict(os.environ),
    }


def build_mcp_client() -> MultiServerMCPClient:
    connections = {
        "weather": _server("weather_server.py"),
        "finance_news": _server("finance_news_server.py"),
        "documents": _server("mcp_server.py"),
    }
    return MultiServerMCPClient(connections)
