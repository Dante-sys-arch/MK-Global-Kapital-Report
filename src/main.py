"""
Main runner: for each client, search for new clippings and generate an
Excel report.

Usage:
    python src/main.py                                  # daily run, all clients
    python src/main.py --client <slug>                  # one client
    python src/main.py --report-only                    # only rebuild Excel reports
    python src/main.py --mode backfill --from 2026-04-01 --to 2026-10-16
    python src/main.py --dry-run                        # search and report, change nothing
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from client_config import load_client, list_clients
from util import berlin_today as _berlin_day


def berlin_today():
    return _berlin_day().isoformat()
from search import run_search, load_clippings
from excel_writer import build_report


def run_client(cfg, args):
    if args.scheduled and args.mode == "daily" and not args.dry_run:
        from state import State
        done = State(cfg["slug"]).data.get("daily", {}).get("full_run")
        if done == berlin_today():
            print(f"{cfg['name']}: Tageslauf für {done} schon erledigt, Ersatztermin übersprungen.")
            return
    print("=" * 60)
    print(cfg["agent_title"])
    print("=" * 60)

    new_articles = []
    if not args.report_only:
        start = date.fromisoformat(args.date_from) if args.date_from else None
        end = date.fromisoformat(args.date_to) if args.date_to else date.today()
        if args.mode == "backfill" and not start:
            raise SystemExit("--mode backfill braucht --from YYYY-MM-DD")
        new_articles = run_search(cfg, mode=args.mode, start=start, end=end, dry_run=args.dry_run,
                                  daily_jobs=not args.no_daily_jobs)
        if args.mode == "daily" and not args.dry_run and not args.no_daily_jobs:
            from state import State
            st = State(cfg["slug"])
            st.data.setdefault("daily", {})["full_run"] = berlin_today()
            st.save()

    if args.dry_run:
        print(f"\nTestlauf: {len(new_articles)} neue Clippings gefunden, nichts gespeichert.")
        return
    clips = load_clippings(cfg)
    if clips:
        filepath = build_report(cfg)
        if filepath:
            print(f"\nReport: {filepath}  |  gesamt {len(clips)}  |  neu {len(new_articles)}")


def main():
    parser = argparse.ArgumentParser(description="DACH Clipping Agent (multi-client)")
    parser.add_argument("--client", help="Run only this client slug (default: all)")
    parser.add_argument("--report-only", action="store_true", help="Skip search, only regenerate Excel reports")
    parser.add_argument("--mode", choices=["daily", "backfill", "enrich", "inbox"], default="daily")
    parser.add_argument("--from", dest="date_from", help="Backfill start YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="Backfill end YYYY-MM-DD (default today)")
    parser.add_argument("--dry-run", action="store_true", help="Search and report, but save nothing")
    parser.add_argument("--no-daily-jobs", action="store_true",
                        help="Quick run (push trigger): no once-per-day jobs (SerpApi, site search, backfill), "
                             "does not count as the day's run")
    parser.add_argument("--scheduled", action="store_true",
                        help="Scheduled trigger: skip if today's daily run (Berlin time) is already done")
    args = parser.parse_args()

    slugs = [args.client] if args.client else list_clients()
    if not slugs:
        print("No clients configured. Add one with: python src/new_client.py")
        sys.exit(1)

    failures = []
    for slug in slugs:
        try:
            run_client(load_client(slug), args)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"\nClient '{slug}' failed: {e}")
            failures.append(slug)
        print()

    if failures:
        print(f"Finished with failures: {', '.join(failures)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
