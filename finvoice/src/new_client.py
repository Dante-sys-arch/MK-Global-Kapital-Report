"""
FinVoice — Kunden-Onboarding (2 Minuten).

    python finvoice/src/new_client.py "Dr. Max Berger" \
      --company "Berger Capital AG" --role CEO \
      --topics "Sachwerte, Zinswende, Private Markets" \
      --keywords "zinsen, immobilienfonds, private equity" \
      --feeds "https://www.dasinvestment.com/feed/" "https://www.institutional-money.com/rss/news/"

Danach: 2–3 echte LinkedIn-Posts des Kunden als voice_samples in die
JSON-Datei kopieren — das ist der wichtigste Schritt für die Tonalität.
"""
import argparse
import json

from client_config import CLIENTS_DIR, slugify


def main() -> None:
    parser = argparse.ArgumentParser(description="Neuen FinVoice-Kunden anlegen")
    parser.add_argument("name", help="Name der Führungskraft, z. B. 'Dr. Max Berger'")
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", default="CEO")
    parser.add_argument("--topics", required=True, help="Kommagetrennt")
    parser.add_argument("--keywords", default="", help="Kommagetrennt, für Feed-Filterung")
    parser.add_argument("--feeds", nargs="+", required=True, help="RSS-Feed-URLs")
    parser.add_argument("--language", default="de")
    parser.add_argument("--posts-per-week", type=int, default=3)
    args = parser.parse_args()

    slug = slugify(args.name)
    path = CLIENTS_DIR / f"{slug}.json"
    if path.exists():
        raise SystemExit(f"Kunde existiert bereits: {path}")

    client = {
        "name": args.name,
        "company": args.company,
        "role": args.role,
        "language": args.language,
        "posts_per_week": args.posts_per_week,
        "topics": [t.strip() for t in args.topics.split(",") if t.strip()],
        "keywords": [k.strip() for k in args.keywords.split(",") if k.strip()],
        "feeds": args.feeds,
        "positions": [
            "HIER EINTRAGEN: 2-4 Kernthesen, die der Kunde öffentlich vertritt",
        ],
        "avoid": [
            "HIER EINTRAGEN: Tabuthemen (z. B. Politik, Wettbewerber, konkrete Produkte)",
        ],
        "voice_samples": [
            "HIER EINTRAGEN: 2-3 echte LinkedIn-Posts des Kunden (Copy & Paste)",
        ],
    }
    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(client, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ Kunde angelegt: {path}")
    print("→ Jetzt voice_samples, positions und avoid in der JSON ausfüllen,")
    print(f"  dann Testlauf: python finvoice/src/main.py --client {slug}")


if __name__ == "__main__":
    main()
