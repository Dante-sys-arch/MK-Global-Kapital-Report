"""
Main runner: for each client, search for new clippings and generate an
Excel report.

Usage:
    python src/main.py                     # run ALL clients in clients/
    python src/main.py --client <slug>     # run a single client
    python src/main.py --report-only       # skip search, only rebuild reports
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from client_config import load_client, list_clients
from search import run_search, load_clippings
from excel_writer import build_report


def run_client(cfg, report_only=False):
    print("=" * 60)
    print(cfg["agent_title"])
    print("=" * 60)

    new_articles = []
    if not report_only:
        print("\n📡 Step 1: Searching for new clippings...\n")
        new_articles = run_search(cfg)

    print("\n📊 Step 2: Generating Excel report...\n")
    clips = load_clippings(cfg)
    if clips:
        filepath = build_report(cfg)
        if filepath:
            print(f"\n✅ Done! Report: {filepath}")
            print(f"   Total clippings: {len(clips)}")
            print(f"   New this run: {len(new_articles)}")
    else:
        print("No clippings available for report generation.")


def main():
    parser = argparse.ArgumentParser(description="DACH Clipping Agent (multi-client)")
    parser.add_argument("--client", help="Run only this client slug (default: all)")
    parser.add_argument("--report-only", action="store_true",
                        help="Skip search, only regenerate Excel reports")
    args = parser.parse_args()

    slugs = [args.client] if args.client else list_clients()
    if not slugs:
        print("No clients configured. Add one with: python src/new_client.py")
        sys.exit(1)

    failures = []
    for slug in slugs:
        try:
            run_client(load_client(slug), report_only=args.report_only)
        except Exception as e:
            print(f"\n❌ Client '{slug}' failed: {e}")
            failures.append(slug)
        print()

    if failures:
        print(f"Finished with failures: {', '.join(failures)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
