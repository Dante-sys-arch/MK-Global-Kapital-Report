"""
Persistent agent state per client (data/state/<slug>.json).

Remembers which URLs were already checked (so pages are not fetched again),
which outlets offer a WordPress search, and when the daily jobs last ran.
"""
import json
from datetime import timedelta

from client_config import REPO_ROOT
from util import berlin_today, today_utc

KEEP_DAYS = 400


class State:
    def __init__(self, slug):
        self.path = REPO_ROOT / "data" / "state" / f"{slug}.json"
        self.data = {"checked": {}, "outlets": {}, "daily": {}, "rss_seen": {}}
        if self.path.exists():
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except (OSError, json.JSONDecodeError):
                pass

    # URLs whose page was fetched and judged. value: {"d": date, "r": result}
    def was_checked(self, key):
        return key in self.data["checked"]

    def check_result(self, key):
        entry = self.data["checked"].get(key)
        return entry.get("r") if entry else None

    def mark_checked(self, key, result):
        self.data["checked"][key] = {"d": today_utc().isoformat(), "r": result}

    def forget_checked(self, key):
        self.data["checked"].pop(key, None)

    # Daily jobs (SerpApi budget, site searches, monthly backfill): once per Berlin calendar day.
    def due_today(self, job):
        return self.data["daily"].get(job) != berlin_today().isoformat()

    def mark_done_today(self, job):
        self.data["daily"][job] = berlin_today().isoformat()

    # Per-outlet capability cache (WordPress search yes/no, sitemap URLs).
    def outlet(self, domain):
        return self.data["outlets"].setdefault(domain, {})

    def save(self):
        cutoff = (today_utc() - timedelta(days=KEEP_DAYS)).isoformat()
        self.data["checked"] = {k: v for k, v in self.data["checked"].items() if v.get("d", "") >= cutoff}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=0, sort_keys=True)
