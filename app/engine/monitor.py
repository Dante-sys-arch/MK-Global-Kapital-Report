"""
Monitoring-Pipeline pro Kunde:
RSS-Feeds + Google Custom Search -> Dedup -> Claude-Validierung -> Speichern.

Generalisierte Fassung des MK-Clipping-Agents: alles Kundenspezifische
kommt aus der ClientConfig statt aus Konstanten.
"""
import html as html_module
import json
import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests

from .feeds import resolve_feeds

BLOCKED_DOMAINS = [
    "facebook.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "instagram.com", "tiktok.com",
    "rocketreach.co", "contactout.com", "theorg.com",
    "northdata.com", "xing.com", "kununu.com",
    "indeed.com", "glassdoor.com", "stepstone.de",
    "reddit.com", "pinterest.com", "amazon.com",
]

OUTLET_NAMES = {
    "faz.net": "Frankfurter Allgemeine Zeitung",
    "handelsblatt.com": "Handelsblatt",
    "nzz.ch": "Neue Zürcher Zeitung",
    "finews.ch": "Finews",
    "finews.com": "Finews",
    "dasinvestment.com": "DAS INVESTMENT",
    "fondsprofessionell.de": "FONDS professionell",
    "fondsprofessionell.at": "FONDS professionell",
    "institutional-money.com": "Institutional Money",
    "portfolio-institutionell.de": "portfolio institutionell",
    "handelszeitung.ch": "Handelszeitung",
    "boersen-zeitung.de": "Börsen-Zeitung",
    "derstandard.de": "Der Standard",
    "derstandard.at": "Der Standard",
    "diepresse.com": "Die Presse",
    "wiwo.de": "WirtschaftsWoche",
    "manager-magazin.de": "Manager Magazin",
    "capital.de": "Capital",
    "sueddeutsche.de": "Süddeutsche Zeitung",
    "welt.de": "Die Welt",
    "spiegel.de": "Der Spiegel",
    "zeit.de": "Die Zeit",
    "moneycab.com": "Moneycab",
    "investrends.ch": "investrends.ch",
    "bondguide.de": "BondGuide",
    "dfpa.info": "dfpa.info",
    "e-fundresearch.com": "e-fundresearch",
    "markteinblicke.de": "Markt Einblicke",
    "finanznachrichten.de": "finanznachrichten.de",
    "cash.ch": "cash.ch",
    "payoff.ch": "Payoff",
    "fondsexklusiv.de": "FONDS exklusiv",
    "fondsexklusiv.at": "FONDS exklusiv Österreich",
    "cash-online.de": "cash-online.de",
    "altii.de": "altii.de",
    "citywire.de": "Citywire Deutschland",
    "private-banking-magazin.de": "Private Banking Magazin",
    "fixed-income.org": "fixed-income.org",
    "finanzwelt.de": "finanzwelt",
    "procontra-online.de": "procontra",
    "boersen-kurier.at": "Börsen-Kurier",
    "kreditwesen.de": "Kreditwesen",
    "allnews.ch": "Allnews",
    "srf.ch": "SRF",
    "n-tv.de": "n-tv",
    "tagesanzeiger.ch": "Tages-Anzeiger",
    "gruenderszene.de": "Gründerszene",
    "deutsche-startups.de": "deutsche-startups.de",
    "t3n.de": "t3n",
    "aerztezeitung.de": "Ärzte Zeitung",
    "apotheke-adhoc.de": "Apotheke Adhoc",
    "pharmazeutische-zeitung.de": "Pharmazeutische Zeitung",
    "immobilien-zeitung.de": "Immobilien Zeitung",
    "kurier.at": "Kurier",
    "platow.de": "Platow",
}

COUNTRY_CH = [".ch", "finews", "payoff", "nzz", "investrends", "handelszeitung",
              "moneycab", "cash.ch", "allnews", "tagesanzeiger", "srf"]
COUNTRY_AT = [".at", "derstandard", "diepresse", "kurier.at", "boersen-kurier",
              "trendingtopics"]


# ── Utilities ──────────────────────────────────────────────────────

def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html_module.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url):
    url = (url or "").strip().rstrip("/").lower()
    url = re.sub(r"[?&](utm_\w+|ref|source|fbclid|gclid|xtor|wt_mc)=[^&]*", "", url)
    url = re.sub(r"#.*$", "", url)
    return url.rstrip("?&")


def extract_domain(url):
    return urlparse(url or "").netloc.lower().replace("www.", "")


def normalize_outlet(source, link=""):
    domain = extract_domain(link) if link else (source or "").lower().replace("www.", "")
    for key, name in OUTLET_NAMES.items():
        if key in domain:
            return name
    return source if source else domain


def is_blocked_domain(url):
    domain = extract_domain(url)
    return any(blocked in domain for blocked in BLOCKED_DOMAINS)


def guess_tier(tier1_keywords, outlet="", link=""):
    text = f"{outlet} {link}".lower()
    return 1 if any(k in text for k in tier1_keywords) else 2


def guess_country(outlet="", link=""):
    text = f"{outlet} {link}".lower()
    if any(k in text for k in COUNTRY_CH):
        return "CH"
    if any(k in text for k in COUNTRY_AT):
        return "A"
    return "D"


def extract_date(text, url=""):
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text or "")
    if m:
        d, mo, y = m.groups()
        if 2024 <= int(y) <= 2030:
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", text or "")
    if m:
        return m.group(0)
    m = re.search(r"(20\d{2})/(\d{2})/(\d{2})", url or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(20\d{2})/(\d{2})/", url or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    m = re.search(r"vor (\d+) Tag", text or "")
    if m:
        return (datetime.now() - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    return ""


def matches_keywords(result, keywords):
    text = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('source', '')}".lower()
    return any(kw in text for kw in keywords)


def is_duplicate(article, existing):
    link = normalize_url(article.get("link", ""))
    title = (article.get("title") or "").lower().strip()
    outlet = (article.get("outlet") or "").lower().strip()
    for c in existing:
        cl = normalize_url(c.get("link", ""))
        ct = (c.get("title") or "").lower().strip()
        co = (c.get("outlet") or "").lower().strip()
        if link and cl and link == cl:
            return True
        if title and ct and len(title) > 15 and len(ct) > 15:
            if title == ct:
                return True
            if outlet and co and outlet == co and (title in ct or ct in title):
                return True
    return False


def http_get(url, timeout=10, retries=2):
    for attempt in range(retries + 1):
        try:
            return requests.get(url, timeout=timeout,
                                headers={"User-Agent": "ClipRadar/0.1"})
        except Exception:
            if attempt < retries:
                time.sleep(2)
            else:
                raise
    return None


# ── Persistenz ─────────────────────────────────────────────────────

def load_clippings(cfg):
    if cfg.data_file.exists():
        with open(cfg.data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_clippings(cfg, clips):
    cfg.data_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg.data_file, "w", encoding="utf-8") as f:
        json.dump(clips, f, ensure_ascii=False, indent=2)


# ── RSS ────────────────────────────────────────────────────────────

def scan_rss_feeds(cfg):
    import feedparser

    feeds = resolve_feeds(cfg.feed_packs, cfg.extra_rss_feeds)
    print(f"  RSS: {len(feeds)} Feeds werden gescannt...")
    results = []
    feeds_ok = 0

    for feed_url in feeds:
        try:
            resp = http_get(feed_url, timeout=8, retries=1)
            if not resp or resp.status_code != 200:
                continue
            feed = feedparser.parse(resp.content)
            if not feed.entries:
                continue
            feeds_ok += 1
            feed_domain = extract_domain(feed_url)

            for entry in feed.entries[:40]:
                title = strip_html(entry.get("title", ""))
                summary = strip_html(
                    entry.get("summary", "") or entry.get("description", "") or
                    (entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "")
                )
                link = entry.get("link", "")
                text = f"{title} {summary[:500]}".lower()
                if any(kw in text for kw in cfg.keywords):
                    date = ""
                    for date_field in ["published_parsed", "updated_parsed"]:
                        if entry.get(date_field):
                            try:
                                date = datetime(*entry[date_field][:6]).strftime("%Y-%m-%d")
                                break
                            except Exception:
                                pass
                    results.append({
                        "title": title.split(" - ")[0].split(" | ")[0].strip(),
                        "link": link,
                        "snippet": summary[:300],
                        "source": feed_domain,
                        "date": date or extract_date(summary, link),
                    })
        except Exception:
            continue

    print(f"  RSS: {feeds_ok}/{len(feeds)} Feeds OK, {len(results)} relevante Treffer")
    return results


# ── Google Custom Search ───────────────────────────────────────────

def google_search(query, api_key, cx, sort_by_date=False, start=1):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key, "cx": cx, "q": query, "num": 10,
        "lr": "lang_de", "dateRestrict": "m9", "start": start,
    }
    if sort_by_date:
        params["sort"] = "date"
    try:
        resp = requests.get(url, params=params, timeout=15,
                            headers={"User-Agent": "ClipRadar/0.1"})
        if resp.status_code == 429:
            print("    Google Rate-Limit erreicht")
            return None
        if resp.status_code != 200:
            print(f"    Google API Fehler {resp.status_code}")
            return []
        return [
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": item.get("displayLink", ""),
            }
            for item in resp.json().get("items", [])
            if not is_blocked_domain(item.get("link", ""))
        ]
    except Exception as e:
        print(f"    Google Fehler: {e}")
        return []


def run_google_queries(cfg, api_key, cx):
    results = []
    queries = [(q, False) for q in cfg.google_queries] + \
              [(q, True) for q in cfg.google_news_queries]
    for query, by_date in queries:
        batch = google_search(query, api_key, cx, sort_by_date=by_date)
        if batch is None:
            break
        relevant = [r for r in batch if matches_keywords(r, cfg.keywords)]
        results.extend(relevant)
        if query in cfg.page2_queries and len(batch) >= 8:
            batch2 = google_search(query, api_key, cx, start=11)
            if batch2 is None:
                break
            results.extend(r for r in batch2 if matches_keywords(r, cfg.keywords))
        time.sleep(1)
    return results


# ── Claude-Validierung ─────────────────────────────────────────────

def build_validation_prompt(cfg):
    disambiguation = f"\nBEKANNTE VERWECHSLUNGEN / FALSE POSITIVES:\n{cfg.disambiguation}\n" if cfg.disambiguation else ""
    return f"""Du prüfst, ob Suchergebnisse tatsächlich den Kunden "{cfg.name}" DIREKT erwähnen (nicht nur in Sidebar-Links oder Werbung).

KUNDENKONTEXT:
{cfg.context or cfg.name}

RELEVANTE SUCHBEGRIFFE: {", ".join(cfg.keywords)}
{disambiguation}
Prüfe für jeden Eintrag:
1. Wird der Kunde (oder eine seiner Personen/Marken) im Artikeltext selbst erwähnt?
2. Passt das Thema zum Kundenkontext?
3. Ist es KEIN Sidebar-Link, keine Werbung, kein "Weitere Artikel"-Verweis?

AUSGABE: Nur die RELEVANTEN Artikel als JSON-Array:
[{{"date":"YYYY-MM-DD","outlet":"Offizieller Medienname","title":"Exakter Artikeltitel","country":"D/CH/A","type":"Online","tier":1 oder 2,"link":"URL"}}]

Keine Treffer? Antworte: []"""


def validate_with_claude(client, cfg, results):
    if not results:
        return []
    text_results = [
        f"{i + 1}. Quelle: {r.get('source', '')}\n"
        f"   Titel: {r.get('title', '')}\n"
        f"   Snippet: {r.get('snippet', '')[:200]}\n"
        f"   URL: {r.get('link', '')}"
        for i, r in enumerate(results)
    ]
    try:
        response = client.messages.create(
            model=os.environ.get("CLIPRADAR_MODEL", "claude-sonnet-5"),
            max_tokens=4000,
            system=build_validation_prompt(cfg),
            messages=[{
                "role": "user",
                "content": "Prüfe diese Suchergebnisse und gib NUR die relevanten Artikel als JSON zurück:\n\n"
                           + "\n\n".join(text_results),
            }],
        )
        all_text = "\n".join(b.text for b in response.content if hasattr(b, "text") and b.text)
        for match in re.findall(r"\[[\s\S]*?\]", all_text) + re.findall(r"\[[\s\S]*\]", all_text):
            try:
                parsed = json.loads(match)
                if isinstance(parsed, list):
                    return [a for a in parsed if isinstance(a, dict) and a.get("title")]
            except json.JSONDecodeError:
                continue
        return []
    except Exception as e:
        print(f"    Claude Fehler: {e}")
        return None  # None = Validierung fehlgeschlagen, [] = keine Treffer


def auto_classify_result(cfg, result):
    raw_title = result.get("title", "")
    link = result.get("link", "")
    source = result.get("source", "")
    return {
        "title": raw_title.split(" - ")[0].split(" | ")[0].strip(),
        "link": link,
        "outlet": normalize_outlet(source, link),
        "date": result.get("date") or extract_date(result.get("snippet", ""), link),
        "tier": guess_tier(cfg.all_tier1_keywords(), source, link),
        "country": guess_country(source, link),
        "type": "Online",
    }


# ── Pipeline ───────────────────────────────────────────────────────

def run_monitor(cfg):
    """Komplette Monitoring-Pipeline für einen Kunden. Gibt neue Artikel zurück."""
    print(f"\n{'=' * 60}\nClipRadar — {cfg.name} ({cfg.client_id}, Plan: {cfg.plan})\n{'=' * 60}")

    existing = load_clippings(cfg)
    existing_urls = {normalize_url(c.get("link", "")) for c in existing if c.get("link")}
    print(f"Bestehende Clippings: {len(existing)}")

    all_results = list(scan_rss_feeds(cfg))

    google_key = os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_CX")
    if google_key and google_cx and cfg.google_queries:
        print(f"  Google: {len(cfg.google_queries) + len(cfg.google_news_queries)} Suchanfragen...")
        all_results.extend(run_google_queries(cfg, google_key, google_cx))

    # Dedup gegen Bestand und innerhalb des Laufs
    seen_urls = set()
    unique_results = []
    for r in all_results:
        url = normalize_url(r.get("link", ""))
        if url and url not in seen_urls and url not in existing_urls:
            seen_urls.add(url)
            unique_results.append(r)
    print(f"  {len(unique_results)} neue Treffer zur Validierung")

    if not unique_results:
        return []

    # Claude-Validierung (Fallback: Auto-Klassifizierung)
    validated = []
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        batch_size = 15
        for i in range(0, len(unique_results), batch_size):
            batch = unique_results[i:i + batch_size]
            articles = validate_with_claude(client, cfg, batch)
            if articles is None:
                validated.extend(auto_classify_result(cfg, r) for r in batch)
            else:
                validated.extend(articles)
            time.sleep(2)
        source_tag = "auto"
    else:
        validated = [auto_classify_result(cfg, r) for r in unique_results]
        source_tag = "auto-unvalidated"

    # Anreichern, final deduplizieren, speichern
    new_articles = []
    for a in validated:
        a["tier"] = a.get("tier") or guess_tier(cfg.all_tier1_keywords(), a.get("outlet", ""), a.get("link", ""))
        a["country"] = a.get("country") or guess_country(a.get("outlet", ""), a.get("link", ""))
        a["type"] = a.get("type") or "Online"
        a["outlet"] = normalize_outlet(a.get("outlet", ""), a.get("link", ""))
        if not a.get("date"):
            a["date"] = extract_date("", a.get("link", ""))
        if not is_duplicate(a, existing) and not is_duplicate(a, new_articles):
            a["added_at"] = datetime.now().isoformat()
            a["source"] = source_tag
            new_articles.append(a)

    if new_articles:
        all_clips = existing + new_articles
        all_clips.sort(key=lambda x: x.get("date", ""), reverse=True)
        save_clippings(cfg, all_clips)
        print(f"  NEU: {len(new_articles)} Artikel")
        for a in new_articles:
            print(f"    + {a.get('date', '')} | {a.get('outlet', '')} | {a.get('title', '')[:55]}")
    else:
        print("  Keine neuen Artikel")

    return new_articles
