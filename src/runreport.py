"""
Run report and health check.

Each run writes data/runs/<slug>-latest.json, a readable data/runs/<slug>-latest.md,
appends one line to data/runs/<slug>-history.jsonl and updates docs/status.json
for the dashboard. `python src/runreport.py` exits with 1 if the latest run of
any client is unhealthy, which makes the GitHub workflow fail and send an email.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from client_config import REPO_ROOT, list_clients

RUNS = REPO_ROOT / "data" / "runs"
HISTORY_KEEP = 500

LABELS = {"rss": "RSS-Feeds", "google": "Google Websuche (Custom Search)", "gnews": "Google News", "bing": "Bing News",
          "serper": "Serper (Google Web + News)", "site": "Seitensuche der Stammmedien",
          "sitemap": "Neue Artikel der Stammmedien", "claude": "Claude-Prüfung", "fetch": "Artikelseiten"}


def evaluate(channels, counts, placements):
    problems, warnings = [], []

    def ch(name):
        return channels.get(name, {"requests": 0, "ok": 0, "errors": 0, "notes": []})

    rss = ch("rss")
    if rss["requests"] and rss["ok"] == 0:
        problems.append("Kein einziger RSS-Feed erreichbar")
    elif rss["requests"] and rss["ok"] < 0.6 * rss["requests"]:
        warnings.append(f"Nur {rss['ok']} von {rss['requests']} RSS-Feeds liefern Einträge")
    gn = ch("gnews")
    if gn["requests"] and gn["ok"] == 0:
        problems.append(f"{LABELS['gnews']}: alle {gn['requests']} Anfragen gescheitert ({'; '.join(gn['notes'][:2])})")
    elif gn["errors"]:
        warnings.append(f"{LABELS['gnews']}: {gn['errors']} von {gn['requests']} Anfragen gescheitert")
    go, sp0 = ch("google"), ch("serper")
    google_dead = go["requests"] and go["ok"] == 0
    serper_ok = sp0["ok"] > 0
    if google_dead and not serper_ok:
        reason = "Custom Search gesperrt" if any("does not have the access" in n for n in go["notes"]) else "; ".join(go["notes"][:1])
        problems.append(f"Keine Google-Websuche: {reason}, Serper nicht eingerichtet (Secret SERPER_API_KEY)")
    elif google_dead:
        warnings.append("Google Custom Search ausgefallen, Websuche läuft über Serper")
    elif go["errors"]:
        warnings.append(f"{LABELS['google']}: {go['errors']} von {go['requests']} Anfragen gescheitert")
    if any("keine Zugangsdaten" in n for n in ch("google")["notes"]):
        warnings.append("Google Websuche ohne Zugangsdaten")
    cl = ch("claude")
    if any("kein ANTHROPIC_API_KEY" in n or "Client-Start" in n for n in cl["notes"]):
        problems.append("Claude-Prüfung nicht verfügbar (API-Schlüssel fehlt). Unklare Fälle liegen in der Prüfliste.")
    if cl["errors"]:
        problems.append(f"Claude-Prüfung fehlgeschlagen ({'; '.join(cl['notes'][:1])}). Unklare Fälle liegen in der Prüfliste.")
    for name in ("site", "sitemap", "bing"):
        c = ch(name)
        if c["requests"] and c["ok"] == 0:
            warnings.append(f"{LABELS[name]}: keine Quelle erreichbar")
    sp = ch("serper")
    if sp["errors"]:
        warnings.append(f"Serper: {sp['errors']} Fehler ({'; '.join(sp['notes'][:1])})")
    attempts = counts.get("fetched", 0) + counts.get("fetch_failed", 0)
    if attempts >= 10 and counts.get("fetch_failed", 0) > 0.5 * attempts:
        warnings.append(f"{counts['fetch_failed']} von {attempts} Artikelseiten nicht lesbar")
    if counts.get("deferred"):
        warnings.append(f"Zeitbudget erreicht: {counts['deferred']} Hinweise werden im nächsten Lauf geprüft")
    if placements and placements.get("overdue"):
        warnings.append(f"{len(placements['overdue'])} Platzierung(en) überfällig")
    status = "error" if problems else ("warn" if warnings else "ok")
    return {"status": status, "problems": problems, "warnings": warnings}


def _clip_view(c):
    return {k: c.get(k) for k in ("date", "outlet", "title", "link", "people", "byline", "found_via", "verified", "syndication_of") if c.get(k) not in (None, "", [])}


def write_report(agent, mode, started, placements):
    slug = agent.cfg["slug"]
    channels = agent.stats.channels
    health = evaluate(channels, agent.counts, placements)
    report = {
        "client": slug,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "dry_run": agent.dry_run,
        "duration_s": int((datetime.now() - started).total_seconds()),
        "health": health,
        "counts": agent.counts,
        "channels": channels,
        "new": [_clip_view(c) for c in agent.new],
        "new_review": agent.new_review,
        "rejected": agent.rejected[:80],
        "review_open": len(agent.review),
        "total_clippings": len(agent.clips),
        "placements": placements,
    }
    RUNS.mkdir(parents=True, exist_ok=True)
    suffix = "-dryrun" if agent.dry_run else ""
    with open(RUNS / f"{slug}{suffix}-latest.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(RUNS / f"{slug}{suffix}-latest.md", "w", encoding="utf-8") as f:
        f.write(markdown(report))
    if not agent.dry_run:
        hist = RUNS / f"{slug}-history.jsonl"
        lines = hist.read_text(encoding="utf-8").splitlines() if hist.exists() else []
        summary = {k: report[k] for k in ("run_at", "mode", "duration_s", "review_open", "total_clippings")}
        summary.update(status=health["status"], new=len(agent.new), new_review=len(agent.new_review),
                       channels={k: {"ok": v["ok"], "req": v["requests"], "cand": v["candidates"]} for k, v in channels.items()})
        lines.append(json.dumps(summary, ensure_ascii=False))
        hist.write_text("\n".join(lines[-HISTORY_KEEP:]) + "\n", encoding="utf-8")
        status = {"run_at": report["run_at"], "status": health["status"], "problems": health["problems"],
                  "warnings": health["warnings"], "new": len(agent.new), "review_open": len(agent.review)}
        docs = REPO_ROOT / "docs"
        docs.mkdir(exist_ok=True)
        name = "status.json" if agent.cfg.get("latest_copy") == "docs/latest_report.xlsx" else f"status-{slug}.json"
        with open(docs / name, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    print(markdown(report))
    return report


def markdown(r):
    h = r["health"]
    icon = {"ok": "OK", "warn": "WARNUNG", "error": "FEHLER"}[h["status"]]
    lines = [f"# Laufbericht {r['client']} – {r['run_at']} ({r['mode']}{', Testlauf' if r['dry_run'] else ''})", "",
             f"**Status: {icon}**", ""]
    for p in h["problems"]:
        lines.append(f"- FEHLER: {p}")
    for w in h["warnings"]:
        lines.append(f"- Warnung: {w}")
    lines += ["", "## Kanäle", "", "| Kanal | Anfragen | erfolgreich | Fehler | Kandidaten |", "|---|---|---|---|---|"]
    for name, c in r["channels"].items():
        lines.append(f"| {LABELS.get(name, name)} | {c['requests']} | {c['ok']} | {c['errors']} | {c['candidates']} |")
    c = r["counts"]
    lines += ["", f"Kandidaten {c['candidates']}, davon eindeutig {c['unique']}, schon bekannt {c['already_known']}, "
              f"schon geprüft {c['already_checked']}, Seiten geladen {c['fetched']}, nicht lesbar {c['fetch_failed']}, "
              f"ohne Treffer {c['no_match']}, Google-News-Links offen {c['gnews_unresolved']}, "
              f"aus Zeitgründen verschoben {c.get('deferred', 0)}.", ""]
    lines.append(f"## Neue Clippings ({len(r['new'])})")
    for n in r["new"]:
        lines.append(f"- {n.get('date','?')} | {n.get('outlet','')} | {n.get('title','')} | {', '.join(n.get('people', []))} | via {', '.join(n.get('found_via', []))} | {n.get('link','')}")
    lines.append(f"\n## Neu in der Prüfliste ({len(r['new_review'])}, offen gesamt {r['review_open']})")
    for n in r["new_review"]:
        lines.append(f"- {n.get('date','?')} | {n.get('outlet','')} | {n.get('title','')} | {n.get('reason','')} | {n.get('link','')}")
    if r["rejected"]:
        lines.append(f"\n## Verworfen ({len(r['rejected'])})")
        for n in r["rejected"]:
            lines.append(f"- {n.get('title','')} | {n.get('reason','')} | {n.get('link','')}")
    p = r.get("placements") or {}
    if p.get("total"):
        lines.append(f"\n## Soll-Liste: {p['total']} Platzierungen, offen {p['open']}, überfällig {len(p['overdue'])}")
        for o in p["overdue"]:
            lines.append(f"- überfällig: {o.get('person','')} | {o.get('outlet','') or o.get('domain','')} | erwartet {o.get('expected_date','')}")
    notes = [(k, n) for k, v in r["channels"].items() for n in v.get("notes", [])]
    if notes:
        lines.append("\n## Hinweise je Kanal")
        for k, n in notes:
            lines.append(f"- {LABELS.get(k, k)}: {n}")
    return "\n".join(lines) + "\n"


def health_exit():
    bad = []
    for slug in list_clients():
        path = RUNS / f"{slug}-latest.json"
        if path.exists():
            r = json.loads(path.read_text(encoding="utf-8"))
            if r["health"]["status"] == "error":
                bad.append(f"{slug}: " + " | ".join(r["health"]["problems"]))
    if bad:
        print("UNHEALTHY RUN:\n" + "\n".join(bad))
        sys.exit(1)
    print("Health check OK")


if __name__ == "__main__":
    health_exit()
