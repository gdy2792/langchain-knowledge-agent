"""Finance news via Alpha Vantage's NEWS_SENTIMENT feed, which aggregates
articles from many outlets and scores each one's sentiment.

Adapted from cli_project_working/finance_news_server.py, which covered only
health insurers and refused to start without a key. A server that crashes
on startup takes the whole agent down with it (the MCP client loads every
server's tools together), so a missing key is reported when the tool is
*called* instead.
"""

import os

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import Field

load_dotenv()

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip().strip("\"'")

mcp = FastMCP("FinanceNewsMCP", log_level="ERROR")

# Major publicly traded health insurers, for "industry news" questions.
HEALTHCARE_INSURANCE_TICKERS = "UNH,CVS,ELV,CI,HUM,CNC,MOH"


@mcp.tool(
    name="get_finance_news",
    description=(
        "Get recent financial news headlines, summaries and sentiment from "
        "Alpha Vantage. Filter by stock tickers (e.g. 'ELV' for Elevance "
        "Health, 'UNH,CVS' for several) and/or topics. For health insurance "
        f"industry news use tickers '{HEALTHCARE_INSURANCE_TICKERS}'. "
        "With no tickers or topics, returns general market news."
    ),
)
def get_finance_news(
    tickers: str = Field(
        default="",
        description="Comma-separated stock tickers, e.g. 'ELV' or 'UNH,CVS'. Empty for any company.",
    ),
    topics: str = Field(
        default="",
        description=(
            "Comma-separated Alpha Vantage topics: earnings, ipo, "
            "mergers_and_acquisitions, financial_markets, economy_fiscal, "
            "economy_monetary, economy_macro, energy_transportation, finance, "
            "life_sciences, manufacturing, real_estate, retail_wholesale, "
            "technology, blockchain. Empty for all topics."
        ),
    ),
    limit: int = Field(default=10, description="Max number of articles to return (1-50)"),
) -> str:
    if not ALPHA_VANTAGE_API_KEY:
        return (
            "Finance news is not configured: ALPHA_VANTAGE_API_KEY is not set. "
            "Tell the user an administrator needs to add a free key from "
            "https://www.alphavantage.co/support/#api-key."
        )

    limit = max(1, min(limit, 50))
    params = {"function": "NEWS_SENTIMENT", "sort": "LATEST", "limit": 50, "apikey": ALPHA_VANTAGE_API_KEY}
    if tickers:
        params["tickers"] = tickers.replace(" ", "").upper()
    if topics:
        params["topics"] = topics.replace(" ", "").lower()

    try:
        response = httpx.get("https://www.alphavantage.co/query", params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return f"Finance news is temporarily unavailable ({exc})."

    # Alpha Vantage reports rate limits and bad input as a normal 200
    # response with one of these keys instead of a feed.
    problem = data.get("Information") or data.get("Note") or data.get("Error Message")
    if problem:
        return f"Alpha Vantage couldn't answer (often the free 25-requests/day limit): {problem}"

    articles = data.get("feed", [])
    if not articles:
        return f"No recent news found (tickers: {tickers or 'any'}, topics: {topics or 'any'})."

    wanted = set(params.get("tickers", "").split(",")) - {""}
    lines = [f"Recent finance news (tickers: {tickers or 'any'}, topics: {topics or 'any'}):"]
    for article in articles[:limit]:
        per_ticker = ", ".join(
            f"{t['ticker']}: {t['ticker_sentiment_label']}"
            for t in article.get("ticker_sentiment", [])
            if t["ticker"] in wanted
        )
        published = article.get("time_published", "")
        date = f"{published[:4]}-{published[4:6]}-{published[6:8]}" if len(published) >= 8 else "unknown date"
        lines.append(
            f"\n- {article.get('title', 'Untitled')} ({article.get('source', 'unknown source')}, {date})\n"
            f"  Overall sentiment: {article.get('overall_sentiment_label', 'n/a')}"
            + (f" | Per-ticker: {per_ticker}" if per_ticker else "")
            + f"\n  {article.get('summary', '')}\n  {article.get('url', '')}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
