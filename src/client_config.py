"""
Client configuration loader.

Each paying client gets one JSON file in clients/. The agent runs the full
pipeline (RSS + Google + Claude validation + Excel report) once per client.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"

REQUIRED_FIELDS = ["slug", "name", "keywords", "google_queries", "validation_prompt"]

DEFAULTS = {
    "page2_queries": [],
    "google_news_queries": [],
    "fallback_queries": [],
    "extra_rss_feeds": [],
    "extra_tier1_keywords": [],
    "clippings_sheet": "Clippings",
    "analysis_sheet": "Analysis",
    "latest_copy": None,
}


def _apply_defaults(cfg):
    for key, val in DEFAULTS.items():
        cfg.setdefault(key, val)
    cfg.setdefault("agent_title", f"{cfg['name']} — Clipping Agent")
    cfg.setdefault("data_file", f"data/{cfg['slug']}/clippings.json")
    cfg.setdefault("output_prefix", f"{cfg['slug']}_Clipping_Report")
    cfg.setdefault("report_title", f"{cfg['name']} — Quantitative Clippings Analysis (DACH)")
    return cfg


def load_client(slug):
    path = CLIENTS_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"No client config: {path}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    missing = [k for k in REQUIRED_FIELDS if not cfg.get(k)]
    if missing:
        raise ValueError(f"Client '{slug}' is missing fields: {missing}")
    return _apply_defaults(cfg)


def list_clients():
    if not CLIENTS_DIR.exists():
        return []
    return sorted(p.stem for p in CLIENTS_DIR.glob("*.json"))


def data_path(cfg):
    return REPO_ROOT / cfg["data_file"]
