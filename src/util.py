"""
Shared helpers: HTTP, URL and text normalization, dates, country and outlet.
"""
import html as html_module
import re
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)

_session = requests.Session()  # main thread
_session.headers.update({"User-Agent": BROWSER_UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.6"})
_local = threading.local()


def _sess():
    if threading.current_thread() is threading.main_thread():
        return _session
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers.update(_session.headers)
    return _local.s

# Seconds between two requests to the same host (politeness). Different hosts run in parallel.
HOST_DELAY = 0.7
_host_delay = {}  # hosts that answered 429 get a longer delay
_last_hit = {}
_host_locks = {}
_locks_guard = threading.Lock()


def _wait_for_host(url):
    host = urlparse(url).netloc
    with _locks_guard:
        lock = _host_locks.setdefault(host, threading.Lock())
    with lock:
        last = _last_hit.get(host)
        delay = _host_delay.get(host, HOST_DELAY)
        if last is not None:
            gap = time.time() - last
            if gap < delay:
                time.sleep(delay - gap)
        _last_hit[host] = time.time()


def http_get(url, params=None, timeout=15, retries=2, headers=None):
    """GET with retries. Passes query params through (the v3 bug was dropping them)."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            _wait_for_host(url)
            resp = _sess().get(url, params=params, timeout=timeout, headers=headers)
            if resp.status_code == 429 and attempt < retries:
                host = urlparse(url).netloc
                _host_delay[host] = min(10.0, max(3.0, _host_delay.get(host, HOST_DELAY) * 2))
                try:
                    wait = min(30, int(resp.headers.get("Retry-After", "10")))
                except ValueError:
                    wait = 10
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise last_exc


def http_post(url, json_body=None, data=None, timeout=20, headers=None):
    _wait_for_host(url)
    return _sess().post(url, json=json_body, data=data, timeout=timeout, headers=headers)


# ── URL helpers ─────────────────────────────────────────────────

_TRACKING = re.compile(r"^(utm_\w+|ref|source|fbclid|gclid|xtor|wt_mc|wt_zmc|mc_cid|mc_eid|cmpid|ito|ns_\w+)$", re.I)


def normalize_url(url):
    """Canonical form for deduplication (scheme, www, tracking params, AMP, trailing slash)."""
    if not url:
        return ""
    url = url.strip()
    try:
        p = urlparse(url)
    except ValueError:
        return url.lower()
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("amp."):
        host = host[4:]
    path = re.sub(r"/amp/?$", "/", p.path)
    path = path.rstrip("/") or "/"
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not _TRACKING.match(k)]
    return urlunparse(("https", host, path.lower(), "", urlencode(query), ""))


def extract_domain(url):
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def domain_matches(domain, target):
    """True if domain equals target or is a subdomain of it."""
    return domain == target or domain.endswith("." + target)


# ── Text helpers ────────────────────────────────────────────────

def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html_module.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def norm_text(text):
    """Lowercase, unify dashes/apostrophes/whitespace for name matching."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[‐-―\-_/]+", " ", text)
    text = text.replace(" ", " ")
    return re.sub(r"\s+", " ", text)


def norm_title(title):
    """Title key for syndication/duplicate comparison."""
    t = norm_text(strip_html(title))
    t = t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_OUTLET_WORDS = ("news", "zeitung", "magazin", "online", "agentur", "presse", "verlag", "invest", "finanz",
                 ".de", ".ch", ".at", ".com", ".net", ".org", ".info")


def _looks_like_outlet(tail, hint=""):
    t = norm_text(tail)
    if not t or len(t) > 60:
        return False
    if hint:
        hint_words = {w for w in re.split(r"[\s.]+", norm_text(hint)) if len(w) > 3}
        if hint_words & set(re.split(r"[\s.]+", t)):
            return True
    if any(norm_text(name) == t for name in OUTLET_NAMES.values()):
        return True
    return any(w in t for w in _OUTLET_WORDS) and len(t.split()) <= 6


def clean_title(title, outlet=""):
    """Drop a trailing ' - Outlet' / ' | Outlet' suffix, but only if it looks like an outlet name."""
    t = strip_html(title)
    for _ in range(2):
        for sep in (" | ", " - ", " – ", " — "):
            if sep in t:
                head, tail = t.rsplit(sep, 1)
                if len(head) >= 15 and _looks_like_outlet(tail, outlet):
                    t = head
                    break
        else:
            break
    return t.strip()


# ── Dates ───────────────────────────────────────────────────────

def today_utc():
    return datetime.now(timezone.utc).date()


def iso_date(value):
    """Best-effort conversion of many date shapes to YYYY-MM-DD, else ''."""
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (tuple, list)) and len(value) >= 3:  # time.struct_time
        try:
            return date(value[0], value[1], value[2]).isoformat()
        except (TypeError, ValueError):
            return ""
    s = str(value).strip()
    m = re.match(r"(20\d{2})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(20\d{2})", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    m = re.search(r"(\d+)\s+(day|days|tag|tagen|hour|hours|stunde|stunden|min|minute|minuten|week|weeks|woche|wochen)", s.lower())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit.startswith(("day", "tag")):
            return (today_utc() - timedelta(days=n)).isoformat()
        if unit.startswith(("week", "woche")):
            return (today_utc() - timedelta(weeks=n)).isoformat()
        return today_utc().isoformat()
    return ""


def date_from_url(url):
    m = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"nachrichten-(20\d{2})-(\d{2})/", url or "")
    if m:
        return ""  # month only, not precise enough
    return ""


def plausible_date(d, earliest="2024-01-01"):
    """Reject impossible dates (future, far past)."""
    if not d:
        return False
    tomorrow = (today_utc() + timedelta(days=1)).isoformat()
    return earliest <= d <= tomorrow


# ── Country / outlet ────────────────────────────────────────────

COUNTRY_CH = [".ch", "finews", "payoff", "nzz", "investrends", "handelszeitung",
              "moneycab", "cash.ch", "allnews", "swissfinanceai", "tagesanzeiger", "srf.ch"]
COUNTRY_AT = [".at", "derstandard", "diepresse", "kurier.at", "boersen-kurier", "fondsexklusiv.at"]


def guess_country(outlet="", link=""):
    text = (outlet + " " + extract_domain(link)).lower()
    if any(k in text for k in COUNTRY_CH):
        return "CH"
    if any(k in text for k in COUNTRY_AT):
        return "A"
    return "D"


OUTLET_NAMES = {
    "faz.net": "Frankfurter Allgemeine Zeitung",
    "handelsblatt.com": "Handelsblatt",
    "nzz.ch": "Neue Zürcher Zeitung",
    "finews.ch": "Finews",
    "finews.com": "Finews",
    "dasinvestment.com": "DAS INVESTMENT",
    "fondsprofessionell.de": "FONDS professionell",
    "fondsprofessionell.at": "FONDS professionell",
    "institutional-money.com": "Institutional Money",
    "portfolio-institutionell.de": "portfolio institutionell",
    "handelszeitung.ch": "Handelszeitung",
    "boersen-zeitung.de": "Börsen-Zeitung",
    "derstandard.de": "Der Standard",
    "derstandard.at": "Der Standard",
    "diepresse.com": "Die Presse",
    "wiwo.de": "WirtschaftsWoche",
    "manager-magazin.de": "Manager Magazin",
    "capital.de": "Capital",
    "sueddeutsche.de": "Süddeutsche Zeitung",
    "welt.de": "Die Welt",
    "moneycab.com": "Moneycab",
    "investrends.ch": "investrends.ch",
    "bondguide.de": "BondGuide",
    "dfpa.info": "dfpa.info",
    "e-fundresearch.com": "e-fundresearch",
    "markteinblicke.de": "Markt Einblicke",
    "finanznachrichten.de": "finanznachrichten.de",
    "cash.ch": "cash.ch",
    "payoff.ch": "Payoff",
    "fondsexklusiv.de": "FONDS exklusiv",
    "fondsexklusiv.at": "FONDS exklusiv Österreich",
    "cash-online.de": "cash-online.de",
    "altii.de": "altii.de",
    "citywire.de": "Citywire Deutschland",
    "private-banking-magazin.de": "Private Banking Magazin",
    "fixed-income.org": "fixed-income.org",
    "finanzwelt.de": "finanzwelt",
    "procontra-online.de": "procontra",
    "exxecnews.org": "exxecnews",
    "boersen-kurier.at": "Börsen-Kurier",
    "kreditwesen.de": "Kreditwesen",
    "allnews.ch": "Allnews",
    "swissfinanceai.ch": "Swiss Finance AI",
    "srf.ch": "SRF",
    "n-tv.de": "n-tv",
    "tagesanzeiger.ch": "Tages-Anzeiger",
    "geldmeisterin.com": "geldmeisterin.com",
    "gruenderkueche.de": "Gründerküche",
    "platow.de": "Platow",
    "kurier.at": "Kurier",
    "privatemarkets360.com": "Private Markets 360",
    "fondstrends.ch": "fondstrends",
    "fondstrends.de": "fondstrends",
    "dpn-online.com": "dpn",
    "fundresearch.de": "FundResearch",
    "boerse-express.com": "Börse Express",
    "wallstreet-online.de": "wallstreet-online",
    "boerse.de": "boerse.de",
    "ariva.de": "ariva",
    "spotify.com": "Spotify",
}


def outlet_from_domain(domain):
    for key, name in OUTLET_NAMES.items():
        if domain_matches(domain, key):
            return name
    return ""


def normalize_outlet(name, link=""):
    """Prefer the curated name for a known domain, else the given name, else the domain."""
    known = outlet_from_domain(extract_domain(link)) if link else ""
    if known:
        return known
    if name:
        known = outlet_from_domain(name.lower().replace("www.", ""))
        return known or name
    return extract_domain(link)


BLOCKED_DOMAINS = [
    "facebook.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "instagram.com", "tiktok.com",
    "rocketreach.co", "contactout.com", "theorg.com",
    "northdata.com", "xing.com", "kununu.com",
    "indeed.com", "glassdoor.com", "stepstone.de",
    "reddit.com", "pinterest.com", "amazon.com",
    "leadiq.com", "thegrid.id", "zoominfo.com", "crunchbase.com",
    "news.google.com",
]


def is_blocked_domain(url, own_domains=()):
    d = extract_domain(url)
    if any(domain_matches(d, b) for b in BLOCKED_DOMAINS):
        return True
    return any(domain_matches(d, o) for o in own_domains)
