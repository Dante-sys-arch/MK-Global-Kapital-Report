"""
Search channels. Each returns candidate dicts:
    {"link", "title", "snippet", "source", "date", "author", "channel", "query"}
Candidates are only leads; every one is verified on the article page later.

Channels:
    rss        configured RSS feeds (title, description, full text, author)
    google     Google Custom Search JSON API (until 31.12.2026)
    gnews      Google News RSS search, editions DE / CH / AT
    bing       Bing News RSS search, markets DE / CH / AT (independent index)
    serper     Google web + news results via serper.dev (optional, needs key)
    serpapi    Google web results via serpapi.com (optional, free plan 250/month)
    site       the outlet's own WordPress search (full archive, incl. bylines)
    sitemap    every new article of the home outlets, read in full
"""
import os
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import quote_plus

import feedparser

from util import (clean_title, extract_domain, http_get, http_post, iso_date,
                  is_blocked_domain, strip_html, today_utc)


class Stats:
    """Collects per-channel numbers and errors for the run report."""

    def __init__(self):
        self.channels = {}

    def ch(self, name):
        return self.channels.setdefault(name, {"requests": 0, "ok": 0, "errors": 0, "candidates": 0, "notes": []})

    def note(self, name, msg, limit=25):
        notes = self.ch(name)["notes"]
        if len(notes) < limit:
            notes.append(msg)


def _cand(link, title, channel, snippet="", source="", dt="", author="", query="", **extra):
    c = {"link": link, "title": clean_title(title), "snippet": strip_html(snippet)[:600],
         "source": source, "date": iso_date(dt), "author": author or "", "channel": channel, "query": query}
    c.update(extra)
    return c


# ── RSS ────────────────────────────────────────────────────────

def _entry_text(entry):
    parts = [entry.get("title", ""), entry.get("summary", ""), entry.get("description", "")]
    for c in entry.get("content", []) or []:
        parts.append(c.get("value", ""))
    authors = [entry.get("author", "")] + [a.get("name", "") for a in entry.get("authors", []) or []]
    return strip_html(" ".join(parts)), " ".join(a for a in authors if a)


def _load_feed(url):
    try:
        resp = http_get(url, timeout=12, retries=1)
    except Exception as exc:
        return None, type(exc).__name__
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    feed = feedparser.parse(resp.content)
    if not feed.entries:
        return None, "keine Einträge"
    return feed, ""


def _discover_feed(url):
    """Find the outlet's current feed via <link rel="alternate"> on its homepage."""
    domain = extract_domain(url)
    try:
        resp = http_get(f"https://www.{domain}/" if domain.count(".") == 1 else f"https://{domain}/", timeout=15, retries=1)
    except Exception:
        return ""
    if resp.status_code != 200:
        return ""
    for m in re.finditer(r"<link[^>]+>", resp.text, re.I):
        tag = m.group(0)
        if re.search(r'type=["\']application/(rss|atom)\+xml', tag, re.I):
            href = re.search(r'href=["\']([^"\']+)', tag)
            if href and "comments" not in href.group(1):
                from urllib.parse import urljoin
                return urljoin(resp.url, href.group(1))
    return ""


def scan_rss(feeds, matcher, stats, own_domains=(), state=None):
    out = []
    alt = state.data.setdefault("feed_alt", {}) if state else {}
    for url in feeds:
        st = stats.ch("rss")
        st["requests"] += 1
        feed, err = _load_feed(alt.get(url, url))
        if feed is None and alt.get(url):
            feed, err = _load_feed(url)
        if feed is None:
            found = _discover_feed(url)
            if found and found != url:
                feed, err2 = _load_feed(found)
                if feed is not None:
                    alt[url] = found
                    stats.note("rss", f"{url}: ersetzt durch {found}", limit=80)
        if feed is None:
            st["errors"] += 1
            stats.note("rss", f"{url}: {err}", limit=80)
            continue
        st["ok"] += 1
        for e in feed.entries:  # all entries, not only the newest 40
            text, author = _entry_text(e)
            if not matcher.mentions_any(text + " " + author):
                continue
            link = e.get("link", "")
            if not link or is_blocked_domain(link, own_domains):
                continue
            dt = e.get("published_parsed") or e.get("updated_parsed")
            out.append(_cand(link, e.get("title", ""), "rss", snippet=matcher.focus(text), source=extract_domain(link),
                             dt=dt, author=author, query=extract_domain(url)))
    stats.ch("rss")["candidates"] += len(out)
    return out


# ── Google Custom Search (ends 01.01.2027) ─────────────────────

CSE_END = date(2027, 1, 1)


class CseBudget:
    def __init__(self, limit):
        self.limit = limit
        self.used = 0
        self.blocked = False
        self.no_access = False

    def available(self):
        return not self.blocked and self.used < self.limit

    def take(self):
        if not self.available():
            return False
        self.used += 1
        return True


def _pagemap_date(item):
    for mt in (item.get("pagemap", {}) or {}).get("metatags", []) or []:
        for key in ("article:published_time", "og:article:published_time", "datepublished", "date", "pubdate"):
            if mt.get(key):
                return mt[key]
    return ""


def google_cse(queries, stats, budget, own_domains=(), date_range=None, recent_days=30, pages=1, first_page=0):
    key, cx = os.environ.get("GOOGLE_API_KEY"), os.environ.get("GOOGLE_CX")
    st = stats.ch("google")
    if not key or not cx:
        stats.note("google", "keine Zugangsdaten")
        return []
    if today_utc() >= CSE_END:
        stats.note("google", "Custom Search API von Google eingestellt (seit 01.01.2027)")
        return []
    out = []
    for q in queries:
        for page in range(first_page, first_page + pages):
            if not budget.take():
                stats.note("google", "Tageskontingent erreicht")
                break
            params = {"key": key, "cx": cx, "q": q, "num": 10, "lr": "lang_de", "start": 1 + 10 * page}
            if date_range:
                params["sort"] = f"date:r:{date_range[0].strftime('%Y%m%d')}:{date_range[1].strftime('%Y%m%d')}"
            else:
                params["dateRestrict"] = f"d{recent_days}"
            st["requests"] += 1
            try:
                resp = http_get("https://www.googleapis.com/customsearch/v1", params=params, timeout=20)
            except Exception as exc:
                st["errors"] += 1
                stats.note("google", f"{q}: {type(exc).__name__}")
                continue
            if resp.status_code in (403, 429):
                st["errors"] += 1
                if "does not have the access" in resp.text:
                    stats.note("google", "Projekt hat keinen Zugang zur Custom Search API (Google nimmt keine Neukunden an)")
                    budget.no_access = True
                else:
                    stats.note("google", f"HTTP {resp.status_code}: {resp.text[:160]}")
                budget.blocked = True
                break
            if resp.status_code != 200:
                st["errors"] += 1
                stats.note("google", f"{q}: HTTP {resp.status_code} {resp.text[:120]}")
                continue
            st["ok"] += 1
            items = resp.json().get("items", []) or []
            for it in items:
                link = it.get("link", "")
                if is_blocked_domain(link, own_domains):
                    continue
                out.append(_cand(link, it.get("title", ""), "google", snippet=it.get("snippet", ""),
                                 source=it.get("displayLink", ""), dt=_pagemap_date(it), query=q))
            if len(items) < 10:
                break
    st["candidates"] += len(out)
    return out


# ── Google News RSS ─────────────────────────────────────────────

GNEWS_EDITIONS = [("de", "DE", "DE:de"), ("de", "CH", "CH:de"), ("de", "AT", "AT:de")]


def gnews_url(query, hl, gl, ceid):
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"


GNEWS_THROTTLE = {"hit": False}  # set once Google answers 429/503; no more requests this run


def google_news(queries, stats, editions=GNEWS_EDITIONS, own_domains=()):
    out, seen = [], set()
    st = stats.ch("gnews")
    streak = 0
    for q in queries:
        for hl, gl, ceid in editions:
            if GNEWS_THROTTLE["hit"]:
                st["candidates"] += len(out)
                return out
            url = gnews_url(q, hl, gl, ceid)
            st["requests"] += 1
            try:
                resp = http_get(url, timeout=20, retries=1)
            except Exception as exc:
                st["errors"] += 1
                stats.note("gnews", f"{q} [{gl}]: {type(exc).__name__}")
                continue
            if resp.status_code in (429, 503):
                streak += 1
                st["errors"] += 1
                if streak >= 2:
                    GNEWS_THROTTLE["hit"] = True
                    stats.note("gnews", f"Google drosselt (HTTP {resp.status_code}), restliche Suchen im nächsten Lauf")
                continue
            if resp.status_code != 200:
                st["errors"] += 1
                stats.note("gnews", f"{q} [{gl}]: HTTP {resp.status_code}")
                continue
            streak = 0
            st["ok"] += 1
            feed = feedparser.parse(resp.content)
            for e in feed.entries:
                src = e.get("source") or {}
                src_href = src.get("href", "") if isinstance(src, dict) else ""
                src_title = src.get("title", "") if isinstance(src, dict) else ""
                title = clean_title(e.get("title", ""), src_title + " " + extract_domain(src_href))
                key = (title.lower(), src_href)
                if key in seen:
                    continue
                seen.add(key)
                domain = extract_domain(src_href)
                if domain and is_blocked_domain("https://" + domain, own_domains):
                    continue
                out.append(_cand("", title, "gnews", snippet=strip_html(e.get("summary", "")),
                                 source=src_title or domain, dt=e.get("published_parsed"),
                                 query=f"{q} [{gl}]", gnews_link=e.get("link", ""), source_domain=domain))
    st["candidates"] += len(out)
    return out


# ── Bing News RSS (second, independent news index) ──────────────

def bing_news(queries, stats, markets=(("de-DE", "DE"), ("de-CH", "CH"), ("de-AT", "AT")), own_domains=()):
    from urllib.parse import parse_qs, urlparse
    out, seen = [], set()
    st = stats.ch("bing")
    for q in queries:
        for mkt, cc in markets:
            url = f"https://www.bing.com/news/search?q={quote_plus(q)}&format=rss&setlang={mkt}&cc={cc}&mkt={mkt}"
            st["requests"] += 1
            try:
                resp = http_get(url, timeout=20, retries=1)
            except Exception as exc:
                st["errors"] += 1
                stats.note("bing", f"{q} [{cc}]: {type(exc).__name__}")
                continue
            feed = feedparser.parse(resp.content) if resp.status_code == 200 else None
            if not feed or (not feed.entries and not feed.feed):
                st["errors"] += 1
                stats.note("bing", f"{q} [{cc}]: HTTP {resp.status_code}")
                continue
            st["ok"] += 1
            for e in feed.entries:
                link = e.get("link", "")
                qs = parse_qs(urlparse(link).query)
                if "url" in qs:
                    link = qs["url"][0]
                if not link or link in seen or is_blocked_domain(link, own_domains):
                    continue
                seen.add(link)
                out.append(_cand(link, e.get("title", ""), "bing", snippet=strip_html(e.get("summary", "")),
                                 source=e.get("news_source", "") or extract_domain(link),
                                 dt=e.get("published_parsed"), query=f"{q} [{cc}]"))
    st["candidates"] += len(out)
    return out


# ── Serper (Google web + news), optional ────────────────────────

def serper(queries, stats, own_domains=(), date_range=None, countries=("de", "ch", "at")):
    key = os.environ.get("SERPER_API_KEY")
    st = stats.ch("serper")
    if not key:
        stats.note("serper", "kein SERPER_API_KEY hinterlegt, Kanal aus")
        return []
    out = []
    tbs = "qdr:m"
    if date_range:
        a, b = date_range
        tbs = f"cdr:1,cd_min:{a.month}/{a.day}/{a.year},cd_max:{b.month}/{b.day}/{b.year}"
    for q in queries:
        for gl in countries:
            for endpoint, key_name in (("search", "organic"), ("news", "news")):
                st["requests"] += 1
                try:
                    resp = http_post(f"https://google.serper.dev/{endpoint}",
                                     json_body={"q": q, "gl": gl, "hl": "de", "num": 20, "tbs": tbs},
                                     headers={"X-API-KEY": key, "Content-Type": "application/json"})
                except Exception as exc:
                    st["errors"] += 1
                    stats.note("serper", f"{q}: {type(exc).__name__}")
                    continue
                if resp.status_code != 200:
                    st["errors"] += 1
                    stats.note("serper", f"{endpoint} {q}: HTTP {resp.status_code} {resp.text[:100]}")
                    if resp.status_code in (401, 402, 403):
                        st["candidates"] += len(out)
                        return out
                    continue
                st["ok"] += 1
                for it in resp.json().get(key_name, []) or []:
                    link = it.get("link", "")
                    if not link or is_blocked_domain(link, own_domains):
                        continue
                    out.append(_cand(link, it.get("title", ""), "serper", snippet=it.get("snippet", ""),
                                     source=it.get("source", "") or extract_domain(link),
                                     dt=it.get("date", ""), query=f"{endpoint}:{q} [{gl}]"))
    st["candidates"] += len(out)
    return out


# ── SerpApi (Google web results, free plan 250 searches/month) ──

def serpapi(queries, stats, budget, own_domains=(), date_range=None):
    key = os.environ.get("SERPAPI_KEY")
    st = stats.ch("serpapi")
    if not key:
        stats.note("serpapi", "kein SERPAPI_KEY hinterlegt, Kanal aus")
        return []
    out = []
    tbs = "qdr:w"
    if date_range:
        a, b = date_range
        tbs = f"cdr:1,cd_min:{a.month}/{a.day}/{a.year},cd_max:{b.month}/{b.day}/{b.year}"
    for q in queries:
        if not budget.take():
            stats.note("serpapi", f"Tagesbudget von {budget.limit} Suchen erreicht")
            break
        st["requests"] += 1
        try:
            resp = http_get("https://serpapi.com/search.json",
                            params={"engine": "google", "q": q, "hl": "de", "gl": "de",
                                    "google_domain": "google.de", "tbs": tbs, "api_key": key}, timeout=40, retries=1)
        except Exception as exc:
            st["errors"] += 1
            stats.note("serpapi", f"{q}: {type(exc).__name__}")
            continue
        if resp.status_code != 200:
            st["errors"] += 1
            stats.note("serpapi", f"{q}: HTTP {resp.status_code} {resp.text[:120]}")
            if resp.status_code in (401, 403, 429):
                budget.blocked = True
                break
            continue
        data = resp.json()
        if data.get("error") and "hasn't returned any results" not in data.get("error", ""):
            st["errors"] += 1
            stats.note("serpapi", f"{q}: {data['error'][:120]}")
            continue
        st["ok"] += 1
        for it in data.get("organic_results", []) or []:
            link = it.get("link", "")
            if not link or is_blocked_domain(link, own_domains):
                continue
            out.append(_cand(link, it.get("title", ""), "serpapi", snippet=it.get("snippet", ""),
                             source=it.get("source", "") or extract_domain(link), dt=it.get("date", ""), query=q))
    st["candidates"] += len(out)
    return out


# ── Outlet's own WordPress search ───────────────────────────────

def site_search(domains, terms, state, stats, matcher, own_domains=()):
    """Full-text search in each home outlet's WordPress archive (/wp-json/wp/v2/posts).

    Returns article bodies, so hits are checked against the names right away and
    only real mentions become candidates. Finds bylines that no search engine shows.
    """
    out = []
    st = stats.ch("site")
    recheck_after = (today_utc() - timedelta(days=14)).isoformat()
    for domain in domains:
        info = state.outlet(domain)
        if info.get("wp") is False and info.get("wp_checked", "") > recheck_after:
            continue
        base = f"https://www.{domain}" if domain.count(".") == 1 else f"https://{domain}"
        domain_ok = False
        for term in terms:
            st["requests"] += 1
            try:
                resp = http_get(f"{base}/wp-json/wp/v2/posts",
                                params={"search": f'"{term}"', "per_page": 50,
                                        "_fields": "link,date,title,excerpt,content"},
                                timeout=30, retries=1, headers={"Accept": "application/json"})
            except Exception as exc:
                st["errors"] += 1
                stats.note("site", f"{domain}: {type(exc).__name__}", limit=80)
                break
            data = None
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    data = None
            if not isinstance(data, list):
                info["wp"] = False
                info["wp_checked"] = today_utc().isoformat()
                stats.note("site", f"{domain}: keine WordPress-Suche (HTTP {resp.status_code})", limit=80)
                break
            domain_ok = True
            for it in data:
                link = it.get("link") or ""
                if not link or is_blocked_domain(link, own_domains):
                    continue
                title = strip_html((it.get("title") or {}).get("rendered", ""))
                body = strip_html((it.get("content") or {}).get("rendered", "") + " " + (it.get("excerpt") or {}).get("rendered", ""))
                if not matcher.mentions_any(title + " " + body):
                    continue
                out.append(_cand(link, title, "site", snippet=matcher.focus(body), source=domain,
                                 dt=it.get("date", ""), query=f"{domain}: {term}"))
        if domain_ok:
            st["ok"] += 1
            info["wp"] = True
            info["wp_checked"] = today_utc().isoformat()
    st["candidates"] += len(out)
    return out


# ── Sitemaps: every new article of the home outlets ─────────────

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
       "news": "http://www.google.com/schemas/sitemap-news/0.9"}


def _xml(url):
    resp = http_get(url, timeout=25, retries=1)
    if resp.status_code != 200 or b"<" not in resp.content[:200]:
        return None
    try:
        return ET.fromstring(resp.content)
    except ET.ParseError:
        return None


def _discover_sitemaps(base, info):
    if info.get("sitemaps"):
        return info["sitemaps"]
    found = []
    try:
        resp = http_get(f"{base}/robots.txt", timeout=15, retries=1)
        if resp.status_code == 200:
            found = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", resp.text)
    except Exception:
        pass
    if not found:
        for path in ("/news-sitemap.xml", "/sitemap-news.xml", "/sitemap_index.xml", "/sitemap.xml", "/wp-sitemap.xml"):
            try:
                if _xml(base + path) is not None:
                    found.append(base + path)
                    break
            except Exception:
                continue
    # News sitemaps first: small and dated.
    found.sort(key=lambda u: 0 if "news" in u.lower() else 1)
    info["sitemaps"] = found[:4]
    return info["sitemaps"]


def _recent_urls(sitemap_url, since, depth=0, budget=None):
    """Collect (url, date) with lastmod/publication date >= since from a sitemap tree."""
    budget = budget if budget is not None else {"files": 12}
    if budget["files"] <= 0:
        return []
    budget["files"] -= 1
    root = _xml(sitemap_url)
    if root is None:
        return []
    tag = root.tag.split("}")[-1]
    out = []
    if tag == "sitemapindex" and depth < 2:
        children = []
        for sm in root.findall("sm:sitemap", _NS):
            loc = (sm.findtext("sm:loc", default="", namespaces=_NS) or "").strip()
            lastmod = iso_date(sm.findtext("sm:lastmod", default="", namespaces=_NS))
            children.append((loc, lastmod))
        dated = [c for c in children if c[1]]
        if dated:
            picks = [c for c in dated if c[1] >= since]
            picks.sort(key=lambda c: c[1], reverse=True)
        else:
            # No dates: news sitemaps first, then the last files (WordPress/Yoast append newest last).
            picks = [c for c in children if "news" in c[0].lower()] or children[-3:]
        for loc, _ in picks[:6]:
            out.extend(_recent_urls(loc, since, depth + 1, budget))
    elif tag == "urlset":
        for u in root.findall("sm:url", _NS):
            loc = (u.findtext("sm:loc", default="", namespaces=_NS) or "").strip()
            pub = iso_date(u.findtext("news:news/news:publication_date", default="", namespaces=_NS))
            lastmod = iso_date(u.findtext("sm:lastmod", default="", namespaces=_NS))
            d = pub or lastmod
            title = u.findtext("news:news/news:title", default="", namespaces=_NS) or ""
            if loc and d and d >= since:
                out.append((loc, d, title))
            elif loc and not d:
                out.append((loc, "", title))  # undated: handled by baseline comparison
    return out


def _h(url):
    import hashlib
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def sitemap_crawl(domains, state, stats, days=3, per_domain_cap=100, skip=None, own_domains=()):
    """New articles of the home outlets.

    Dated sitemaps: URLs published/modified in the last `days` days.
    Undated sitemaps: URLs that were not in the sitemap at the previous run (baseline).
    """
    out = []
    st = stats.ch("sitemap")
    since = (today_utc() - timedelta(days=days)).isoformat()
    for domain in domains:
        info = state.outlet(domain)
        base = f"https://www.{domain}" if domain.count(".") == 1 else f"https://{domain}"
        st["requests"] += 1
        try:
            maps = _discover_sitemaps(base, info)
            urls = []
            for sm in maps:
                urls.extend(_recent_urls(sm, since))
        except Exception as exc:
            st["errors"] += 1
            stats.note("sitemap", f"{domain}: {type(exc).__name__}", limit=80)
            continue
        if not maps:
            st["errors"] += 1
            stats.note("sitemap", f"{domain}: keine Sitemap gefunden", limit=80)
            info.pop("sitemaps", None)
            continue
        dated = [u for u in urls if u[1]]
        undated = [u for u in urls if not u[1]]
        picks = sorted(dated, key=lambda x: x[1], reverse=True)
        if undated:
            known = set(info.get("baseline", []))
            fresh = [u for u in undated if _h(u[0]) not in known]
            if not known:
                stats.note("sitemap", f"{domain}: Ausgangsbestand angelegt ({len(undated)} URLs), ab dem nächsten Lauf werden neue geprüft", limit=80)
                fresh = []
            info["baseline"] = (list(known) + [_h(u[0]) for u in undated if _h(u[0]) not in known])[-30000:]
            picks += fresh
        if not urls:
            stats.note("sitemap", f"{domain}: Sitemap ohne Einträge", limit=80)
            continue
        st["ok"] += 1
        seen, new = set(), []
        for loc, d, title in picks:
            if loc in seen or is_blocked_domain(loc, own_domains):
                continue
            seen.add(loc)
            if skip and skip(loc):
                continue
            new.append(_cand(loc, title, "sitemap", source=domain, dt=d, query=domain, needs_text_match=True))
        if len(new) > per_domain_cap:
            stats.note("sitemap", f"{domain}: {len(new)} neue Artikel, {per_domain_cap} in diesem Lauf geprüft, Rest folgt", limit=80)
            new = new[:per_domain_cap]
        out.extend(new)
    st["candidates"] += len(out)
    return out
