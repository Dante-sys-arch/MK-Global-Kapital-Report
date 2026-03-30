"""
MK Global Kapital - DACH Clipping Agent v3.0
Google Custom Search API + 60+ RSS Feeds + Claude validation.
Maximum recall, minimum false positives, full robustness.
"""
import json
import os
import re
import time
import html as html_module
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import requests
import anthropic

try:
    import feedparser
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "feedparser", "--break-system-packages", "-q"])
    import feedparser


# ╔══════════════════════════════════════════════════════════════╗
# ║  CONFIGURATION                                              ║
# ╚══════════════════════════════════════════════════════════════╝

MK_KEYWORDS = [
    "mk global kapital", "mikro kapital", "johannes feist",
    "michele mattioda", "louzia savchenko", "vincenzo trani",
    "thomas heinig", "luca pellegrini",
    "mikrokapital", "mk global",
]

TIER1_KEYWORDS = [
    "faz", "frankfurter allgemeine", "handelsblatt",
    "boersen-zeitung", "börsen-zeitung", "nzz", "neue zuercher", "neue zürcher",
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
    "boerse-online", "börse online",
]

# Normalize messy source names to clean outlet names
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
    "exxecnews.org": "exxecnews",
    "boersen-kurier.at": "Börsen-Kurier",
    "kreditwesen.de": "Kreditwesen",
    "allnews.ch": "Allnews",
    "swissfinanceai.ch": "Swiss Finance AI",
    "srf.ch": "SRF",
    "n-tv.de": "n-tv",
    "tagesanzeiger.ch": "Tages-Anzeiger",
    "geldmeisterin.com": "geldmeisterin.com",
    "gruenderkueche.de": "Gründerküche",
    "platow.de": "Platow",
    "kurier.at": "Kurier",
}

BLOCKED_DOMAINS = [
    "facebook.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "instagram.com", "tiktok.com",
    "rocketreach.co", "contactout.com", "theorg.com",
    "northdata.com", "xing.com", "kununu.com",
    "indeed.com", "glassdoor.com", "stepstone.de",
    "reddit.com", "pinterest.com", "amazon.com",
]

COUNTRY_CH = [".ch", "finews", "payoff", "nzz", "investrends", "handelszeitung",
    "moneycab", "cash.ch", "allnews.ch", "swissfinanceai.ch", "tagesanzeiger", "srf.ch"]
COUNTRY_AT = [".at", "derstandard", "diepresse", "kurier.at", "boersen-kurier", "fondsexklusiv.at"]


# ╔══════════════════════════════════════════════════════════════╗
# ║  RSS FEEDS                                                   ║
# ╚══════════════════════════════════════════════════════════════╝

RSS_FEEDS = [
    # TIER 1: Major financial media
    "https://www.faz.net/rss/aktuell/finanzen/",
    "https://www.faz.net/rss/aktuell/wirtschaft/",
    "https://www.handelsblatt.com/contentexport/feed/finanzen",
    "https://www.handelsblatt.com/contentexport/feed/unternehmen",
    "https://www.nzz.ch/finanzen.rss",
    "https://www.nzz.ch/wirtschaft.rss",
    "https://www.finews.ch/news/finanzplatz/rss/1finews",
    "https://www.dasinvestment.com/api/rss/",
    "https://www.dasinvestment.com/feed/",
    "https://www.fondsprofessionell.de/rss/news.xml",
    "https://www.fondsprofessionell.de/feed/",
    "https://www.institutional-money.com/rss/news/",
    "https://www.portfolio-institutionell.de/feed/",
    "https://www.handelszeitung.ch/rss.xml",
    "https://www.boersen-zeitung.de/rss",
    # TIER 1: General DACH
    "https://www.derstandard.at/rss/wirtschaft",
    "https://www.derstandard.at/rss/finanzen",
    "https://diepresse.com/rss/Wirtschaft",
    "https://www.wiwo.de/contentexport/feed/rss/schlagzeilen/finanzen/",
    "https://www.manager-magazin.de/finanzen/index.rss",
    "https://www.capital.de/feed/rss",
    "https://rss.sueddeutsche.de/rss/Wirtschaft",
    "https://www.welt.de/feeds/section/finanzen.rss",
    "https://kurier.at/wirtschaft/rss",
    # TIER 2: Specialist media
    "https://www.moneycab.com/feed/",
    "https://investrends.ch/feed/",
    "https://www.bondguide.de/feed/",
    "https://www.dfpa.info/rss/",
    "https://www.dfpa.info/feed/",
    "https://e-fundresearch.com/rss",
    "https://e-fundresearch.com/feeds/news",
    "https://markteinblicke.de/feed/",
    "https://www.finanznachrichten.de/rss-alle-nachrichten",
    "https://www.cash.ch/rss/news",
    "https://www.payoff.ch/feed/",
    "https://www.payoff.ch/rss",
    "https://www.fondsexklusiv.de/feed/",
    "https://www.fondsexklusiv.at/feed/",
    "https://www.cash-online.de/feed/",
    "https://www.altii.de/feed/",
    "https://www.altii.de/rss/",
    "https://citywire.de/feed/",
    "https://www.private-banking-magazin.de/feed/",
    "https://www.fixed-income.org/feed/",
    "https://www.fixed-income.org/rss/",
    "https://www.finanzwelt.de/feed/",
    "https://www.procontra-online.de/feed/",
    "https://exxecnews.org/feed/",
    "https://www.boersen-kurier.at/feed/",
    "https://www.kreditwesen.de/feed/",
    "https://www.allnews.ch/rss",
    "https://www.swissfinanceai.ch/blog/rss.xml",
    "https://www.swissfinanceai.ch/feed/",
    "https://www.srf.ch/news/wirtschaft/rss/feed",
    "https://www.n-tv.de/wirtschaft/rss",
    "https://www.tagesanzeiger.ch/wirtschaft/rss.xml",
    "https://www.geldmeisterin.com/feed/",
    "https://www.gruenderkueche.de/feed/",
    "https://www.platow.de/feed/",
    "https://fondstrends.ch/feed/",
    "https://fondstrends.de/feed/",
    # Additional specialist
    "https://www.dpn-online.com/feed/",
    "https://www.versicherungsbote.de/feed/",
    "https://www.fundresearch.de/feed/",
]


# ╔══════════════════════════════════════════════════════════════╗
# ║  GOOGLE SEARCH QUERIES                                       ║
# ╚══════════════════════════════════════════════════════════════╝

GOOGLE_QUERIES = [
    # BARE NAMES (most important — also fetch page 2)
    '"Johannes Feist"',
    '"Michele Mattioda"',
    '"Louzia Savchenko"',
    '"MK Global Kapital"',
    '"Mikro Kapital"',
    # BRAND + CONTEXT
    '"Mikro Kapital" Mikrofinanz',
    '"Mikro Kapital Management"',
    '"MK Global" Mikrofinanz',
    '"MK Global" "Private Debt"',
    '"MK Global" "Private Credit"',
    '"MK Global" Impact',
    '"MK Global" Anleihe',
    '"MK Global" ALTERNATIVE Fonds',
    '"Mikro Kapital" ESG',
    # PEOPLE + CONTEXT
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
    # BROAD
    '"MK Global Kapital" OR "Mikro Kapital" 2026',
]

# Bare name queries that should also fetch Google page 2
PAGE2_QUERIES = ['"Johannes Feist"', '"MK Global Kapital"', '"Mikro Kapital"']

GOOGLE_NEWS_QUERIES = [
    '"MK Global Kapital"',
    '"Johannes Feist" Mikrofinanz',
    '"Mikro Kapital"',
    '"Louzia Savchenko"',
    '"Michele Mattioda"',
]

VALIDATION_PROMPT = """Du pruefst ob Suchergebnisse tatsaechlich MK Global Kapital, Mikro Kapital oder eine der folgenden Personen DIREKT erwaehnen (nicht nur in Sidebar-Links oder Werbung):
- Dr. Johannes Feist (CEO MK Global Kapital), Michele Mattioda, Louzia Savchenko, Vincenzo Trani, Thomas Heinig, Luca Pellegrini

WICHTIG: Es gibt andere Personen namens "Johannes Feist" (z.B. Edeka-Marktleiter in Gundelfingen). NUR Artikel ueber den MK Global Kapital / Mikro Kapital CEO sind relevant!

Pruefe fuer jeden Eintrag:
1. Wird MK Global Kapital / Mikro Kapital / eine MK-Person im Artikeltext selbst erwaehnt?
2. Geht es um Finanzen, Mikrofinanz, Impact Investing, Private Debt — NICHT um Supermaerkte, Edeka oder andere Branchen?
3. Ist es KEIN Sidebar-Link, keine Werbung, kein "Weitere Artikel"-Verweis?

AUSGABE: Nur die RELEVANTEN Artikel als JSON-Array:
[{"date":"YYYY-MM-DD","outlet":"Offizieller Medienname (z.B. Frankfurter Allgemeine Zeitung, nicht faz.net)","title":"Exakter Artikeltitel","country":"D/CH/A/DACH","type":"Online","tier":1 oder 2,"link":"URL"}]

TIER 1: FAZ, Handelsblatt, Boersen-Zeitung, NZZ, Finews, Institutional Money, DAS INVESTMENT, FONDS professionell, altii, Citywire, portfolio institutionell, Handelszeitung, Der Standard, Die Presse, WirtschaftsWoche, Manager Magazin, Capital, SZ, Boerse Online
TIER 2: Alle anderen

Keine Treffer? Antworte: []"""

DATA_FILE = Path(__file__).parent.parent / "data" / "clippings.json"


# ╔══════════════════════════════════════════════════════════════╗
# ║  UTILITY FUNCTIONS                                           ║
# ╚══════════════════════════════════════════════════════════════╝

def load_clippings():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_clippings(clips):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(clips, f, ensure_ascii=False, indent=2)

def strip_html(text):
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_module.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()

def normalize_url(url):
    """Normalize URL for deduplication."""
    url = url.strip().rstrip("/").lower()
    url = re.sub(r'[?&](utm_\w+|ref|source|fbclid|gclid|xtor|wt_mc)=[^&]*', '', url)
    url = re.sub(r'#.*$', '', url)
    url = url.rstrip("?&")
    return url

def extract_domain(url):
    """Extract clean domain from URL."""
    return urlparse(url).netloc.lower().replace("www.", "")

def normalize_outlet(source, link=""):
    """Convert domain/source to official outlet name."""
    domain = extract_domain(link) if link else source.lower().replace("www.", "")
    for key, name in OUTLET_NAMES.items():
        if key in domain:
            return name
    return source if source else domain

def is_blocked_domain(url):
    domain = extract_domain(url)
    return any(blocked in domain for blocked in BLOCKED_DOMAINS)

def guess_tier(outlet="", link=""):
    text = (outlet + " " + link).lower()
    return 1 if any(k in text for k in TIER1_KEYWORDS) else 2

def guess_country(outlet="", link=""):
    text = (outlet + " " + link).lower()
    if any(k in text for k in COUNTRY_CH):
        return "CH"
    if any(k in text for k in COUNTRY_AT):
        return "A"
    return "D"

def extract_date(text, url=""):
    """Extract date from multiple formats."""
    # DD.MM.YYYY
    m = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
    if m:
        d, mo, y = m.groups()
        if 2024 <= int(y) <= 2027:
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    # YYYY-MM-DD
    m = re.search(r'(20\d{2})-(\d{2})-(\d{2})', text)
    if m:
        return m.group(0)
    # YYYY/MM/DD in URLs
    m = re.search(r'(20\d{2})/(\d{2})/(\d{2})', url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # YYYY/MM in URLs (use first of month)
    m = re.search(r'(20\d{2})/(\d{2})/', url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    # "vor X Tagen/Stunden"
    m = re.search(r'vor (\d+) Tag', text)
    if m:
        from datetime import timedelta
        d = datetime.now() - timedelta(days=int(m.group(1)))
        return d.strftime("%Y-%m-%d")
    return ""

def is_mk_relevant(result):
    """Pre-filter: does the result mention MK keywords?"""
    text = f"{result.get('title','')} {result.get('snippet','')} {result.get('source','')}".lower()
    return any(kw in text for kw in MK_KEYWORDS)

def is_duplicate(article, existing):
    link = normalize_url(article.get("link", ""))
    title = article.get("title", "").lower().strip()
    outlet = article.get("outlet", "").lower().strip()
    for c in existing:
        cl = normalize_url(c.get("link", ""))
        ct = c.get("title", "").lower().strip()
        co = c.get("outlet", "").lower().strip()
        if link and cl and link == cl:
            return True
        if title and ct and len(title) > 15 and len(ct) > 15:
            # Same title regardless of outlet (cross-domain syndication)
            if title == ct:
                return True
            # One contains the other (same outlet)
            if outlet and co and outlet == co and (title in ct or ct in title):
                return True
    return False

def http_get(url, timeout=10, retries=2):
    """HTTP GET with retry logic."""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, timeout=timeout,
                headers={"User-Agent": "MK-Clipping-Agent/3.0"})
            return resp
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                raise e
    return None

def auto_classify_result(result):
    """Create a clipping from Google/RSS result without Claude."""
    raw_title = result.get("title", "")
    title = raw_title.split(" - ")[0].split(" | ")[0].strip()
    link = result.get("link", "")
    source = result.get("source", "")
    snippet = result.get("snippet", "")
    date = result.get("date") or extract_date(snippet, link)
    
    return {
        "title": title,
        "link": link,
        "outlet": normalize_outlet(source, link),
        "date": date,
        "tier": guess_tier(source, link),
        "country": guess_country(source, link),
        "type": "Online",
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║  RSS SCANNING                                                ║
# ╚══════════════════════════════════════════════════════════════╝

def scan_rss_feeds():
    """Scan all RSS feeds for MK-relevant articles."""
    print(f"Scanning {len(RSS_FEEDS)} RSS feeds...\n")
    results = []
    feeds_ok = 0
    feeds_fail = 0
    
    for feed_url in RSS_FEEDS:
        try:
            resp = http_get(feed_url, timeout=8, retries=1)
            if not resp or resp.status_code != 200:
                feeds_fail += 1
                continue
            
            feed = feedparser.parse(resp.content)
            if not feed.entries:
                feeds_fail += 1
                continue
            
            feeds_ok += 1
            feed_domain = extract_domain(feed_url)
            
            for entry in feed.entries[:40]:  # Check last 40 entries per feed
                title = strip_html(entry.get("title", ""))
                summary = strip_html(
                    entry.get("summary", "") or 
                    entry.get("description", "") or
                    entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""
                )
                link = entry.get("link", "")
                
                # Check relevance against title + summary (up to 500 chars)
                text = f"{title} {summary[:500]}".lower()
                if any(kw in text for kw in MK_KEYWORDS):
                    date = ""
                    for date_field in ["published_parsed", "updated_parsed"]:
                        if entry.get(date_field):
                            try:
                                dt = datetime(*entry[date_field][:6])
                                date = dt.strftime("%Y-%m-%d")
                                break
                            except:
                                pass
                    if not date:
                        date = extract_date(summary, link)
                    
                    results.append({
                        "title": title.split(" - ")[0].split(" | ")[0].strip(),
                        "link": link,
                        "snippet": summary[:300],
                        "source": feed_domain,
                        "date": date,
                    })
        except Exception:
            feeds_fail += 1
            continue
    
    print(f"  RSS: {feeds_ok}/{len(RSS_FEEDS)} feeds OK, {len(results)} MK-relevant entries\n")
    return results


# ╔══════════════════════════════════════════════════════════════╗
# ║  GOOGLE SEARCH                                               ║
# ╚══════════════════════════════════════════════════════════════╝

def google_search(query, api_key, cx, sort_by_date=False, start=1):
    """Run a single Google Custom Search query."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": 10,
        "lr": "lang_de",
        "dateRestrict": "m9",  # 9 months (wider net)
        "start": start,
    }
    if sort_by_date:
        params["sort"] = "date"
    
    try:
        resp = http_get(url, timeout=15, retries=2)
        if not resp:
            return []
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


# ╔══════════════════════════════════════════════════════════════╗
# ║  CLAUDE VALIDATION                                           ║
# ╚══════════════════════════════════════════════════════════════╝

def validate_with_claude(client, results):
    """Use Claude to validate and structure results into clippings."""
    if not results:
        return []
    
    text_results = []
    for i, r in enumerate(results):
        text_results.append(
            f"{i+1}. Quelle: {r.get('source','')}\n"
            f"   Titel: {r.get('title','')}\n"
            f"   Snippet: {r.get('snippet','')[:200]}\n"
            f"   URL: {r.get('link','')}"
        )
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=VALIDATION_PROMPT,
            messages=[{
                "role": "user",
                "content": "Pruefe diese Suchergebnisse und gib NUR die relevanten MK Global Kapital Artikel als JSON zurueck:\n\n" + "\n\n".join(text_results)
            }],
        )
        
        texts = [block.text for block in response.content if hasattr(block, "text") and block.text]
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
        print(f"    Claude error: {e}")
        return None  # None = Claude failed, [] = no results


# ╔══════════════════════════════════════════════════════════════╗
# ║  MAIN SEARCH ORCHESTRATION                                   ║
# ╚══════════════════════════════════════════════════════════════╝

def run_search():
    google_key = os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_CX")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not google_key or not google_cx:
        print("WARNING: No Google keys, using Anthropic fallback")
        return run_anthropic_fallback()
    
    existing = load_clippings()
    existing_urls = {normalize_url(c.get("link","")) for c in existing if c.get("link")}
    new_articles = []
    all_results = []
    rate_limited = False
    stats = {"rss_ok": 0, "rss_fail": 0, "google_queries": 0, "google_hits": 0, 
             "rss_relevant": 0, "validated": 0, "new": 0}
    
    print(f"{'='*60}")
    print(f"MK Global Kapital — DACH Clipping Agent v3.0")
    print(f"{'='*60}")
    print(f"Existing clippings: {len(existing)}\n")
    
    # ── STEP 0: RSS Feeds (free, unlimited) ──
    rss_results = scan_rss_feeds()
    for r in rss_results:
        if not is_blocked_domain(r.get("link", "")):
            all_results.append(r)
    stats["rss_relevant"] = len(rss_results)
    
    # ── STEP 1a: Google Web Search ──
    print(f"Running {len(GOOGLE_QUERIES)} Google web queries...\n")
    for i, query in enumerate(GOOGLE_QUERIES):
        if rate_limited:
            break
        print(f"[Google {i+1}/{len(GOOGLE_QUERIES)}] {query[:60]}...")
        results = google_search(query, google_key, google_cx)
        
        if results is None:
            rate_limited = True
            break
        
        stats["google_queries"] += 1
        relevant = [r for r in results if is_mk_relevant(r)]
        stats["google_hits"] += len(relevant)
        print(f"  -> {len(results)} results, {len(relevant)} MK-relevant")
        all_results.extend(relevant)
        
        # Fetch page 2 for bare name queries (doubles coverage)
        if query in PAGE2_QUERIES and not rate_limited and len(results) >= 8:
            results2 = google_search(query, google_key, google_cx, start=11)
            if results2 is None:
                rate_limited = True
            elif results2:
                stats["google_queries"] += 1
                relevant2 = [r for r in results2 if is_mk_relevant(r)]
                stats["google_hits"] += len(relevant2)
                if relevant2:
                    print(f"  -> page 2: {len(relevant2)} more MK-relevant")
                    all_results.extend(relevant2)
        
        time.sleep(1)
    
    # ── STEP 1b: Google News Search ──
    if not rate_limited:
        print(f"\nRunning {len(GOOGLE_NEWS_QUERIES)} Google News queries...\n")
        for i, query in enumerate(GOOGLE_NEWS_QUERIES):
            if rate_limited:
                break
            print(f"[News {i+1}/{len(GOOGLE_NEWS_QUERIES)}] {query[:60]}...")
            results = google_search(query, google_key, google_cx, sort_by_date=True)
            
            if results is None:
                rate_limited = True
                break
            
            stats["google_queries"] += 1
            relevant = [r for r in results if is_mk_relevant(r)]
            stats["google_hits"] += len(relevant)
            print(f"  -> {len(results)} results, {len(relevant)} MK-relevant")
            all_results.extend(relevant)
            time.sleep(1)
    
    # ── STEP 2: Deduplicate all results ──
    seen_urls = set()
    unique_results = []
    for r in all_results:
        url = normalize_url(r.get("link", ""))
        if url and url not in seen_urls and url not in existing_urls:
            seen_urls.add(url)
            unique_results.append(r)
    
    print(f"\n{len(unique_results)} unique NEW results to validate")
    
    if not unique_results:
        print("No new results to process")
        print_stats(stats)
        return []
    
    # ── STEP 3: Validate with Claude (or auto-classify) ──
    claude_available = bool(anthropic_key)
    client = None
    if claude_available:
        try:
            client = anthropic.Anthropic(api_key=anthropic_key)
        except:
            claude_available = False
    
    validated = []
    if claude_available:
        print(f"\nValidating with Claude...\n")
        batch_size = 15
        for i in range(0, len(unique_results), batch_size):
            batch = unique_results[i:i+batch_size]
            print(f"[Claude] Batch {i//batch_size+1} ({len(batch)} results)...")
            articles = validate_with_claude(client, batch)
            
            if articles is None:
                print("  Claude failed, auto-classifying batch...")
                for r in batch:
                    validated.append(auto_classify_result(r))
            elif articles:
                validated.extend(articles)
                print(f"  -> {len(articles)} valid")
            else:
                print(f"  -> 0 valid")
            time.sleep(2)
    else:
        print("\nClaude unavailable. Auto-classifying all results...\n")
        for r in unique_results:
            validated.append(auto_classify_result(r))
    
    stats["validated"] = len(validated)
    
    # ── STEP 4: Final dedup, enrich, and save ──
    for a in validated:
        a["tier"] = a.get("tier") or guess_tier(a.get("outlet",""), a.get("link",""))
        a["country"] = a.get("country") or guess_country(a.get("outlet",""), a.get("link",""))
        a["type"] = a.get("type") or "Online"
        a["outlet"] = normalize_outlet(a.get("outlet",""), a.get("link",""))
        if not a.get("date"):
            a["date"] = extract_date("", a.get("link",""))
        
        if not is_duplicate(a, existing) and not is_duplicate(a, new_articles):
            a["added_at"] = datetime.now().isoformat()
            a["source"] = "auto" if claude_available else "auto-noclaudecheck"
            a["id"] = f"g-{int(datetime.now().timestamp())}-{len(new_articles)}"
            new_articles.append(a)
    
    stats["new"] = len(new_articles)
    
    if new_articles:
        all_clips = existing + new_articles
        all_clips.sort(key=lambda x: x.get("date", ""), reverse=True)
        save_clippings(all_clips)
        print(f"\n{'='*50}")
        print(f"NEW: {len(new_articles)} articles added")
        print(f"TOTAL: {len(all_clips)} clippings")
        print(f"{'='*50}")
        for a in new_articles:
            print(f"  + {a.get('date','')} | {a.get('outlet','')} | {a.get('title','')[:55]}")
    else:
        print(f"\nNo new articles (existing: {len(existing)})")
    
    print_stats(stats)
    return new_articles


def print_stats(stats):
    """Print performance summary."""
    print(f"\n{'─'*40}")
    print(f"PERFORMANCE REPORT")
    print(f"  RSS relevant entries: {stats.get('rss_relevant',0)}")
    print(f"  Google queries used:  {stats.get('google_queries',0)}")
    print(f"  Google MK hits:       {stats.get('google_hits',0)}")
    print(f"  Validated by Claude:  {stats.get('validated',0)}")
    print(f"  New articles added:   {stats.get('new',0)}")
    print(f"{'─'*40}")


def run_anthropic_fallback():
    """Fallback if Google keys not set."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("ERROR: No API keys available")
        return []
    
    # Still scan RSS even without Google
    rss_results = scan_rss_feeds()
    
    client = anthropic.Anthropic(api_key=anthropic_key)
    existing = load_clippings()
    new_articles = []
    
    # Auto-classify RSS results
    for r in rss_results:
        if not is_blocked_domain(r.get("link", "")):
            a = auto_classify_result(r)
            if not is_duplicate(a, existing) and not is_duplicate(a, new_articles):
                a["added_at"] = datetime.now().isoformat()
                a["source"] = "auto-rss"
                a["id"] = f"r-{int(datetime.now().timestamp())}-{len(new_articles)}"
                new_articles.append(a)
    
    fallback_queries = [
        '"MK Global Kapital"', '"Mikro Kapital" Mikrofinanz',
        '"Johannes Feist" Mikrofinanz OR "MK Global"',
        '"Johannes Feist" "Private Credit" OR Gastkommentar',
        '"Michele Mattioda" "MK Global"',
        '"Louzia Savchenko" "MK Global" OR Tokenisierung',
    ]
    
    system = """Finde ALLE deutschsprachigen Medienartikel zu MK Global Kapital / Mikro Kapital.
Antworte NUR mit JSON-Array: [{"date":"YYYY-MM-DD","outlet":"Name","title":"Titel","country":"D/CH/A","type":"Online","tier":1/2,"link":"URL"}]
Keine Treffer? []"""
    
    for i, q in enumerate(fallback_queries):
        print(f"[Fallback {i+1}/{len(fallback_queries)}] {q}...")
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514", max_tokens=4000, system=system,
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
            for match in re.findall(r'\[[\s\S]*?\]', "\n".join(texts)):
                try:
                    for a in json.loads(match):
                        if isinstance(a, dict) and a.get("title"):
                            a["tier"] = a.get("tier") or guess_tier(a.get("outlet",""), a.get("link",""))
                            a["country"] = a.get("country") or guess_country(a.get("outlet",""), a.get("link",""))
                            a["outlet"] = normalize_outlet(a.get("outlet",""), a.get("link",""))
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
