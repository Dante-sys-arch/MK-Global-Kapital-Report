"""
MK Global Kapital - DACH Clipping Agent
Ultra-broad search strategy across web, news, and specific outlets.
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
import anthropic

# 40+ search queries for maximum coverage
SEARCHES = [
    # === CORE BRAND (Web + News) ===
    '"MK Global Kapital"',
    '"Mikro Kapital" Mikrofinanz',
    '"Mikro Kapital Management"',
    '"MK Global Kapital" News',
    '"Mikro Kapital" News deutsch',
    
    # === KEY PEOPLE ===
    '"Johannes Feist" Mikrofinanz',
    '"Johannes Feist" "MK Global"',
    '"Johannes Feist" "Mikro Kapital"',
    '"Johannes Feist" CEO Mikrofinanz Interview',
    '"Michele Mattioda" MK Global',
    '"Michele Mattioda" Mikrofinanz',
    
    # === TOPIC COMBINATIONS ===
    '"Mikro Kapital" Anleihe',
    '"Mikro Kapital" "Private Debt"',
    '"MK Global" Impact Investing',
    '"Mikro Kapital" ESG nachhaltig',
    '"Mikro Kapital" Emerging Markets',
    '"MK Global" OR "Mikro Kapital" KMU Kredit',
    '"Mikro Kapital" Fonds ALTERNATIVE',
    '"MK Global" Seidenstrasse OR "Silk Road"',
    '"Mikro Kapital" Leasing Zentralasien',
    
    # === GOOGLE NEWS SPECIFIC ===
    '"MK Global Kapital" nach:2025-01-01',
    '"Mikro Kapital" Mikrofinanz nach:2025-06-01',
    '"Johannes Feist" Mikrofinanz nach:2025-01-01',
    'Mikrofinanz "Mikro Kapital" Nachrichten 2026',
    
    # === PER-OUTLET SEARCHES (Tier 1) ===
    '"Mikro Kapital" OR "MK Global" OR "Johannes Feist" site:faz.net',
    '"Mikro Kapital" OR "MK Global" OR "Johannes Feist" site:handelsblatt.com',
    '"Mikro Kapital" OR "MK Global" OR "Johannes Feist" site:finews.ch',
    '"Mikro Kapital" OR "MK Global" OR "Johannes Feist" site:nzz.ch',
    '"Mikro Kapital" OR "MK Global" site:institutional-money.com',
    '"Mikro Kapital" OR "MK Global" site:dasinvestment.com',
    '"Mikro Kapital" OR "MK Global" site:fondsprofessionell.de',
    '"Mikro Kapital" OR "MK Global" site:altii.de',
    '"Mikro Kapital" OR "MK Global" site:citywire.de',
    '"Mikro Kapital" OR "MK Global" site:portfolio-institutionell.de',
    '"Mikro Kapital" OR "MK Global" site:handelszeitung.ch',
    
    # === PER-OUTLET SEARCHES (Tier 2) ===
    '"Mikro Kapital" OR "MK Global" OR "Johannes Feist" site:moneycab.com',
    '"Mikro Kapital" OR "MK Global" OR "Johannes Feist" site:investrends.ch',
    '"Mikro Kapital" OR "MK Global" site:bondguide.de',
    '"Mikro Kapital" OR "MK Global" site:dfpa.info',
    '"Mikro Kapital" OR "MK Global" site:e-fundresearch.com',
    '"Mikro Kapital" OR "MK Global" site:markteinblicke.de',
    '"Mikro Kapital" OR "MK Global" site:finanznachrichten.de',
    '"Mikro Kapital" OR "MK Global" site:cash.ch',
    '"Mikro Kapital" OR "MK Global" site:payoff.ch',
    '"Mikro Kapital" OR "MK Global" site:fondsexklusiv.de',
    '"Mikro Kapital" OR "MK Global" site:boersen-zeitung.de',
    '"Mikro Kapital" OR "MK Global" site:geldmeisterin.com',
    '"Mikro Kapital" OR "MK Global" site:exxecnews.org',
    '"Mikro Kapital" OR "MK Global" site:boersen-kurier.at',
    '"Mikro Kapital" OR "MK Global" site:kreditwesen.de',
    '"Mikro Kapital" OR "MK Global" site:gruenderkueche.de',
    
    # === BROAD THEMATIC ===
    'Mikrofinanzfonds Deutschland Schweiz 2026',
    'Mikrofinanz Anleihe Impact "Private Debt" DACH 2026',
    '"Mikro Kapital" OR "Mikrokapital" Presse OR Pressemitteilung',
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

SYSTEM_PROMPT = """Du bist ein extrem gruendlicher Medienrecherche-Assistent fuer MK Global Kapital (ehemals Mikro Kapital Management S.A.).

DEINE AUFGABE: Durchsuche das Web und Google News so breit wie moeglich nach ALLEN deutschsprachigen Medienartikeln aus dem DACH-Raum, die folgende Begriffe erwaehnen:
- MK Global Kapital
- Mikro Kapital (Management)
- Dr. Johannes Feist (CEO, im Kontext Finanzen/Mikrofinanz)
- Michele Mattioda (im Kontext MK Global/Mikrofinanz)

SUCHSTRATEGIE:
- Suche in Nachrichtenportalen, Fachmedien, Blogs, Pressemitteilungen, Interviews, Gastbeitraege
- Suche auch in Google News
- Beachte sowohl aktuelle als auch aeltere Artikel (ab 2025)
- Auch kurze Erwaehnungen und Zitate zaehlen
- Wenn ein Artikel MK Global Kapital oder Mikro Kapital auch nur am Rande erwaehnt, nimm ihn auf
- Lieber einen Artikel zu viel als einen zu wenig!

ANTWORTFORMAT: Ausschliesslich ein JSON-Array, kein anderer Text.
[{"date":"YYYY-MM-DD","outlet":"Exakter Medienname","title":"Exakter Artikeltitel","country":"D/CH/A/DACH","type":"Online/Print","tier":1 oder 2,"link":"Vollstaendige URL"}]

TIER-ZUORDNUNG:
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
            if outlet == co and len(title) > 15 and (title in ct or ct in title):
                return True
    return False


def guess_tier(outlet="", link=""):
    text = (outlet + " " + link).lower()
    return 1 if any(k in text for k in TIER1) else 2


def guess_country(outlet="", link=""):
    text = (outlet + " " + link).lower()
    if any(k in text for k in [".ch", "finews", "payoff", "nzz", "investrends", "handelszeitung", "moneycab", "cash.ch"]):
        return "CH"
    if any(k in text for k in [".at", "kurier"]):
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
    print(f"Running {len(SEARCHES)} searches (ultra-broad)...\n")

    for i, query in enumerate(SEARCHES):
        print(f"[{i+1}/{len(SEARCHES)}] {query[:70]}...")
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Durchsuche das Web und Google News extrem gruendlich nach: {query}\n\n"
                        f"Finde ALLE deutschsprachigen Medienartikel die MK Global Kapital, Mikro Kapital, "
                        f"Johannes Feist oder Michele Mattioda erwaehnen. Suche breit: Nachrichtenportale, "
                        f"Fachmedien, Blogs, Pressemitteilungen, Gastbeitraege, Interviews. "
                        f"Gib das Ergebnis als JSON-Array zurueck."
                    )
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
