"""
FinVoice — Orchestrierung.

    python finvoice/src/main.py                      # alle Kunden
    python finvoice/src/main.py --client max-berger  # ein Kunde
    python finvoice/src/main.py --render-only        # nur Seiten neu bauen

Läuft wöchentlich (Montag früh) via GitHub Actions, siehe
.github/workflows/finvoice.yml.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from client_config import data_path, list_clients, load_client
from collect import collect_hooks
from generate import generate_drafts
from review_page import render_client_page


def run_client(slug: str, render_only: bool = False) -> None:
    client = load_client(slug)
    print(f"\n▶ {client['name']} ({client['company']})")

    if not render_only:
        week = datetime.now().strftime("%G-W%V")
        hooks = collect_hooks(client)
        print(f"  {len(hooks)} Aufhänger gesammelt")
        drafts = generate_drafts(client, hooks)
        payload = {
            "week": week,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "hooks": hooks,
            "drafts": drafts,
        }
        out = data_path(client, f"{week}.json")
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ {len(drafts)} Entwürfe → {out}")

    render_client_page(client)


def main() -> None:
    parser = argparse.ArgumentParser(description="FinVoice Ghostwriting-Agent")
    parser.add_argument("--client", help="Nur diesen Kunden-Slug verarbeiten")
    parser.add_argument("--render-only", action="store_true", help="Nur HTML-Seiten neu bauen")
    args = parser.parse_args()

    slugs = [args.client] if args.client else list_clients()
    if not slugs:
        print("Keine Kunden in finvoice/clients/ — siehe beispiel-ceo.json.example")
        return

    failures = 0
    for slug in slugs:
        try:
            run_client(slug, render_only=args.render_only)
        except Exception as exc:
            failures += 1
            print(f"  ✗ Fehler bei '{slug}': {exc}")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
