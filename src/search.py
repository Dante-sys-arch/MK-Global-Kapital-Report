"""
MK Global Kapital — DACH Clipping Agent
Searches for German-language media coverage using Anthropic API with web search.
"""
import json
import os
import time
from datetime import datetime, date
from pathlib import Path
import anthropic

# --- Config ---
SEARCHES = [
    '"MK Global Kapital" 2026',
    '"Mikro Kapital" Mikrofinanz DACH 2026',
    '"Michele Mattioda" "MK Global Kapital"',
    '"Johannes Feist" Mikrofinanz 2026',
    '"Mikro Kapital" "Private Debt" KMU',
    '"MK Global Kapital" Anleihe Mikrofinanz',
]

TIER1_KEYWORDS = [
    "faz", "frankfurter allgemeine", "handelsblatt", "börsen-zeitung", "boersen-zeitung",
    "nzz", "neue zürcher", "finews", "institutional money", "institutional-money",
    "das investment", "dasinvestment", "fonds professionell", "fondsprofessionell",
    "altii", "citywire", "portfolio institutionell", "portfolio-institutionell",
]

SYSTEM_PROMPT = """Du bist ein Medienanalyse-Assistent für MK Global Kapital (ehemals Mikro Kapital Management).
Deine Aufgabe: Finde deutschsprachige Medienartikel aus dem DACH-Raum, die MK Global Kapital, Mikro Kapital,
Michele Mattioda oder Johannes Feist im Kontext von Mikrofinanz, Private Debt oder KMU-Finanzierung erwähnen.

Antworte AUSSCHLIESSLICH mit einem JSON-Array. Kein anderer Text.

Format:
[
  {
    "date": "YYYY-MM-DD",
    "outlet": "Name des Mediums",
    "title": "Exakter Artikeltitel",
    "country": "D oder CH oder A oder DACH",
    "type": "Online oder Print",
    "tier": 1 oder 2,
    "link": "URL"
  }
]

Tier 1: FAZ, Handelsblatt, Börsen-Zeitung, NZZ, Finews, Institutional Money, DAS INVESTMENT,
FONDS professionell, altii, Citywire, portfolio institutionell
Tier 2: Alle anderen deutschsprachigen Medien

Keine relevanten Treffer? Antworte: []"""

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
    for c in existing:
        if article.get("link") and c.get("link") and article["link"] == c["link"]:
            return True
        if (article.get("title", "").lower().strip() == c.get("title", "").lower().strip()
                and article.get("outlet", "").lower() == c.get("outlet", "").lower()
                and article.get("title")):
            return True
    return False


def guess_tier(outlet="", link=""):
    text = f"{outlet} {link}".lower()
    return 1 if any(k in text for k in TIER1_KEYWORDS) else 2


def guess_country(outlet="", link=""):
    text = f"{outlet} {link}".lower()
    if any(k in text for k in [".ch", "finews", "payoff", "nzz", "investrends", "handelszeitung"]):
        return "CH"
    if any(k in text for k in [".at", "kurier", "börsen-kurier"]):
        return "A"
    return "D"


def extract_articles(response):
    """Extract JSON array of articles from Anthropic API response."""
    texts = []
    for block in response.content:
        if hasattr(block, "text") and block.text:
            texts.append(block.text)
        if hasattr(block, "content") and isinstance(block.content, list):
            for sub in block.content:
                if hasattr(sub, "text") and sub.text:
                    texts.append(sub.text)
    
    all_text = "\n".join(texts)
    
    # Find JSON arrays
    import re
    matches = re.findall(r'\[[\s\S]*?\]', all_text)
    for match in matches:
        try:
            parsed = json.loads(match)
            if isinstance(parsed, list):
                return [a for a in parsed if isinstance(a, dict) and a.get("title")]
        except json.JSONDecodeError:
            continue
    
    # Try the greedy match
    matches = re.findall(r'\[[\s\S]*\]', all_text)
    for match in matches:
        try:
            parsed = json.loads(match)
            if isinstance(parsed, list):
                return [a for a in parsed if isinstance(a, dict) and a.get("title")]
        except json.JSONDecodeError:
            continue
    
    return []


def run_search():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return []
    
    client = anthropic.Anthropic(api_key=api_key)
    existing = load_clippings()
    new_articles = []
    
    print(f"Loaded {len(existing)} existing clippings")
    print(f"Running {len(SEARCHES)} searches...\n")
    
    for i, query in enumerate(SEARCHES):
        print(f"[{i+1}/{len(SEARCHES)}] Searching: {query}")
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"Suche im Web nach deutschsprachigen Medienartikeln zu: {query}\nGib die Ergebnisse als JSON-Array zurück."
                }],
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
            )
            
            block_types = [b.type for b in response.content]
            print(f"  Response: {len(response.content)} blocks ({', '.join(block_types)}), stop: {response.stop_reason}")
            
            articles = extract_articles(response)
            
            added = 0
            for a in articles:
                a["tier"] = a.get("tier") or guess_tier(a.get("outlet", ""), a.get("link", ""))
                a["country"] = a.get("country") or guess_country(a.get("outlet", ""), a.get("link", ""))
                a["type"] = a.get("type") or "Online"
                
                if not is_duplicate(a, existing) and not is_duplicate(a, new_articles):
                    a["added_at"] = datetime.now().isoformat()
                    a["source"] = "auto"
                    new_articles.append(a)
                    added += 1
            
            print(f"  Found {len(articles)} articles, {added} new")
            
        except Exception as e:
            print(f"  ERROR: {e}")
        
        time.sleep(2)
    
    if new_articles:
        all_clips = existing + new_articles
        all_clips.sort(key=lambda x: x.get("date", ""), reverse=True)
        save_clippings(all_clips)
        print(f"\nSaved {len(new_articles)} new articles (total: {len(all_clips)})")
    else:
        print("\nNo new articles found")
    
    return new_articles


if __name__ == "__main__":
    new = run_search()
    print(f"\nDone. {len(new)} new clippings added.")
