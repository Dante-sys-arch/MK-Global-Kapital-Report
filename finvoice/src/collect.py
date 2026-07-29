"""
FinVoice — Materialsammlung ("Hooks").

Liest die themenrelevanten RSS-Feeds des Kunden, filtert auf die letzten
7 Tage, bewertet Treffer nach Keyword-Relevanz und liefert die besten
Aufhänger für die Post-Entwürfe der Woche.
"""
import html as html_module
import re
import time
from datetime import datetime, timedelta

import feedparser

MAX_PER_FEED = 40


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html_module.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _entry_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime.fromtimestamp(time.mktime(parsed))
    return None


def collect_hooks(client: dict, max_items: int = 8, days: int = 7) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days)
    keywords = [k.lower() for k in client.get("keywords", [])]
    topics = [t.lower() for t in client.get("topics", [])]
    seen_links: set[str] = set()
    hooks: list[dict] = []

    for feed_url in client["feeds"]:
        try:
            feed = feedparser.parse(feed_url)
        except Exception as exc:
            print(f"  ⚠ Feed nicht lesbar: {feed_url} ({exc})")
            continue
        for entry in feed.entries[:MAX_PER_FEED]:
            date = _entry_date(entry)
            if date and date < cutoff:
                continue
            link = getattr(entry, "link", "") or ""
            title = _strip_html(getattr(entry, "title", ""))
            if not title or link in seen_links:
                continue
            seen_links.add(link)
            summary = _strip_html(getattr(entry, "summary", ""))[:500]
            haystack = f"{title} {summary}".lower()
            score = sum(2 for k in keywords if k in haystack)
            score += sum(1 for t in topics if t in haystack)
            hooks.append({
                "title": title,
                "link": link,
                "source": feed.feed.get("title", feed_url) if feed.feed else feed_url,
                "date": (date or datetime.now()).strftime("%Y-%m-%d"),
                "summary": summary,
                "score": score,
            })

    hooks.sort(key=lambda h: (h["score"], h["date"]), reverse=True)
    return hooks[:max_items]
