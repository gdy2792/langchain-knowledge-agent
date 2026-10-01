"""Connects to the weather and document MCP servers, vendored (unchanged)
into mcp_servers/ from the sibling cli_project_working project as part of
Phase 8 — a deployed backend has no access to that sibling project's
folder, so the servers had to live inside this project to be deployable.
finance_news_server.py was left out at first (it needed an
ALPHA_VANTAGE_API_KEY that was never set) and later added back, widened
from health-insurer news to any ticker or topic, and changed to report a
missing key when called rather than crash on startup.
"""

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.config import PROJECT_ROOT

MCP_SERVERS_DIR = PROJECT_ROOT / "mcp_servers"


def build_mcp_client() -> MultiServerMCPClient:
    connections = {
        "weather": {
            "transport": "stdio",
            "command": "uv",
            "args": ["run", "weather_server.py"],
            "cwd": str(MCP_SERVERS_DIR),
        },
        "finance_news": {
            "transport": "stdio",
            "command": "uv",
            "args": ["run", "finance_news_server.py"],
            "cwd": str(MCP_SERVERS_DIR),
        },
        "documents": {
            "transport": "stdio",
            "command": "uv",
            "args": ["run", "mcp_server.py"],
            "cwd": str(MCP_SERVERS_DIR),
        },
    }
    return MultiServerMCPClient(connections)
