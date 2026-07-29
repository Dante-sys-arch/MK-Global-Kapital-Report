"""
FinVoice — Kunden-Konfigurationen.

Jeder Kunde (= eine Führungskraft) ist eine JSON-Datei in finvoice/clients/.
Vorlage: clients/beispiel-ceo.json.example
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CLIENTS_DIR = BASE / "clients"
DATA_DIR = BASE / "data"
DOCS_DIR = BASE / "docs"

REQUIRED = ["name", "company", "role", "topics", "feeds"]

DEFAULTS = {
    "language": "de",
    "posts_per_week": 3,
    "keywords": [],
    "positions": [],
    "avoid": [],
    "voice_samples": [],
}


def slugify(name: str) -> str:
    s = name.lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def list_clients() -> list[str]:
    return sorted(p.stem for p in CLIENTS_DIR.glob("*.json"))


def load_client(slug: str) -> dict:
    path = CLIENTS_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"Kein Kunde '{slug}' — erwartet: {path}")
    client = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if not client.get(k)]
    if missing:
        raise ValueError(f"Kunde '{slug}': Pflichtfelder fehlen: {', '.join(missing)}")
    for key, value in DEFAULTS.items():
        client.setdefault(key, value)
    client["slug"] = slug
    return client


def data_path(client: dict, filename: str) -> Path:
    d = DATA_DIR / client["slug"]
    d.mkdir(parents=True, exist_ok=True)
    return d / filename


def docs_path(client: dict) -> Path:
    d = DOCS_DIR / client["slug"]
    d.mkdir(parents=True, exist_ok=True)
    return d
