"""
Web tools — search, fetch pages, and global news briefings.
Ported from FRIDAY; rebranded and routed through the permission guard.
"""

import asyncio
import re
import xml.etree.ElementTree as ET

import httpx

SEED_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
]

FINANCE_SEED_FEEDS = [
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
]


async def fetch_and_parse_feed(client, url):
    """Fetch one RSS feed and return up to 5 parsed items (empty on failure)."""
    try:
        response = await client.get(url, headers={"User-Agent": "REMY-AI/1.0"},
                                    timeout=5.0)
        if response.status_code != 200:
            return []
        root = ET.fromstring(response.content)
        source_name = url.split(".")[1].upper()
        feed_items = []
        for item in root.findall(".//item")[:5]:
            title = item.findtext("title")
            description = item.findtext("description")
            link = item.findtext("link")
            if description:
                description = re.sub("<[^<]+?>", "", description).strip()
            feed_items.append({
                "source": source_name,
                "title": title,
                "summary": (description[:200] + "...") if description else "",
                "link": link,
            })
        return feed_items
    except Exception:
        return []


async def _gather_feeds(feeds: list[str]) -> list[dict]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        results = await asyncio.gather(*(fetch_and_parse_feed(client, u) for u in feeds))
    return [item for sublist in results for item in sublist]


def _format_briefing(title: str, articles: list[dict]) -> str:
    report = [f"### {title}\n"]
    for entry in articles[:12]:
        report.append(f"**[{entry['source']}]** {entry['title']}")
        report.append(entry["summary"])
        report.append(f"Link: {entry['link']}\n")
    return "\n".join(report)


def register(mcp, guard):

    @mcp.tool()
    async def get_world_news() -> str:
        """Fetch the latest global headlines from major news outlets."""
        async def impl() -> str:
            articles = await _gather_feeds(SEED_FEEDS)
            if not articles:
                return "The global news grid is unresponsive; unable to pull headlines."
            return _format_briefing("GLOBAL NEWS BRIEFING (LIVE)", articles)
        return await guard(impl, "get_world_news")()

    @mcp.tool()
    async def get_world_finance_news() -> str:
        """Fetch the latest finance and market headlines from major outlets."""
        async def impl() -> str:
            articles = await _gather_feeds(FINANCE_SEED_FEEDS)
            if not articles:
                return "The financial feeds are unresponsive; can't pull market headlines."
            return _format_briefing("FINANCE BRIEFING (LIVE)", articles)
        return await guard(impl, "get_world_finance_news")()

    @mcp.tool()
    async def search_web(query: str) -> str:
        """Search the web via DuckDuckGo's instant-answer API."""
        async def impl(query: str) -> str:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                r = await client.get("https://api.duckduckgo.com/",
                                     params={"q": query, "format": "json",
                                             "no_html": 1, "skip_disambig": 1})
                data = r.json()
            parts = []
            if data.get("AbstractText"):
                parts.append(data["AbstractText"])
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and topic.get("Text"):
                    parts.append(f"- {topic['Text']}")
            return "\n".join(parts) if parts else f"No instant results for: {query}"
        return await guard(impl, "search_web")(query)

    @mcp.tool()
    async def fetch_url(url: str) -> str:
        """Fetch the raw text content of a URL (truncated to 4000 chars)."""
        async def impl(url: str) -> str:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text[:4000]
        return await guard(impl, "fetch_url")(url)

    @mcp.tool()
    async def open_world_monitor() -> str:
        """Open the World Monitor dashboard (worldmonitor.app) in the browser."""
        async def impl() -> str:
            import webbrowser
            try:
                webbrowser.open("https://worldmonitor.app/")
                return "Displaying the World Monitor on your primary screen now."
            except Exception as e:
                return f"Unable to initialize the visual monitor: {e}"
        return await guard(impl, "open_world_monitor")()

    @mcp.tool()
    async def open_finance_world_monitor() -> str:
        """Open the Finance World Monitor (finance.worldmonitor.app) in the browser."""
        async def impl() -> str:
            import webbrowser
            try:
                webbrowser.open("https://finance.worldmonitor.app/")
                return "Displaying the Finance World Monitor now."
            except Exception as e:
                return f"Unable to initialize the finance monitor: {e}"
        return await guard(impl, "open_finance_world_monitor")()
