"""
Main runner: Search for new clippings, then generate Excel report.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from search import run_search, load_clippings
from excel_writer import build_report


def main():
    print("=" * 60)
    print("MK Global Kapital — DACH Clipping Agent")
    print("=" * 60)
    
    # Step 1: Search
    print("\n📡 Step 1: Searching for new clippings...\n")
    new_articles = run_search()
    
    # Step 2: Generate report
    print("\n📊 Step 2: Generating Excel report...\n")
    clips = load_clippings()
    if clips:
        filepath = build_report()
        if filepath:
            print(f"\n✅ Done! Report: {filepath}")
            print(f"   Total clippings: {len(clips)}")
            print(f"   New this run: {len(new_articles)}")
    else:
        print("No clippings available for report generation.")


if __name__ == "__main__":
    main()
