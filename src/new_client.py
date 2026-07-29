"""
Client onboarding: generates a ready-to-run client config in clients/.

Usage:
    python src/new_client.py "Acme Invest GmbH" \
        --keywords "acme invest, peter mustermann" \
        --people "Peter Mustermann (CEO), Anna Beispiel (CIO)" \
        --industry "Immobilienfonds, Sachwerte"

Only --keywords is required besides the name. The generated JSON can then
be fine-tuned by hand (extra queries, extra RSS feeds, prompt details).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from client_config import CLIENTS_DIR

VALIDATION_TEMPLATE = """Du pruefst ob Suchergebnisse tatsaechlich {name}{people_clause} DIREKT erwaehnen (nicht nur in Sidebar-Links oder Werbung):
{people_list}
Pruefe fuer jeden Eintrag:
1. Wird {name} oder eine der genannten Personen im Artikeltext selbst erwaehnt?
2. Passt der Kontext zur Branche ({industry}) — NICHT zu namensgleichen Personen/Firmen aus anderen Branchen?
3. Ist es KEIN Sidebar-Link, keine Werbung, kein "Weitere Artikel"-Verweis?

AUSGABE: Nur die RELEVANTEN Artikel als JSON-Array:
[{{"date":"YYYY-MM-DD","outlet":"Offizieller Medienname (z.B. Frankfurter Allgemeine Zeitung, nicht faz.net)","title":"Exakter Artikeltitel","country":"D/CH/A/DACH","type":"Online","tier":1 oder 2,"link":"URL"}}]

TIER 1: FAZ, Handelsblatt, Boersen-Zeitung, NZZ, Finews, Institutional Money, DAS INVESTMENT, FONDS professionell, altii, Citywire, portfolio institutionell, Handelszeitung, Der Standard, Die Presse, WirtschaftsWoche, Manager Magazin, Capital, SZ, Boerse Online
TIER 2: Alle anderen

Keine Treffer? Antworte: []"""


def slugify(name):
    slug = name.lower()
    for src, dst in [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")]:
        slug = slug.replace(src, dst)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def build_config(name, keywords, people, industry, year):
    slug = slugify(name)
    quoted = [f'"{k}"' for k in keywords]

    google_queries = list(quoted)
    for q in quoted:
        google_queries.append(f"{q} {year}")
    if industry:
        main_terms = [t.strip() for t in industry.split(",") if t.strip()][:3]
        for term in main_terms:
            google_queries.append(f"{quoted[0]} {term}")

    people_list = ""
    people_clause = ""
    if people:
        people_clause = " oder eine der folgenden Personen"
        people_list = "- " + people + "\n\n"

    validation = VALIDATION_TEMPLATE.format(
        name=name,
        people_clause=people_clause,
        people_list=people_list,
        industry=industry or "siehe Keywords",
    )

    return {
        "slug": slug,
        "name": name,
        "agent_title": f"{name} — DACH Clipping Agent",
        "data_file": f"data/{slug}/clippings.json",
        "output_prefix": f"{slug}_{year}_DACH_Clipping_Report",
        "report_title": f"{name} — Quantitative Clippings Analysis (DACH) | {year}",
        "clippings_sheet": f"{year} Clippings",
        "analysis_sheet": f"Analysis {year}",
        "latest_copy": f"docs/{slug}_latest.xlsx",
        "keywords": [k.lower() for k in keywords],
        "google_queries": google_queries,
        "page2_queries": quoted[:3],
        "google_news_queries": quoted[:5],
        "fallback_queries": quoted[:6],
        "extra_rss_feeds": [],
        "extra_tier1_keywords": [],
        "validation_prompt": validation,
    }


def main():
    parser = argparse.ArgumentParser(description="Create a new clipping client")
    parser.add_argument("name", help='Client name, e.g. "Acme Invest GmbH"')
    parser.add_argument("--keywords", required=True,
                        help="Comma-separated search keywords (brand names, people)")
    parser.add_argument("--people", default="",
                        help='Key people with roles, e.g. "Peter Mustermann (CEO), ..."')
    parser.add_argument("--industry", default="",
                        help='Industry context, e.g. "Immobilienfonds, Sachwerte"')
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--force", action="store_true", help="Overwrite existing config")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if not keywords:
        sys.exit("ERROR: --keywords must contain at least one keyword")

    cfg = build_config(args.name, keywords, args.people, args.industry, args.year)
    path = CLIENTS_DIR / f"{cfg['slug']}.json"
    if path.exists() and not args.force:
        sys.exit(f"ERROR: {path} exists already (use --force to overwrite)")

    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(f"✅ Client created: {path}")
    print(f"   Slug: {cfg['slug']}")
    print(f"   Test run: python src/main.py --client {cfg['slug']}")
    print("   Tip: refine google_queries and validation_prompt in the JSON for fewer false positives.")


if __name__ == "__main__":
    main()
