"""
MK Global Kapital - DACH Clipping Agent
Uses Google Custom Search API for finding articles, Claude for validation.
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
import requests
import anthropic

# === GOOGLE SEARCH QUERIES ===
# Each query counts as 1 of 100 free daily searches
GOOGLE_QUERIES = [
    # Core brand (most important)
    '"MK Global Kapital"',
    '"Mikro Kapital" Mikrofinanz',
    '"Mikro Kapital Management"',
    
    # People with company context
    '"Johannes Feist" "MK Global"',
    '"Johannes Feist" "Mikro Kapital"',
    '"Johannes Feist" Mikrofinanz',
    '"Johannes Feist" "Private Credit"',
    '"Johannes Feist" "Private Debt"',
    '"Johannes Feist" Gastkommentar',
    '"Johannes Feist" "Emerging Markets"',
    '"Michele Mattioda" Mikrofinanz',
    '"Michele Mattioda" "MK Global"',
    '"Louzia Savchenko" "MK Global"',
    '"Louzia Savchenko" Tokenisierung',
    '"Louzia Savchenko" Mikrofinanz',
    '"Vincenzo Trani" "Mikro Kapital"',
    '"Thomas Heinig" "Mikro Kapital"',
    
    # Topic combinations
    '"MK Global" Anleihe',
    '"MK Global" Impact Investing',
    '"Mikro Kapital" ESG',
    '"MK Global" ALTERNATIVE Fonds',
    
    # Broad catches
    '"MK Global Kapital" OR "Mikro Kapital" 2026',
    '"Johannes Feist" CEO Mikrofinanz 2026',
]

TIER1_KEYWORDS = [
    "faz", "frankfurter allgemeine", "handelsblatt",
    "boersen-zeitung", "nzz", "neue zuercher",
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

# Keywords that MUST appear in article text to be a valid MK clipping
MK_KEYWORDS = [
    "mk global kapital", "mikro kapital", "johannes feist",
    "michele mattioda", "louzia savchenko", "vincenzo trani",
    "thomas heinig", "luca pellegrini",
    "mikrokapital", "mk global",
]

VALIDATION_PROMPT = """Du pruefst ob Artikel tatsaechlich MK Global Kapital, Mikro Kapital oder eine der folgenden Personen DIREKT erwaehnen (nicht nur in Sidebar-Links oder Werbung):
- Johannes Feist, Michele Mattioda, Louzia Savchenko, Vincenzo Trani, Thomas Heinig, Luca Pellegrini

Fuer jeden Artikel: Pruefe ob er RELEVANT ist (MK/Person wird im Artikeltext selbst erwaehnt, nicht nur als Link auf der Seite).

EINGABE: Liste von Google-Suchergebnissen mit Titel, Snippet und URL.
AUSGABE: Nur die RELEVANTEN Artikel als JSON-Array:
[{"date":"YYYY-MM-DD","outlet":"Medienname","title":"Artikeltitel","country":"D/CH/A/DACH","type":"Online","tier":1 oder 2,"link":"URL"}]

REGELN:
- NUR Artikel bei denen MK/Mikro Kapital/eine MK-Person im Snippet oder Titel vorkommt
- KEINE Artikel die nur zufaellig auf derselben Seite verlinkt sind
- Tier 1: FAZ, Handelsblatt, Boersen-Zeitung, NZZ, Finews, Institutional Money, DAS INVESTMENT, FONDS professionell, altii, Citywire, portfolio institutionell, Handelszeitung, Der Standard
- Tier 2: Alle anderen
- Datum aus Snippet/Kontext schaetzen, falls nicht klar: leer lassen
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


def is_duplicate(article, existing):
    link = article.get("link", "").strip().rstrip("/").lower()
    title = article.get("title", "").lower().strip()
    outlet = article.get("outlet", "").lower().strip()
    for c in existing:
        cl = c.get("link", "").strip().rstrip("/").lower()
        ct = c.get("title", "").lower().strip()
        co = c.get("outlet", "").lower().strip()
        if link and cl and link == cl:
            return True
        if title and ct and outlet and co:
            if title == ct and outlet == co:
                return True
            if outlet == co and len(title) > 15 and (title in ct or ct in title):
                return True
    return False


def guess_tier(outlet="", link=""):
    text = (outlet + " " + link).lower()
    return 1 if any(k in text for k in TIER1_KEYWORDS) else 2


def guess_country(outlet="", link=""):
    text = (outlet + " " + link).lower()
    if any(k in text for k in [".ch", "finews", "payoff", "nzz", "investrends", "handelszeitung", "moneycab", "cash.ch", "allnews.ch"]):
        return "CH"
    if any(k in text for k in [".at", "derstandard", "diepresse", "kurier.at", "boersen-kurier", "fondsexklusiv.at"]):
        return "A"
    return "D"


def google_search(query, api_key, cx):
    """Run a single Google Custom Search query. Returns list of results."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": 10,
        "lr": "lang_de",
        "dateRestrict": "m6",  # last 6 months
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 429:
            print("    RATE LIMIT - stopping Google searches")
            return None  # Signal to stop
        if resp.status_code != 200:
            print(f"    Google API error {resp.status_code}: {resp.text[:100]}")
            return []
        data = resp.json()
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": item.get("displayLink", ""),
            })
        return results
    except Exception as e:
        print(f"    Google error: {e}")
        return []


def is_mk_relevant(result):
    """Quick pre-filter: does the result mention MK keywords?"""
    text = f"{result.get('title','')} {result.get('snippet','')} {result.get('source','')}".lower()
    return any(kw in text for kw in MK_KEYWORDS)


def validate_with_claude(client, results):
    """Use Claude to validate and structure Google results into clippings."""
    if not results:
        return []
    
    # Format results for Claude
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
        return []


def run_search():
    google_key = os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_CX")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not google_key or not google_cx:
        print("WARNING: GOOGLE_API_KEY or GOOGLE_CX not set, falling back to Anthropic-only search")
        return run_anthropic_fallback()
    
    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return []
    
    client = anthropic.Anthropic(api_key=anthropic_key)
    existing = load_clippings()
    new_articles = []
    all_google_results = []
    
    print(f"Loaded {len(existing)} existing clippings")
    print(f"Running {len(GOOGLE_QUERIES)} Google searches...\n")
    
    # Step 1: Google searches
    for i, query in enumerate(GOOGLE_QUERIES):
        print(f"[Google {i+1}/{len(GOOGLE_QUERIES)}] {query[:60]}...")
        results = google_search(query, google_key, google_cx)
        
        if results is None:  # Rate limit
            print("  Stopping Google searches due to rate limit")
            break
        
        # Pre-filter for MK relevance
        relevant = [r for r in results if is_mk_relevant(r)]
        all_results = len(results)
        
        if relevant:
            all_google_results.extend(relevant)
            print(f"  -> {all_results} results, {len(relevant)} MK-relevant")
        else:
            print(f"  -> {all_results} results, 0 MK-relevant")
        
        time.sleep(1)
    
    # Deduplicate Google results by URL
    seen_urls = set()
    unique_results = []
    for r in all_google_results:
        url = r.get("link", "").strip().rstrip("/").lower()
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(r)
    
    print(f"\n{len(unique_results)} unique MK-relevant Google results found")
    
    if not unique_results:
        print("No new results to validate")
        return []
    
    # Step 2: Validate with Claude in batches of 15
    print(f"\nValidating with Claude...\n")
    validated = []
    batch_size = 15
    for i in range(0, len(unique_results), batch_size):
        batch = unique_results[i:i+batch_size]
        print(f"[Claude] Validating batch {i//batch_size + 1} ({len(batch)} results)...")
        articles = validate_with_claude(client, batch)
        if articles:
            validated.extend(articles)
            print(f"  -> {len(articles)} valid articles")
        else:
            print(f"  -> 0 valid")
        time.sleep(2)
    
    # Step 3: Deduplicate against existing
    for a in validated:
        a["tier"] = a.get("tier") or guess_tier(a.get("outlet", ""), a.get("link", ""))
        a["country"] = a.get("country") or guess_country(a.get("outlet", ""), a.get("link", ""))
        a["type"] = a.get("type") or "Online"
        if not is_duplicate(a, existing) and not is_duplicate(a, new_articles):
            a["added_at"] = datetime.now().isoformat()
            a["source"] = "auto-google"
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
