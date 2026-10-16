"""
Loads article pages and extracts main text, date, author and site name.
Also resolves Google News redirect links to the publisher URL.
"""
import json
import re
from urllib.parse import parse_qs, quote, urlparse

import trafilatura

from util import http_get, http_post, iso_date, strip_html

# Publication date sources in order of reliability.
_META_DATE = [
    r'<meta[^>]+(?:property|name)=["\'](?:og:)?article:published_time["\'][^>]*content=["\']([^"\']+)',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:)?article:published_time["\']',
    r'"datePublished"\s*:\s*"([^"]+)"',
    r'<meta[^>]+itemprop=["\']datePublished["\'][^>]*content=["\']([^"\']+)',
    r'<meta[^>]+name=["\'](?:pubdate|publishdate|publish-date|parsely-pub-date|sailthru\.date|dc\.date\.issued|DC\.date\.issued)["\'][^>]*content=["\']([^"\']+)',
    r'<time[^>]+datetime=["\']([^"\']+)',
]
_SITE_NAME = r'<meta[^>]+property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)'
_OG_TITLE = r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)'


def _first(patterns, html):
    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1)
    return ""


def fetch_article(url, timeout=20):
    """Return dict with ok, status, final_url, title, text, author, date, sitename, error."""
    out = {"ok": False, "status": None, "final_url": url, "title": "", "text": "",
           "author": "", "date": "", "sitename": "", "error": ""}
    try:
        resp = http_get(url, timeout=timeout, retries=1)
    except Exception as exc:  # network errors
        out["error"] = f"{type(exc).__name__}"
        return out
    out["status"] = resp.status_code
    out["final_url"] = resp.url or url
    if resp.status_code != 200:
        out["error"] = f"HTTP {resp.status_code}"
        return out
    ctype = resp.headers.get("Content-Type", "")
    if "pdf" in ctype.lower() or url.lower().endswith(".pdf"):
        out.update(_extract_pdf(resp.content))
        return out
    html = resp.text
    try:
        data = trafilatura.extract(html, url=out["final_url"], output_format="json",
                                   with_metadata=True, include_comments=False,
                                   include_tables=True, favor_recall=True)
        meta = json.loads(data) if data else {}
    except Exception as exc:
        meta = {}
        out["error"] = f"extract:{type(exc).__name__}"
    out["text"] = meta.get("text") or ""
    out["title"] = meta.get("title") or strip_html(_first([_OG_TITLE], html))
    out["author"] = meta.get("author") or ""
    out["sitename"] = strip_html(_first([_SITE_NAME], html))
    out["date"] = iso_date(_first(_META_DATE, html)) or iso_date(meta.get("date"))
    # Whole visible page without scripts and menus. Author boxes often sit
    # outside the main text; a hit there is checked by Claude, not trusted blindly.
    out["page_text"] = strip_html(re.sub(r"(?is)<(script|style|nav|noscript|svg)[^>]*>.*?</\1>", " ", html))[:60000]
    out["meta_text"] = " ".join(strip_html(m) for m in re.findall(
        r'<meta[^>]+(?:name|property)=["\'](?:author|description|og:description|twitter:description|keywords|article:author|og:image|twitter:image)["\'][^>]*content=["\']([^"\']+)', html, re.I))
    if not out["text"]:
        out["text"] = out["page_text"][:20000]
        out["fallback_text"] = True
    out["ok"] = True
    return out


def _extract_pdf(content):
    try:
        from io import BytesIO
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:60])
        return {"ok": True, "text": text, "type": "pdf"}
    except Exception as exc:
        return {"ok": False, "error": f"pdf:{type(exc).__name__}"}


# ── Google News link resolution ─────────────────────────────────
# Google News RSS links point to news.google.com/rss/articles/<id>. Since 2024
# the id is opaque; the publisher URL comes from Google's batchexecute endpoint
# after reading a signature from the article page. Same approach as the
# open-source package googlenewsdecoder, without its HTML-parser dependency.

_SG = re.compile(r'data-n-a-sg="([^"]+)"')
_TS = re.compile(r'data-n-a-ts="([^"]+)"')
_CTX = [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
        "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0]


def _gnews_id(url):
    parts = urlparse(url).path.split("/")
    if len(parts) > 1 and parts[-2] in ("articles", "read"):
        return parts[-1]
    return ""


def resolve_google_news(url):
    """Return the publisher URL for a Google News link, or '' if it cannot be resolved."""
    art_id = _gnews_id(url)
    if not art_id:
        return ""
    qs = parse_qs(urlparse(url).query)
    hl = qs.get("hl", ["de"])[0]
    gl = qs.get("gl", ["DE"])[0]
    ceid = qs.get("ceid", ["DE:de"])[0]
    page = f"https://news.google.com/rss/articles/{art_id}?hl={quote(hl)}&gl={quote(gl)}&ceid={quote(ceid)}"
    try:
        resp = http_get(page, timeout=15, retries=1)
        if resp.status_code != 200:
            return ""
        sg, ts = _SG.search(resp.text), _TS.search(resp.text)
        if not (sg and ts):
            return ""
        inner = ["garturlreq", _CTX, art_id, int(ts.group(1)) if ts.group(1).isdigit() else ts.group(1), sg.group(1)]
        envelope = [[["Fbv4je", json.dumps(inner, separators=(",", ":")), None, "1"]]]
        body = "f.req=" + quote(json.dumps(envelope, separators=(",", ":")))
        resp = http_post("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
                         headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        if resp.status_code != 200:
            return ""
        text = resp.text
        if "\n\n" in text:
            text = text.split("\n\n", 1)[1]
        text = text.lstrip()
        if text.startswith(")]}'"):
            text = text.split("\n", 1)[1] if "\n" in text else text[4:]
        rows = json.loads(text)
        for row in rows:
            if isinstance(row, list) and len(row) >= 3 and (row[0] == "wrb.fr" or row[1] == "Fbv4je"):
                payload = json.loads(row[2]) if isinstance(row[2], str) else row[2]
                if isinstance(payload, list) and payload and payload[0] == "garturlres":
                    return payload[1]
    except Exception:
        return ""
    return ""
