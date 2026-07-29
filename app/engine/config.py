"""
Kunden-Konfigurationen laden und validieren.

Jeder Kunde ist eine YAML-Datei in app/clients/. Dateien, die mit "_"
beginnen (z.B. _template.yml), werden ignoriert.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CLIENTS_DIR = Path(__file__).parent.parent / "clients"
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

DEFAULT_TIER1_KEYWORDS = [
    "faz", "frankfurter allgemeine", "handelsblatt",
    "boersen-zeitung", "börsen-zeitung", "nzz", "neue zuercher", "neue zürcher",
    "finews", "institutional money", "institutional-money",
    "das investment", "dasinvestment",
    "fonds professionell", "fondsprofessionell",
    "altii", "citywire",
    "portfolio institutionell", "portfolio-institutionell",
    "handelszeitung",
    "der standard", "derstandard",
    "die presse", "diepresse",
    "wiwo", "wirtschaftswoche",
    "manager magazin", "manager-magazin",
    "capital.de", "sueddeutsche",
    "boerse-online", "börse online",
    "spiegel", "zeit.de", "welt.de", "n-tv", "srf.ch", "tagesanzeiger",
]

VALID_PLANS = {"starter", "pro", "agentur", "intern"}
VALID_FREQUENCIES = {"daily", "weekly"}


@dataclass
class ClientConfig:
    client_id: str
    name: str
    active: bool = True
    plan: str = "starter"
    report_title: str = ""
    keywords: list = field(default_factory=list)
    context: str = ""
    disambiguation: str = ""
    google_queries: list = field(default_factory=list)
    google_news_queries: list = field(default_factory=list)
    page2_queries: list = field(default_factory=list)
    feed_packs: list = field(default_factory=list)
    extra_rss_feeds: list = field(default_factory=list)
    tier1_keywords: list = field(default_factory=list)
    delivery_emails: list = field(default_factory=list)
    frequency: str = "daily"

    @property
    def data_file(self):
        return DATA_DIR / self.client_id / "clippings.json"

    @property
    def output_dir(self):
        return OUTPUT_DIR / self.client_id

    def all_tier1_keywords(self):
        return DEFAULT_TIER1_KEYWORDS + [k.lower() for k in self.tier1_keywords]


class ConfigError(Exception):
    pass


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_client(path):
    """Eine Kunden-YAML in eine validierte ClientConfig umwandeln."""
    raw = _load_yaml(path)
    client_id = raw.get("client") or Path(path).stem

    keywords = [str(k).lower().strip() for k in raw.get("keywords", []) if str(k).strip()]
    if not keywords:
        raise ConfigError(f"{path}: 'keywords' ist Pflicht (mindestens 1 Suchbegriff)")

    plan = str(raw.get("plan", "starter")).lower()
    if plan not in VALID_PLANS:
        raise ConfigError(f"{path}: Ungültiger Plan '{plan}' (erlaubt: {sorted(VALID_PLANS)})")

    delivery = raw.get("delivery") or {}
    frequency = str(delivery.get("frequency", "daily")).lower()
    if frequency not in VALID_FREQUENCIES:
        raise ConfigError(f"{path}: Ungültige Frequenz '{frequency}' (erlaubt: daily, weekly)")

    return ClientConfig(
        client_id=client_id,
        name=raw.get("name", client_id),
        active=bool(raw.get("active", True)),
        plan=plan,
        report_title=raw.get("report_title") or f"{raw.get('name', client_id)} — DACH Pressespiegel",
        keywords=keywords,
        context=raw.get("context", ""),
        disambiguation=raw.get("disambiguation", ""),
        google_queries=raw.get("google_queries", []),
        google_news_queries=raw.get("google_news_queries", []),
        page2_queries=raw.get("page2_queries", []),
        feed_packs=raw.get("feed_packs", []),
        extra_rss_feeds=raw.get("extra_rss_feeds", []),
        tier1_keywords=raw.get("tier1_keywords", []),
        delivery_emails=delivery.get("emails", []),
        frequency=frequency,
    )


def load_all_clients(clients_dir=None):
    """Alle aktiven Kunden laden, sortiert nach client_id."""
    clients_dir = Path(clients_dir or CLIENTS_DIR)
    clients = []
    for path in sorted(clients_dir.glob("*.yml")):
        if path.name.startswith("_"):
            continue
        cfg = load_client(path)
        if cfg.active:
            clients.append(cfg)
    return clients
