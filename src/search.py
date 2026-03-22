"""
MK Global Kapital - DACH Clipping Agent
Broad, thorough search for German-language media coverage.
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
import anthropic

SEARCHES = [
    # Core brand
    '"MK Global Kapital"',
    '"Mikro Kapital" Mikrofinanz',
    '"Mikro Kapital Management"',
    # Key people
    '"Johannes Feist" Mikrofinanz OR "MK Global" OR "Mikro Kapital"',
    '"Michele Mattioda" MK OR Mikrofinanz OR Mikro',
    # Topic combos
    '"Mikro Kapital" Anleihe OR Bond OR Fonds',
    '"MK Global Kapital" OR "Mikro Kapital" Private Debt KMU',
    '"Mikro Kapital" Impact OR ESG OR nachhaltig',
    '"Mikro Kapital" OR "MK Global" Emerging Markets OR Schwellenlaender',
    # Per-outlet searches (critical for completeness)
    '"Mikro Kapital" OR "MK Global" site:handelsblatt.com OR site:faz.net',
    '"Mikro Kapital" OR "MK Global" site:finews.ch OR site:nzz.ch',
    '"Mikro Kapital" OR "MK Global" site:institutional-money.com OR site:dasinvestment.com',
    '"Mikro Kapital" OR "MK Global" site:fondsprofessionell.de OR site:citywire.de',
    '"Mikro Kapital" OR "MK Global" site:moneycab.com OR site:cash.ch',
    '"Mikro Kapital" OR "MK Global" site:investrends.ch OR site:payoff.ch',
    '"Mikro Kapital" OR "MK Global" site:bondguide.de OR site:altii.de',
    '"Mikro Kapital" OR "MK Global" site:dfpa.info OR site:e-fundresearch.com',
    '"Mikro Kapital" OR "MK Global" site:markteinblicke.de OR site:finanznachrichten.de',
    '"Johannes Feist" OR "MK Global" site:fondsprofessionell.de OR site:portfolio-institutionell.de',
    '"Mikro Kapital" OR "MK Global" site:boersen-zeitung.de OR site:fondsexklusiv.de',
    # Broader thematic
    'Mikrofinanz DACH Anleihe 2026 Feist OR "Mikro Kapital"',
    '"MK Global" OR "Mikro Kapital" Kreditwesen OR geldmeisterin OR Handelszeitung',
    '"MK Global" OR "Mikro Kapital" exxecnews OR gruenderkueche OR "Boersen-Kurier"',
]

TIER1 = [
    "faz", "frankfurter allgemeine", "handelsblatt",
    "boersen-zeitung", "nzz", "neue zuercher",
    "finews", "institutional money", "institutional-money",
    "das investment", "dasinvestment",
    "fonds professionell", "fondsprofessionell",
    "altii", "citywire",
    "portfolio institutionell", "portfolio-institutionell",
    "handelszeitung",
]

SYSTEM_PROMPT = """Du bist ein gruendlicher Medienanalyse-Assistent fuer MK Global Kapital (ehemals Mikro Kapital Management S.A.).

AUFGABE: Finde ALLE deutschsprachigen Medienartikel aus dem DACH-Raum, die eines der folgenden erwaehnen:
- MK Global Kapital
- Mikro Kapital (Management)
- Dr. Johannes Feist (im Kontext Mikrofinanz/Finance)
- Michele Mattioda (im Kontext MK Global/Mikrofinanz)

Sei SEHR GRUENDLICH. Auch kurze Erwaehnungen, Gastbeitraege, Interviews, Pressemitteilungen und Kommentare zaehlen.

ANTWORTFORMAT: Ausschliesslich ein JSON-Array, kein anderer Text.
[{"date":"YYYY-MM-DD","outlet":"Medienname","title":"Artikeltitel","country":"D/CH/A/DACH","type":"Online/Print","tier":1 oder 2,"link":"URL"}]

Tier 1: FAZ, Handelsblatt, Boersen-Zeitung, NZZ, Finews, Institutional Money, DAS INVESTMENT, FONDS professionell, altii, Citywire, portfolio institutionell, Handelszeitung
Tier 2: Alle anderen

Keine Treffer? Antworte: []"""

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
            if outlet == co and (title in ct or ct in title):
                return True
    return False


def guess_tier(outlet="", link=""):
    text = (outlet + " " + link).lower()
    return 1 if any(k in text for k in TIER1) else 2


def guess_country(outlet="", link=""):
    text = (outlet + " " + link).lower()
    ch = [".ch", "finews", "payoff", "nzz", "investrends", "handelszeitung", "moneycab", "cash.ch"]
    at = [".at", "kurier"]
    if any(k in text for k in ch):
        return "CH"
    if any(k in text for k in at):
        return "A"
    return "D"


def extract_articles(response):
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
    print(f"Running {len(SEARCHES)} broad searches...\n")

    for i, query in enumerate(SEARCHES):
        print(f"[{i+1}/{len(SEARCHES)}] {query[:70]}...")
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"Durchsuche das Web gruendlich nach: {query}\n\nFinde ALLE deutschsprachigen Medienartikel die MK Global Kapital, Mikro Kapital, Johannes Feist oder Michele Mattioda erwaehnen. Gib das Ergebnis als JSON-Array zurueck."
                }],
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
            )
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
            if len(articles) > 0:
                print(f"  -> {len(articles)} found, {added} new")
            else:
                print(f"  -> no results")
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(2)

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


if __name__ == "__main__":
    new = run_search()
    print(f"\nDone. {len(new)} new clippings added.")
