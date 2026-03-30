"""
MK Global Kapital - DACH Clipping Agent
Google Custom Search API + RSS Feeds + Claude validation.
Optimized for maximum recall with minimum false positives.
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import requests
import anthropic

# Try to import feedparser, install if missing
try:
    import feedparser
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "feedparser", "--break-system-packages", "-q"])
    import feedparser

# === RSS FEEDS (free, unlimited, checked every run) ===
RSS_FEEDS = [
    # --- TIER 1: Major financial media ---
    # FAZ
    "https://www.faz.net/rss/aktuell/finanzen/",
    "https://www.faz.net/rss/aktuell/wirtschaft/",
    # Handelsblatt
    "https://www.handelsblatt.com/contentexport/feed/finanzen",
    "https://www.handelsblatt.com/contentexport/feed/unternehmen",
    # NZZ
    "https://www.nzz.ch/finanzen.rss",
    "https://www.nzz.ch/wirtschaft.rss",
    # Finews
    "https://www.finews.ch/news/finanzplatz/rss/1finews",
    # DAS INVESTMENT
    "https://www.dasinvestment.com/api/rss/",
    "https://www.dasinvestment.com/feed/",
    # FONDS professionell
    "https://www.fondsprofessionell.de/rss/news.xml",
    "https://www.fondsprofessionell.de/feed/",
    # Institutional Money
    "https://www.institutional-money.com/rss/news/",
    # portfolio institutionell
    "https://www.portfolio-institutionell.de/feed/",
    # Handelszeitung
    "https://www.handelszeitung.ch/rss.xml",
    # Börsen-Zeitung
    "https://www.boersen-zeitung.de/rss",
    
    # --- TIER 1: General DACH media ---
    # Der Standard
    "https://www.derstandard.at/rss/wirtschaft",
    "https://www.derstandard.at/rss/finanzen",
    # Die Presse
    "https://diepresse.com/rss/Wirtschaft",
    # WirtschaftsWoche
    "https://www.wiwo.de/contentexport/feed/rss/schlagzeilen/finanzen/",
    # Manager Magazin
    "https://www.manager-magazin.de/finanzen/index.rss",
    # Capital
    "https://www.capital.de/feed/rss",
    # SZ
    "https://rss.sueddeutsche.de/rss/Wirtschaft",
    # Welt
    "https://www.welt.de/feeds/section/finanzen.rss",
    
    # --- TIER 2: Specialist media ---
    # Moneycab
    "https://www.moneycab.com/feed/",
    # investrends.ch
    "https://investrends.ch/feed/",
    # bondguide.de
    "https://www.bondguide.de/feed/",
    # dfpa.info
    "https://www.dfpa.info/rss/",
    "https://www.dfpa.info/feed/",
    # e-fundresearch
    "https://e-fundresearch.com/rss",
    "https://e-fundresearch.com/feeds/news",
    # markteinblicke.de
    "https://markteinblicke.de/feed/",
    # finanznachrichten.de
    "https://www.finanznachrichten.de/rss-alle-nachrichten",
    # cash.ch
    "https://www.cash.ch/rss/news",
    # Payoff
    "https://www.payoff.ch/feed/",
    "https://www.payoff.ch/rss",
    # FONDS exklusiv
    "https://www.fondsexklusiv.de/feed/",
    "https://www.fondsexklusiv.at/feed/",
    # cash-online.de
    "https://www.cash-online.de/feed/",
    # altii
    "https://www.altii.de/feed/",
    "https://www.altii.de/rss/",
    # Citywire
    "https://citywire.de/feed/",
    # private-banking-magazin
    "https://www.private-banking-magazin.de/feed/",
    # fixed-income.org
    "https://www.fixed-income.org/feed/",
    "https://www.fixed-income.org/rss/",
    # finanzwelt.de
    "https://www.finanzwelt.de/feed/",
    # procontra-online
    "https://www.procontra-online.de/feed/",
    # exxecnews
    "https://exxecnews.org/feed/",
    # Börsen-Kurier
    "https://www.boersen-kurier.at/feed/",
    # Kreditwesen
    "https://www.kreditwesen.de/feed/",
    # allnews.ch
    "https://www.allnews.ch/rss",
    # Swiss Finance AI
    "https://www.swissfinanceai.ch/blog/rss.xml",
    "https://www.swissfinanceai.ch/feed/",
    # SRF
    "https://www.srf.ch/news/wirtschaft/rss/feed",
    # n-tv
    "https://www.n-tv.de/wirtschaft/rss",
    # tagesanzeiger
    "https://www.tagesanzeiger.ch/wirtschaft/rss.xml",
    # geldmeisterin
    "https://www.geldmeisterin.com/feed/",
    # gruenderkueche
    "https://www.gruenderkueche.de/feed/",
    # platow
    "https://www.platow.de/feed/",
    # fondstrends
    "https://fondstrends.ch/feed/",
    "https://fondstrends.de/feed/",
]


def scan_rss_feeds():
    """Scan all RSS feeds for MK-relevant articles. Free and unlimited."""
    print(f"Scanning {len(RSS_FEEDS)} RSS feeds...\n")
    results = []
    feeds_ok = 0
    feeds_fail = 0
    
    for feed_url in RSS_FEEDS:
        try:
            # Timeout via requests first, then parse
            resp = requests.get(feed_url, timeout=8, headers={"User-Agent": "MK-Clipping-Agent/1.0"})
            if resp.status_code != 200:
                feeds_fail += 1
                continue
            
            feed = feedparser.parse(resp.content)
            if not feed.entries:
                feeds_fail += 1
                continue
            
            feeds_ok += 1
            feed_source = urlparse(feed_url).netloc.replace("www.", "")
            
            for entry in feed.entries[:30]:  # Check last 30 entries per feed
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")
                
                # Check if MK-relevant
                text = f"{title} {summary}".lower()
                if any(kw in text for kw in MK_KEYWORDS):
                    # Extract date
                    date = ""
                    if entry.get("published_parsed"):
                        try:
                            dt = datetime(*entry.published_parsed[:6])
                            date = dt.strftime("%Y-%m-%d")
                        except:
                            pass
                    elif entry.get("updated_parsed"):
                        try:
                            dt = datetime(*entry.updated_parsed[:6])
                            date = dt.strftime("%Y-%m-%d")
                        except:
                            pass
                    
                    results.append({
                        "title": title.split(" - ")[0].split(" | ")[0].strip(),
                        "link": link,
                        "snippet": summary[:200] if summary else "",
                        "source": feed_source,
                        "date": date,
                    })
        except Exception:
            feeds_fail += 1
            continue
    
    print(f"  RSS: {feeds_ok} feeds OK, {feeds_fail} failed/empty, {len(results)} MK-relevant entries found\n")
    return results

# === GOOGLE SEARCH QUERIES ===
# Budget: 100 free/day. At 3 runs/day = ~33 per run.
# We use 32 queries = 96/day, safely under limit.
GOOGLE_QUERIES = [
    # --- BARE NAME SEARCHES (highest recall — catches everything) ---
    '"Johannes Feist"',
    '"Michele Mattioda"',
    '"Louzia Savchenko"',
    '"MK Global Kapital"',
    '"Mikro Kapital"',

    # --- BRAND + CONTEXT ---
    '"Mikro Kapital" Mikrofinanz',
    '"Mikro Kapital Management"',
    '"MK Global" Mikrofinanz',
    '"MK Global" "Private Debt"',
    '"MK Global" "Private Credit"',
    '"MK Global" Impact',
    '"MK Global" Anleihe',
    '"MK Global" ALTERNATIVE Fonds',
    '"Mikro Kapital" ESG',
    '"Mikro Kapital" Seidenstrasse OR Zentralasien',

    # --- PEOPLE + CONTEXT (catches guest articles) ---
    '"Johannes Feist" Gastkommentar OR Gastbeitrag',
    '"Johannes Feist" "Private Credit" OR "Private Debt"',
    '"Johannes Feist" Mikrofinanz CEO',
    '"Johannes Feist" Emerging Markets',
    '"Johannes Feist" Wasserknappheit OR Klima OR ESG',
    '"Michele Mattioda" Mikrofinanz OR "MK Global"',
    '"Louzia Savchenko" Tokenisierung OR tokenisiert',
    '"Vincenzo Trani" "Mikro Kapital"',
    '"Thomas Heinig" "Mikro Kapital" OR "MK Global"',
    '"Luca Pellegrini" "MK Global" OR "Mikro Kapital"',

    # --- BROAD CATCHES ---
    '"MK Global Kapital" OR "Mikro Kapital" 2026',
    '"Johannes Feist" OR "MK Global" Finanzen 2026',
]

# Google News-specific queries (use sort=date for freshness)
GOOGLE_NEWS_QUERIES = [
    '"MK Global Kapital"',
    '"Johannes Feist" Mikrofinanz',
    '"Mikro Kapital"',
    '"Louzia Savchenko"',
    '"Michele Mattioda"',
]

TIER1_KEYWORDS = [
    "faz", "frankfurter allgemeine", "handelsblatt",
    "boersen-zeitung", "börsen-zeitung", "nzz", "neue zuercher",
    "finews", "institutional money", "institutional-money",
    "das investment", "dasinvestment",
    "fonds professionell", "fondsprofessionell",
    "altii", "citywire",
    "portfolio institutionell", "portfolio-institutionell",
    "handelszeitung",
    "der standard", "derstandard",
    "die presse", "diepresse",
    "wiwo", "wirtschaftswoche",
    "manager magazin", "manager-magazin",
    "capital.de", "sueddeutsche",
]

# Keywords that MUST appear in title/snippet to be MK-relevant
MK_KEYWORDS = [
    "mk global kapital", "mikro kapital", "johannes feist",
    "michele mattioda", "louzia savchenko", "vincenzo trani",
    "thomas heinig", "luca pellegrini",
    "mikrokapital", "mk global",
]

# Known false-positive domains (social media, job boards, etc.)
BLOCKED_DOMAINS = [
    "facebook.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "instagram.com", "tiktok.com",
    "rocketreach.co", "contactout.com", "theorg.com",
    "northdata.com", "xing.com", "kununu.com",
    "indeed.com", "glassdoor.com", "stepstone.de",
]

VALIDATION_PROMPT = """Du pruefst ob Artikel tatsaechlich MK Global Kapital, Mikro Kapital oder eine der folgenden Personen DIREKT erwaehnen (nicht nur in Sidebar-Links oder Werbung):
- Dr. Johannes Feist (CEO), Michele Mattioda, Louzia Savchenko, Vincenzo Trani, Thomas Heinig, Luca Pellegrini

WICHTIG: Es gibt einen anderen "Johannes Feist" der nichts mit MK Global Kapital zu tun hat (z.B. Edeka-Markt Gundelfingen). NUR Artikel ueber den MK Global Kapital CEO sind relevant!

Fuer jeden Artikel: Pruefe ob er RELEVANT ist:
1. MK/Mikro Kapital/eine MK-Person wird im Artikeltext selbst erwaehnt
2. Es geht um Finanzen/Mikrofinanz/Impact/Private Debt — NICHT um Supermaerkte oder andere Branchen
3. KEINE Artikel die nur zufaellig auf derselben Seite verlinkt sind (Sidebar, "Weitere Artikel")

EINGABE: Liste von Google-Suchergebnissen mit Titel, Snippet und URL.
AUSGABE: Nur die RELEVANTEN Artikel als JSON-Array:
[{"date":"YYYY-MM-DD","outlet":"Medienname","title":"Exakter Artikeltitel","country":"D/CH/A/DACH","type":"Online","tier":1 oder 2,"link":"URL"}]

TIER-ZUORDNUNG:
Tier 1: FAZ, Handelsblatt, Boersen-Zeitung, NZZ, Finews, Institutional Money, DAS INVESTMENT, FONDS professionell, altii, Citywire, portfolio institutionell, Handelszeitung, Der Standard, Die Presse, WirtschaftsWoche, Manager Magazin
Tier 2: Alle anderen

- Datum: Aus Snippet/URL/Kontext ableiten. Format YYYY-MM-DD. Falls unklar: leer lassen.
- Outlet: Exakter Medienname (z.B. "Frankfurter Allgemeine Zeitung", nicht "faz.net")
- Keine Treffer? Antworte: []"""

DATA_FILE = Path(__file__).parent.parent / "data" / "clippings.json"


def load_clippings():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_clippings(clips):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(clips, f, ensure_ascii=False, indent=2)


def normalize_url(url):
    """Normalize URL for deduplication: strip trailing slash, fragment, tracking params."""
    url = url.strip().rstrip("/").lower()
    # Remove common tracking parameters
    url = re.sub(r'[?&](utm_\w+|ref|source|fbclid|gclid)=[^&]*', '', url)
    url = url.rstrip("?&")
    return url


def is_duplicate(article, existing):
    link = normalize_url(article.get("link", ""))
    title = article.get("title", "").lower().strip()
    outlet = article.get("outlet", "").lower().strip()
    for c in existing:
        cl = normalize_url(c.get("link", ""))
        ct = c.get("title", "").lower().strip()
        co = c.get("outlet", "").lower().strip()
        # Same URL
        if link and cl and link == cl:
            return True
        # Same title + outlet
        if title and ct and outlet and co:
            if title == ct and outlet == co:
                return True
            # Partial title match (one title contains the other)
            if outlet == co and len(title) > 15 and (title in ct or ct in title):
                return True
    return False


def guess_tier(outlet="", link=""):
    text = (outlet + " " + link).lower()
    return 1 if any(k in text for k in TIER1_KEYWORDS) else 2


def guess_country(outlet="", link=""):
    text = (outlet + " " + link).lower()
    if any(k in text for k in [".ch", "finews", "payoff", "nzz", "investrends", "handelszeitung", "moneycab", "cash.ch", "allnews.ch", "swissfinanceai.ch"]):
        return "CH"
    if any(k in text for k in [".at", "derstandard", "diepresse", "kurier.at", "boersen-kurier", "fondsexklusiv.at"]):
        return "A"
    return "D"


def is_blocked_domain(url):
    """Filter out social media, job boards, contact databases."""
    domain = urlparse(url).netloc.lower()
    return any(blocked in domain for blocked in BLOCKED_DOMAINS)


def google_search(query, api_key, cx, sort_by_date=False):
    """Run a single Google Custom Search query. Returns list of results."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": 10,
        "lr": "lang_de",
        "dateRestrict": "m6",
    }
    if sort_by_date:
        params["sort"] = "date"
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 429:
            print("    RATE LIMIT - stopping Google searches")
            return None
        if resp.status_code != 200:
            print(f"    Google API error {resp.status_code}: {resp.text[:200]}")
            return []
        data = resp.json()
        results = []
        for item in data.get("items", []):
            link = item.get("link", "")
            if not is_blocked_domain(link):
                results.append({
                    "title": item.get("title", ""),
                    "link": link,
                    "snippet": item.get("snippet", ""),
                    "source": item.get("displayLink", ""),
                })
        return results
    except Exception as e:
        print(f"    Google error: {e}")
        return []


def is_mk_relevant(result):
    """Pre-filter: does the result mention MK keywords in title/snippet?"""
    text = f"{result.get('title','')} {result.get('snippet','')} {result.get('source','')}".lower()
    return any(kw in text for kw in MK_KEYWORDS)


def auto_classify_result(result):
    """Create a clipping directly from Google result without Claude.
    Used as fallback when Claude API is unavailable."""
    title = result.get("title", "").split(" - ")[0].split(" | ")[0].strip()
    link = result.get("link", "")
    source = result.get("source", "")
    snippet = result.get("snippet", "")
    
    # Try to extract date from snippet (pattern: "vor X Tagen", "DD.MM.YYYY", etc.)
    date = ""
    date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', snippet)
    if date_match:
        d, m, y = date_match.groups()
        date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    
    return {
        "title": title,
        "link": link,
        "outlet": source,
        "date": date,
        "tier": guess_tier(source, link),
        "country": guess_country(source, link),
        "type": "Online",
    }


def validate_with_claude(client, results):
    """Use Claude to validate and structure Google results into clippings."""
    if not results:
        return []
    
    text_results = []
    for i, r in enumerate(results):
        text_results.append(
            f"{i+1}. Quelle: {r.get('source','')}\n"
            f"   Titel: {r.get('title','')}\n"
            f"   Snippet: {r.get('snippet','')}\n"
            f"   URL: {r.get('link','')}"
        )
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=VALIDATION_PROMPT,
            messages=[{
                "role": "user",
                "content": "Pruefe diese Google-Suchergebnisse und gib NUR die relevanten MK Global Kapital Artikel als JSON zurueck:\n\n" + "\n\n".join(text_results)
            }],
        )
        
        texts = []
        for block in response.content:
            if hasattr(block, "text") and block.text:
                texts.append(block.text)
        all_text = "\n".join(texts)
        
        for pattern in [r'\[[\s\S]*?\]', r'\[[\s\S]*\]']:
            for match in re.findall(pattern, all_text):
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, list):
                        return [a for a in parsed if isinstance(a, dict) and a.get("title")]
                except json.JSONDecodeError:
                    continue
        return []
    except Exception as e:
        print(f"    Claude validation error: {e}")
        return None  # None signals Claude failure (vs [] = no results)


def run_search():
    google_key = os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_CX")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not google_key or not google_cx:
        print("WARNING: GOOGLE_API_KEY or GOOGLE_CX not set, falling back to Anthropic-only search")
        return run_anthropic_fallback()
    
    existing = load_clippings()
    new_articles = []
    all_google_results = []
    rate_limited = False
    
    print(f"Loaded {len(existing)} existing clippings")
    
    # Step 0: RSS Feed scan (free, unlimited)
    rss_results = scan_rss_feeds()
    for r in rss_results:
        if not is_blocked_domain(r.get("link", "")):
            all_google_results.append(r)
    
    print(f"Running {len(GOOGLE_QUERIES)} web queries + {len(GOOGLE_NEWS_QUERIES)} news queries...\n")
    
    # Step 1a: Regular Google searches
    for i, query in enumerate(GOOGLE_QUERIES):
        if rate_limited:
            break
        print(f"[Google {i+1}/{len(GOOGLE_QUERIES)}] {query[:60]}...")
        results = google_search(query, google_key, google_cx)
        
        if results is None:
            rate_limited = True
            break
        
        relevant = [r for r in results if is_mk_relevant(r)]
        print(f"  -> {len(results)} results, {len(relevant)} MK-relevant")
        all_google_results.extend(relevant)
        time.sleep(1)
    
    # Step 1b: Google News searches (sort by date for freshness)
    if not rate_limited:
        for i, query in enumerate(GOOGLE_NEWS_QUERIES):
            if rate_limited:
                break
            print(f"[News {i+1}/{len(GOOGLE_NEWS_QUERIES)}] {query[:60]}...")
            results = google_search(query, google_key, google_cx, sort_by_date=True)
            
            if results is None:
                rate_limited = True
                break
            
            relevant = [r for r in results if is_mk_relevant(r)]
            print(f"  -> {len(results)} results, {len(relevant)} MK-relevant")
            all_google_results.extend(relevant)
            time.sleep(1)
    
    # Step 2: Deduplicate Google results by URL
    seen_urls = set()
    unique_results = []
    for r in all_google_results:
        url = normalize_url(r.get("link", ""))
        if url and url not in seen_urls:
            # Also skip if already in existing clippings
            if not any(normalize_url(c.get("link","")) == url for c in existing):
                seen_urls.add(url)
                unique_results.append(r)
    
    print(f"\n{len(unique_results)} unique NEW MK-relevant Google results found")
    
    if not unique_results:
        print("No new results to process")
        return []
    
    # Step 3: Validate with Claude (or fallback to auto-classify)
    claude_available = bool(anthropic_key)
    client = None
    if claude_available:
        try:
            client = anthropic.Anthropic(api_key=anthropic_key)
        except Exception as e:
            print(f"Claude client init error: {e}")
            claude_available = False
    
    validated = []
    if claude_available:
        print(f"\nValidating with Claude...\n")
        batch_size = 15
        for i in range(0, len(unique_results), batch_size):
            batch = unique_results[i:i+batch_size]
            print(f"[Claude] Validating batch {i//batch_size + 1} ({len(batch)} results)...")
            articles = validate_with_claude(client, batch)
            
            if articles is None:
                # Claude failed — fall back to auto-classify for this batch
                print("  Claude unavailable, auto-classifying this batch...")
                for r in batch:
                    validated.append(auto_classify_result(r))
            elif articles:
                validated.extend(articles)
                print(f"  -> {len(articles)} valid articles")
            else:
                print(f"  -> 0 valid")
            time.sleep(2)
    else:
        # No Claude at all — auto-classify everything
        print("\nClaude API unavailable. Auto-classifying all results...\n")
        for r in unique_results:
            validated.append(auto_classify_result(r))
        print(f"  Auto-classified {len(validated)} results")
    
    # Step 4: Deduplicate against existing and add
    for a in validated:
        a["tier"] = a.get("tier") or guess_tier(a.get("outlet", ""), a.get("link", ""))
        a["country"] = a.get("country") or guess_country(a.get("outlet", ""), a.get("link", ""))
        a["type"] = a.get("type") or "Online"
        if not is_duplicate(a, existing) and not is_duplicate(a, new_articles):
            a["added_at"] = datetime.now().isoformat()
            a["source"] = "auto-google" if claude_available else "auto-google-noclaudecheck"
            a["id"] = f"g-{int(datetime.now().timestamp())}-{len(new_articles)}"
            new_articles.append(a)
    
    if new_articles:
        all_clips = existing + new_articles
        all_clips.sort(key=lambda x: x.get("date", ""), reverse=True)
        save_clippings(all_clips)
        print(f"\n{'='*50}")
        print(f"RESULT: {len(new_articles)} new articles added")
        print(f"TOTAL:  {len(all_clips)} clippings in database")
        print(f"{'='*50}")
        for a in new_articles:
            print(f"  + {a.get('date','')} | {a.get('outlet','')} | {a.get('title','')[:60]}")
    else:
        print(f"\nNo new articles found (existing: {len(existing)})")
    
    return new_articles


def run_anthropic_fallback():
    """Fallback if Google keys are not set - uses Anthropic web search."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return []
    
    client = anthropic.Anthropic(api_key=anthropic_key)
    existing = load_clippings()
    new_articles = []
    
    fallback_queries = [
        '"MK Global Kapital"',
        '"Mikro Kapital" Mikrofinanz',
        '"Johannes Feist" Mikrofinanz OR "MK Global"',
        '"Johannes Feist" "Private Credit" OR Gastkommentar',
        '"Michele Mattioda" "MK Global"',
        '"Louzia Savchenko" "MK Global" OR Tokenisierung',
    ]
    
    system = """Finde ALLE deutschsprachigen Medienartikel zu MK Global Kapital / Mikro Kapital / Johannes Feist / Michele Mattioda / Louzia Savchenko.
Antworte NUR mit JSON-Array:
[{"date":"YYYY-MM-DD","outlet":"Medienname","title":"Titel","country":"D/CH/A/DACH","type":"Online/Print","tier":1 oder 2,"link":"URL"}]
Keine Treffer? []"""
    
    for i, q in enumerate(fallback_queries):
        print(f"[Fallback {i+1}/{len(fallback_queries)}] {q}...")
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": f"Suche: {q}"}],
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
            )
            texts = []
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    texts.append(block.text)
                if hasattr(block, "content") and isinstance(block.content, list):
                    for sub in block.content:
                        if hasattr(sub, "text") and sub.text:
                            texts.append(sub.text)
            all_text = "\n".join(texts)
            for pattern in [r'\[[\s\S]*?\]', r'\[[\s\S]*\]']:
                for match in re.findall(pattern, all_text):
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, list):
                            for a in parsed:
                                if isinstance(a, dict) and a.get("title"):
                                    a["tier"] = a.get("tier") or guess_tier(a.get("outlet",""), a.get("link",""))
                                    a["country"] = a.get("country") or guess_country(a.get("outlet",""), a.get("link",""))
                                    a["type"] = a.get("type") or "Online"
                                    if not is_duplicate(a, existing) and not is_duplicate(a, new_articles):
                                        a["added_at"] = datetime.now().isoformat()
                                        a["source"] = "auto-anthropic"
                                        a["id"] = f"a-{int(datetime.now().timestamp())}-{len(new_articles)}"
                                        new_articles.append(a)
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(2)
    
    if new_articles:
        all_clips = existing + new_articles
        all_clips.sort(key=lambda x: x.get("date", ""), reverse=True)
        save_clippings(all_clips)
    
    return new_articles


if __name__ == "__main__":
    new = run_search()
    print(f"\nDone. {len(new)} new clippings added.")
