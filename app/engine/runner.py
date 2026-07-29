"""
Runner: Monitoring + Report + Versand für einen oder alle Kunden.

Aufruf (aus dem app/-Verzeichnis):
  python -m engine.runner              # alle aktiven Kunden
  python -m engine.runner --client demo
  python -m engine.runner --no-mail    # ohne E-Mail-Versand (z.B. lokal)
"""
import argparse
import sys
from datetime import datetime

from .config import load_all_clients
from .mailer import send_report
from .monitor import load_clippings, run_monitor
from .report import build_report


def run_client(cfg, send_mail=True):
    new_articles = run_monitor(cfg)
    clips = load_clippings(cfg)
    if not clips:
        return {"client": cfg.client_id, "new": 0, "total": 0}

    report_path = build_report(cfg, clips)

    # Wöchentliche Kunden bekommen nur montags Post, tägliche immer bei Neuigkeiten
    is_monday = datetime.now().weekday() == 0
    should_send = bool(new_articles) if cfg.frequency == "daily" else is_monday
    if send_mail and should_send:
        try:
            send_report(cfg, new_articles, len(clips), report_path)
        except Exception as e:
            print(f"  Mail: Fehler beim Versand — {e}")

    return {"client": cfg.client_id, "new": len(new_articles), "total": len(clips)}


def main():
    parser = argparse.ArgumentParser(description="ClipRadar Runner")
    parser.add_argument("--client", help="Nur diesen Kunden verarbeiten (client_id)")
    parser.add_argument("--no-mail", action="store_true", help="E-Mail-Versand überspringen")
    args = parser.parse_args()

    clients = load_all_clients()
    if args.client:
        clients = [c for c in clients if c.client_id == args.client]
        if not clients:
            print(f"Kunde '{args.client}' nicht gefunden oder inaktiv")
            sys.exit(1)

    print(f"ClipRadar — {len(clients)} Kunde(n) werden verarbeitet")
    summary = [run_client(cfg, send_mail=not args.no_mail) for cfg in clients]

    print(f"\n{'=' * 60}\nZUSAMMENFASSUNG\n{'=' * 60}")
    for s in summary:
        print(f"  {s['client']:20} neu: {s['new']:3}   gesamt: {s['total']}")


if __name__ == "__main__":
    main()
