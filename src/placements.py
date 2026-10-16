"""
Soll-Liste: placements the team has arranged (guest articles, interviews).
File: <data dir>/placements.csv, separated by semicolons, editable in Excel or on GitHub.

Columns: person;outlet;domain;expected_date;title_hint;status;found_date;found_link;notes
- domain: e.g. bondguide.de (required)
- expected_date: YYYY-MM-DD or DD.MM.YYYY (required)
- person, title_hint: optional, narrow the match
- status/found_*: filled in by the agent
"""
import csv
from datetime import date, timedelta

from client_config import data_path
from util import extract_domain, iso_date, norm_title, today_utc

FIELDS = ["person", "outlet", "domain", "expected_date", "title_hint", "status", "found_date", "found_link", "notes"]
GRACE_DAYS = 3


def placements_path(cfg):
    return data_path(cfg).parent / "placements.csv"


def _read(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f, delimiter=";")]


def _write(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def _matches(row, clip):
    dom = (row.get("domain") or "").strip().lower().replace("www.", "")
    if not dom or not extract_domain(clip.get("link", "")).endswith(dom):
        return False
    exp = iso_date(row.get("expected_date"))
    if exp and clip.get("date") and clip["date"] < (date.fromisoformat(exp) - timedelta(days=7)).isoformat():
        return False
    person = (row.get("person") or "").strip().lower()
    if person:
        surname = person.split()[-1]
        hay = " ".join(clip.get("people", [])).lower() + " " + clip.get("title", "").lower() + " " + clip.get("author", "").lower()
        if surname not in hay:
            return False
    hint = norm_title(row.get("title_hint") or "")
    if hint:
        words = [w for w in hint.split() if len(w) > 3]
        title = norm_title(clip.get("title", ""))
        if words and sum(w in title for w in words) < max(1, len(words) // 2):
            return False
    return True


def update_placements(cfg, clips, dry_run=False):
    path = placements_path(cfg)
    rows = _read(path)
    report = {"total": len(rows), "found_now": [], "overdue": [], "open": 0}
    if not rows:
        if not path.exists() and not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            _write(path, [])
        return report
    today = today_utc()
    before = [dict(r) for r in rows]
    for row in rows:
        if (row.get("status") or "").strip().lower() == "gefunden":
            continue
        hits = sorted((c for c in clips if _matches(row, c)), key=lambda c: c.get("date", ""))
        if hits:
            row["status"] = "gefunden"
            row["found_date"] = hits[0].get("date", "")
            row["found_link"] = hits[0].get("link", "")
            report["found_now"].append({k: row.get(k, "") for k in ("person", "outlet", "domain", "found_link")})
            continue
        report["open"] += 1
        exp = iso_date(row.get("expected_date"))
        if exp and today > date.fromisoformat(exp) + timedelta(days=GRACE_DAYS):
            row["status"] = "überfällig"
            report["overdue"].append({k: row.get(k, "") for k in ("person", "outlet", "domain", "expected_date", "title_hint")})
        else:
            row["status"] = "offen"
    if not dry_run and rows != before:
        _write(path, rows)
    return report
