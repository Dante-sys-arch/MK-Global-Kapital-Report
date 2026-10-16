"""
DACH Clipping Agent v5 — maximum recall.

Every lead from every channel is checked on the article page itself:
the client's names must appear in the article (title, author line or main
text). Unclear cases go to Claude, and whatever stays unclear goes to the
review list instead of being dropped or added unchecked.

Counting rules (TE): every appearance counts, including syndicated copies on
other outlets; French-language articles from Romandie are not counted.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from client_config import data_path, REPO_ROOT
from fetcher import fetch_article, resolve_google_news
from matcher import Matcher, detect_language
from runreport import write_report
from sources import (CseBudget, GNEWS_EDITIONS, Stats, bing_news, google_cse, google_news,
                     scan_rss, serper, site_search, sitemap_crawl)
from state import State
from util import (clean_title, date_from_url, extract_domain, guess_country, iso_date, norm_text, norm_title,
                  normalize_outlet, normalize_url, plausible_date, today_utc)

SEARCH_CHANNELS = {"google", "gnews", "serper", "site", "bing"}

TIER1_KEYWORDS = [
    "faz", "frankfurter allgemeine", "handelsblatt", "boersen-zeitung", "börsen-zeitung",
    "nzz", "neue zürcher", "finews", "institutional money", "institutional-money",
    "das investment", "dasinvestment", "fonds professionell", "fondsprofessionell",
    "altii", "citywire", "portfolio institutionell", "portfolio-institutionell",
    "handelszeitung", "der standard", "derstandard", "die presse", "diepresse",
    "wiwo", "wirtschaftswoche", "manager magazin", "manager-magazin", "capital.de",
    "sueddeutsche", "boerse-online", "börse online",
]

# Shared RSS list (all clients). Broken or empty feeds show up in the run report.
RSS_FEEDS = [
    "https://www.faz.net/rss/aktuell/finanzen/",
    "https://www.faz.net/rss/aktuell/wirtschaft/",
    "https://www.handelsblatt.com/contentexport/feed/finanzen",
    "https://www.handelsblatt.com/contentexport/feed/unternehmen",
    "https://www.nzz.ch/finanzen.rss",
    "https://www.nzz.ch/wirtschaft.rss",
    "https://www.finews.ch/news/finanzplatz/rss/1finews",
    "https://www.dasinvestment.com/feed/",
    "https://www.fondsprofessionell.de/rss/news.xml",
    "https://www.institutional-money.com/rss/news/",
    "https://www.portfolio-institutionell.de/feed/",
    "https://www.handelszeitung.ch/rss.xml",
    "https://www.boersen-zeitung.de/rss",
    "https://www.derstandard.at/rss/wirtschaft",
    "https://diepresse.com/rss/Wirtschaft",
    "https://www.wiwo.de/contentexport/feed/rss/schlagzeilen/finanzen/",
    "https://www.manager-magazin.de/finanzen/index.rss",
    "https://www.capital.de/feed/rss",
    "https://rss.sueddeutsche.de/rss/Wirtschaft",
    "https://www.welt.de/feeds/section/finanzen.rss",
    "https://kurier.at/wirtschaft/rss",
    "https://www.moneycab.com/feed/",
    "https://investrends.ch/feed/",
    "https://www.bondguide.de/feed/",
    "https://www.dfpa.info/rss/",
    "https://e-fundresearch.com/rss",
    "https://markteinblicke.de/feed/",
    "https://www.cash.ch/rss/news",
    "https://www.payoff.ch/feed/",
    "https://www.fondsexklusiv.de/feed/",
    "https://www.fondsexklusiv.at/feed/",
    "https://www.cash-online.de/feed/",
    "https://www.altii.de/feed/",
    "https://citywire.de/feed/",
    "https://www.private-banking-magazin.de/feed/",
    "https://www.fixed-income.org/feed/",
    "https://www.finanzwelt.de/feed/",
    "https://www.procontra-online.de/feed/",
    "https://exxecnews.org/feed/",
    "https://www.boersen-kurier.at/feed/",
    "https://www.kreditwesen.de/feed/",
    "https://www.allnews.ch/rss",
    "https://www.swissfinanceai.ch/feed/",
    "https://www.srf.ch/news/wirtschaft/rss/feed",
    "https://www.n-tv.de/wirtschaft/rss",
    "https://www.tagesanzeiger.ch/wirtschaft/rss.xml",
    "https://www.geldmeisterin.com/feed/",
    "https://www.gruenderkueche.de/feed/",
    "https://www.platow.de/feed/",
    "https://fondstrends.ch/feed/",
    "https://www.dpn-online.com/feed/",
    "https://www.fundresearch.de/feed/",
    "https://privatemarkets360.com/feed/",
]


def _slug(url):
    path = (url or "").split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"\.(html?|php)$", "", path.lower())


def guess_tier(outlet, link, extra=()):
    text = (outlet + " " + link).lower()
    return 1 if any(k in text for k in list(TIER1_KEYWORDS) + list(extra)) else 2


def load_clippings(cfg):
    p = data_path(cfg)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def review_path(cfg):
    return data_path(cfg).parent / "review.json"


def _month_windows(start, end):
    cur = start
    while cur <= end:
        nxt = (cur.replace(day=1) + timedelta(days=32)).replace(day=1)
        yield cur, min(end, nxt - timedelta(days=1))
        cur = nxt


class Agent:
    def __init__(self, cfg, dry_run=False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.stats = Stats()
        self.matcher = Matcher(cfg)
        self.state = State(cfg["slug"])
        self.clips = load_clippings(cfg)
        rp = review_path(cfg)
        self.review = json.load(open(rp, encoding="utf-8")) if rp.exists() else []
        self.own = cfg.get("own_domains", [])
        self.new, self.new_review, self.rejected = [], [], []
        self.counts = {"candidates": 0, "unique": 0, "already_known": 0, "already_checked": 0,
                       "fetched": 0, "fetch_failed": 0, "no_match": 0, "gnews_unresolved": 0}
        from validator import Validator
        self.validator = Validator(cfg, self.matcher, self.stats)
        self.deadline = None
        self.out_of_time = 0
        self._reindex()

    def _time_left(self):
        return self.deadline is None or time.time() < self.deadline

    def _fetch_many(self, links, workers=8):
        """Load pages in parallel (per-host politeness is kept in util.http_get)."""
        links = list(dict.fromkeys(links))
        by_host = {}
        for link in links:
            by_host.setdefault(extract_domain(link), []).append(link)
        links = []
        while any(by_host.values()):
            for host in list(by_host):
                if by_host[host]:
                    links.append(by_host[host].pop(0))
        results = {}
        if not links:
            return results

        def job(link):
            if not self._time_left():
                return link, None
            return link, fetch_article(link)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for link, art in pool.map(job, links):
                if art is not None:
                    results[link] = art
        return results

    # ── indexes ──
    def _reindex(self):
        self.by_url = {}
        self.by_title = {}
        for c in self.clips:
            if c.get("link"):
                self.by_url[normalize_url(c["link"])] = c
            t = norm_title(c.get("title", ""))
            if t:
                self.by_title.setdefault(t, []).append(c)
        self.review_urls = {normalize_url(r.get("link", "")) or r.get("gnews_link", "") for r in self.review}

    def _known_title_domain(self, title, domain, link=""):
        for c in self.by_title.get(norm_title(title), []):
            if domain and extract_domain(c.get("link", "")) == domain:
                return c
        slug = _slug(link)
        if slug and len(slug) >= 25:
            for c in self.clips:
                if extract_domain(c.get("link", "")) == domain and _slug(c.get("link", "")) == slug:
                    return c
        return None

    @staticmethod
    def _add_channel(record, channel):
        via = record.setdefault("found_via", [])
        if channel not in via:
            via.append(channel)

    # ── collection ──
    def collect_daily(self):
        cfg, st = self.cfg, self.state
        cands = []
        feeds = RSS_FEEDS + cfg.get("extra_rss_feeds", [])
        cands += scan_rss(feeds, self.matcher, self.stats, self.own, state=st)
        cands += google_news(cfg.get("gnews_queries", []), self.stats, own_domains=self.own)
        cands += bing_news(cfg.get("bing_queries") or cfg.get("gnews_queries", []), self.stats, own_domains=self.own)
        cands += sitemap_crawl(cfg.get("crawl_outlets", []), st, self.stats,
                               days=cfg.get("crawl_days", 3), skip=self._skip_url, own_domains=self.own)
        if st.due_today("google"):
            budget = CseBudget(cfg.get("google_daily_budget", 90))
            self.cse_budget = budget
            cands += google_cse(cfg["google_queries"], self.stats, budget, self.own, recent_days=30)
            cands += google_cse(cfg.get("page2_queries", []), self.stats, budget, self.own, recent_days=30, first_page=1)
            st.mark_done_today("google")
        if st.due_today("serper"):
            cands += serper(cfg.get("serper_queries") or cfg.get("gnews_queries", []), self.stats, self.own)
            st.mark_done_today("serper")
        if st.due_today("site"):
            cands += site_search(cfg.get("home_outlets", []), cfg.get("site_search_terms", []), st, self.stats, self.matcher, self.own)
            st.mark_done_today("site")
        return cands

    def collect_backfill(self, start, end):
        cfg = self.cfg
        cands = []
        outlets = cfg.get("home_outlets", []) + cfg.get("search_only_outlets", [])
        site_terms = cfg.get("gnews_site_terms", "")
        budget = CseBudget(cfg.get("google_daily_budget", 90))
        self.cse_budget = budget
        for a, b in _month_windows(start, end):
            span = f" after:{a.isoformat()} before:{(b + timedelta(days=1)).isoformat()}"
            cands += google_news([q + span for q in cfg.get("gnews_queries", [])], self.stats, own_domains=self.own)
            if site_terms:
                cands += google_news([f"site:{d} {site_terms}{span}" for d in outlets], self.stats,
                                     editions=GNEWS_EDITIONS[:1], own_domains=self.own)
            cands += google_cse(cfg.get("backfill_google_queries", cfg["google_queries"][:8]), self.stats, budget,
                                self.own, date_range=(a, b))
            cands += serper(cfg.get("serper_queries") or cfg.get("gnews_queries", []), self.stats, self.own, date_range=(a, b))
        cands += site_search(cfg.get("home_outlets", []), cfg.get("site_search_terms", []), self.state, self.stats, self.matcher, self.own)
        return cands

    def _skip_url(self, url):
        key = normalize_url(url)
        return key in self.by_url or self.state.was_checked(key)

    # ── verification ──
    def process(self, cands, syndication_of=None):
        self.counts["candidates"] += len(cands)
        merged, order = {}, []
        for c in cands:
            if c["channel"] == "gnews" and not c.get("link"):
                known = self._known_title_domain(c["title"], c.get("source_domain", ""))
                if known:
                    self._add_channel(known, "gnews")
                    self.counts["already_known"] += 1
                    continue
                key = "gnews:" + norm_title(c["title"]) + "|" + c.get("source_domain", "")
            else:
                key = normalize_url(c["link"])
            if not key:
                continue
            if key in merged:
                m = merged[key]
                m["channels"].add(c["channel"])
                for f in ("date", "snippet", "author", "title"):
                    if not m.get(f) and c.get(f):
                        m[f] = c[f]
                m["needs_text_match"] = m.get("needs_text_match") and c.get("needs_text_match")
                continue
            c = dict(c)
            c["channels"] = {c["channel"]}
            merged[key] = c
            order.append(key)
        self.counts["unique"] += len(order)

        prepared = []
        for key in order:
            if not self._time_left():
                self.out_of_time += 1
                continue
            p = self._prepare(key, merged[key])
            if p:
                prepared.append(p)
        arts = self._fetch_many([p[2] for p in prepared])
        unclear = []
        for key, c, link, channels in prepared:
            if key in self.by_url or self.state.was_checked(key):
                if key in self.by_url:
                    for ch in channels:
                        self._add_channel(self.by_url[key], ch)
                continue  # same article reached twice in this batch
            if link not in arts:
                self.out_of_time += 1  # not loaded in time: stays unchecked, next run picks it up
                continue
            outcome = self._decide(key, c, link, channels, arts[link], syndication_of)
            if outcome and outcome[0] == "check":
                unclear.append(outcome[1])
        if unclear:
            decisions = self.validator.decide(unclear)
            for item, (decision, reason) in zip(unclear, decisions):
                if decision == "accept":
                    item["verified"] = "claude"
                    self._accept(item)
                elif decision == "reject":
                    self.rejected.append({"link": item["link"], "title": item["title"], "reason": "Claude: " + reason})
                    self.state.mark_checked(item["key"], "rejected")
                else:
                    self._to_review(item, "unklar: " + reason)

    def _prepare(self, key, c):
        """Dedup, state and Google News link resolution. Returns (key, c, link, channels) or None."""
        channels = sorted(c["channels"])
        if key in self.by_url:
            for ch in channels:
                self._add_channel(self.by_url[key], ch)
            self.counts["already_known"] += 1
            return None
        if key in self.review_urls:
            return None
        if self.state.was_checked(key):
            self.counts["already_checked"] += 1
            return None

        link = c.get("link", "")
        if not link and c.get("gnews_link"):
            link = resolve_google_news(c["gnews_link"])
            if not link:
                self.counts["gnews_unresolved"] += 1
                fails = self.state.data.setdefault("gnews_fail", {})
                fails[key] = fails.get(key, 0) + 1
                if fails[key] < 3:
                    return None  # try again next run
                fails.pop(key, None)
                item = self._item(key, c, link=c["gnews_link"], channels=channels)
                item["people"] = self.matcher.analyse(c["title"], c.get("snippet", ""))["people"]
                self._to_review(item, "Google-News-Link nicht auflösbar, Fundstelle bitte prüfen")
                return None
            self.state.mark_checked(key, "resolved")
            nkey = normalize_url(link)
            if nkey in self.by_url:
                for ch in channels:
                    self._add_channel(self.by_url[nkey], ch)
                self.counts["already_known"] += 1
                return None
            if self.state.was_checked(nkey) or nkey in self.review_urls:
                self.counts["already_checked"] += 1
                return None
            key = nkey

        return key, c, link, channels

    def _decide(self, key, c, link, channels, art, syndication_of):
        item = self._item(key, c, link=link, channels=channels)
        if syndication_of:
            item["syndication_of"] = syndication_of
        src_analysis = self.matcher.analyse(c.get("title", ""), c.get("snippet", ""), c.get("author", ""))

        if art.get("ok"):
            self.counts["fetched"] += 1
            if art.get("title") and (not c.get("title") or c["channel"] in ("sitemap", "site")):
                item["title"] = art["title"]
            item["title"] = clean_title(item["title"], " ".join([art.get("sitename", ""), extract_domain(link), c.get("source", "")]))
            item["author"] = art.get("author") or c.get("author", "")
            item["sitename"] = art.get("sitename", "")
            item["page_date"] = art.get("date", "")
            item["text"] = art.get("text", "")
            analysis = self.matcher.analyse(item["title"], item["text"] + " " + art.get("meta_text", ""), item["author"])
            item["verified"] = "volltext"
            if analysis["decision"] == "none":
                page_text = art.get("page_text", "")
                if syndication_of and self._same_title(art.get("title") or item["title"], c.get("orig_title", "")):
                    analysis = {"decision": "accept", "people": [], "byline": False, "brand": False}
                    item["verified"] = "titelgleich"
                elif ("rss" in channels or "site" in channels) and src_analysis["decision"] != "none":
                    analysis = src_analysis  # name in the feed entry or archive text itself (author line, body)
                    item["verified"] = "feed" if "rss" in channels else "archiv"
                elif self.matcher.mentions_any(page_text):
                    analysis = self.matcher.analyse(item["title"], page_text, item["author"])
                    analysis["decision"] = "check"  # outside the main text: author box or sidebar?
                    item["text"] = page_text
                    item["verified"] = "seite"
                elif src_analysis["decision"] != "none" and any(ch in SEARCH_CHANNELS for ch in channels):
                    analysis = dict(src_analysis, decision="check")  # paywall or teaser only
                    item["verified"] = "suchausschnitt"
                else:
                    self.counts["no_match"] += 1
                    self.state.mark_checked(key, "nomatch")
                    return None
        else:
            self.counts["fetch_failed"] += 1
            self.stats.note("fetch", f"{extract_domain(link)}: {art.get('error')}", limit=60)
            analysis = src_analysis
            reliable = "rss" in channels or "site" in channels
            item["verified"] = ("feed" if "rss" in channels else "archiv") if reliable else "suchausschnitt"
            transient = art.get("status") in (None, 403, 408, 425, 429, 500, 502, 503, 504) or art.get("status", 0) >= 500
            if analysis["decision"] == "none":
                if syndication_of:
                    analysis = {"decision": "check", "people": [], "byline": False, "brand": False}
                elif transient and self._retry_later(key):
                    return None  # blocked or overloaded right now: try again next run
                else:
                    self.state.mark_checked(key, "unreadable")
                    return None
            elif analysis["decision"] == "accept" and not reliable:
                analysis["decision"] = "check"  # only a search snippet, page not readable: Claude confirms

        item["people"] = analysis.get("people", [])
        item["byline"] = analysis.get("byline", False)
        lang = detect_language(item.get("text") or "")
        item["language"] = lang
        if lang == "fr":
            self.rejected.append({"link": link, "title": item["title"], "reason": "französisch (Romandie-Regel)"})
            self.state.mark_checked(key, "rejected-fr")
            return None
        if lang == "en":
            self._to_review(item, "englischsprachig: zählt das? (Regel offen)")
            return None
        url_l = link.lower()
        if any(re.search(pat, url_l) for pat in self.cfg.get("blocked_url_patterns", [])):
            self.rejected.append({"link": link, "title": item["title"], "reason": "Kurs- oder Datenseite, kein Artikel"})
            self.state.mark_checked(key, "rejected-datapage")
            return None
        if self._too_old(item):
            self.state.mark_checked(key, "too-old")
            self.counts["too_old"] = self.counts.get("too_old", 0) + 1
            return None
        if re.search(r"ist (\w+ )?erschienen|neue ausgabe|newsletter|pressespiegel|presse ?digest|inhaltsverzeichnis",
                     norm_text(item["title"]) + " " + url_l):
            self._to_review(item, "Hinweis auf Heft, Newsletter oder Pressespiegel: eigenes Clipping?")
            return None
        if analysis["decision"] == "accept":
            self._accept(item)
            return None
        return ("check", item)

    @staticmethod
    def _same_title(a, b):
        a, b = norm_title(a), norm_title(b)
        return bool(a and b) and (a == b or (len(b) >= 25 and b in a))

    def _item(self, key, c, link, channels):
        return {"key": key, "link": link, "title": c.get("title", ""), "snippet": c.get("snippet", ""),
                "source": c.get("source", ""), "feed_date": c.get("date", ""), "author": c.get("author", ""),
                "channels": channels, "gnews_link": c.get("gnews_link", ""), "query": c.get("query", ""),
                "source_domain": c.get("source_domain", "")}

    def _retry_later(self, key, attempts=3):
        fails = self.state.data.setdefault("fetch_fail", {})
        fails[key] = fails.get(key, 0) + 1
        if fails[key] < attempts:
            return True
        fails.pop(key, None)
        return False

    def _best_date(self, item):
        for d, src in ((item.get("page_date"), "seite"), (item.get("feed_date"), "quelle"),
                       (date_from_url(item.get("link", "")), "url")):
            d = iso_date(d)
            if plausible_date(d, earliest="2000-01-01"):
                return d, src
        return "", ""

    def _too_old(self, item):
        earliest = self.cfg.get("earliest_date")
        d, _ = self._best_date(item)
        return bool(earliest and d and d < earliest)

    def _accept(self, item):
        link = item["link"]
        domain = extract_domain(link)
        title = item["title"].strip()
        same = self._known_title_domain(title, domain, link)
        if same:  # same article under another URL of the same outlet
            for ch in item["channels"]:
                self._add_channel(same, ch)
            self.state.mark_checked(item["key"], "duplicate")
            return
        outlet = normalize_outlet(item.get("sitename") or item.get("source") or "", link)
        d, dsrc = self._best_date(item)
        clip = {
            "date": d,
            "outlet": outlet,
            "title": title,
            "country": guess_country(outlet, link),
            "type": "Online",
            "tier": guess_tier(outlet, link, self.cfg.get("extra_tier1_keywords", [])),
            "link": link,
            "people": item.get("people", []),
            "byline": bool(item.get("byline")),
            "author": item.get("author", "")[:120],
            "found_via": list(item["channels"]),
            "verified": item.get("verified", ""),
            "date_source": dsrc,
            "added_at": datetime.now().isoformat(timespec="seconds"),
            "source": "auto",
            "id": f"a-{int(datetime.now().timestamp())}-{len(self.new)}",
        }
        twins = [c for c in self.by_title.get(norm_title(title), []) if extract_domain(c.get("link", "")) != domain]
        if item.get("syndication_of"):
            clip["syndication_of"] = item["syndication_of"]
        elif twins:
            clip["syndication_of"] = twins[0].get("id", "")
        self.clips.append(clip)
        self.new.append(clip)
        self.by_url[normalize_url(link)] = clip
        self.by_title.setdefault(norm_title(title), []).append(clip)
        self.state.mark_checked(item["key"], "accepted")
        if normalize_url(link) != item["key"]:
            self.state.mark_checked(normalize_url(link), "accepted")

    def _to_review(self, item, reason):
        if item["key"] in self.review_urls:
            return
        d, _ = self._best_date(item)
        entry = {"link": item["link"], "title": item["title"], "outlet": normalize_outlet(item.get("sitename") or item.get("source", ""), item["link"]),
                 "date": d, "people": item.get("people", []), "reason": reason, "found_via": item["channels"],
                 "snippet": item.get("snippet", "")[:300], "added_at": datetime.now().isoformat(timespec="seconds")}
        self.review.append(entry)
        self.new_review.append(entry)
        self.review_urls.add(item["key"])
        self.state.mark_checked(item["key"], "review")

    # ── syndication ──
    def syndication_search(self, clips):
        """Search each clipping's exact title to find copies on other outlets."""
        batches = []
        for clip in clips:
            title = clip.get("title", "")
            if len(norm_title(title)) < 20:
                continue
            q = f'"{title}"'
            found = google_news([q], self.stats, own_domains=self.own)
            budget = getattr(self, "cse_budget", None)
            if budget and budget.available():
                found += google_cse([q], self.stats, budget, self.own, recent_days=365)
            origin_domain = extract_domain(clip.get("link", ""))
            keep = []
            for f in found:
                dom = extract_domain(f.get("link", "")) or f.get("source_domain", "")
                if dom and dom == origin_domain:
                    continue
                if not self._same_title(f["title"], title):
                    continue
                f = dict(f, channel="syndication", orig_title=title)
                keep.append(f)
            if keep:
                batches.append((clip.get("id", ""), keep))
        for origin, cands in batches:
            self.process(cands, syndication_of=origin)

    # ── review decisions (data/review_decisions.csv: link;entscheidung) ──
    def apply_review_decisions(self):
        """Apply ja/nein decisions on review entries, then clear the processed lines."""
        import csv
        path = data_path(self.cfg).parent / "review_decisions.csv"
        if not path.exists():
            if not self.dry_run:
                path.write_text("link;entscheidung\n", encoding="utf-8")
            return
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, delimiter=";"))
        keep, applied = [], 0
        for row in rows:
            link = (row.get("link") or "").strip()
            dec = (row.get("entscheidung") or "").strip().lower()
            entry = next((r for r in self.review if normalize_url(r.get("link", "")) == normalize_url(link)), None)
            if not link or dec not in ("ja", "nein") or not entry:
                if link:
                    keep.append(row)
                continue
            self.review.remove(entry)
            key = normalize_url(link)
            if dec == "ja":
                item = {"key": key, "link": link, "title": entry.get("title", ""), "source": entry.get("outlet", ""),
                        "feed_date": entry.get("date", ""), "channels": entry.get("found_via", []),
                        "people": entry.get("people", []), "verified": "manuell geprüft", "author": ""}
                self._accept(item)
            else:
                self.rejected.append({"link": link, "title": entry.get("title", ""), "reason": "manuell abgelehnt"})
                self.state.mark_checked(key, "rejected-manual")
            applied += 1
        self.counts["review_decisions"] = applied
        if not self.dry_run:
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["link", "entscheidung"], delimiter=";", extrasaction="ignore")
                w.writeheader()
                w.writerows(keep)
        self._reindex()

    # ── enrich existing clippings (speakers, byline) ──
    def enrich(self, force=False, limit=None):
        """Fetch stored clippings once and add people/byline. Never changes date, outlet or title."""
        done = tried = 0
        for clip in self.clips:
            if ("people" in clip and not force) or not clip.get("link"):
                continue
            if (limit is not None and tried >= limit) or not self._time_left():
                break
            tried += 1
            art = fetch_article(clip["link"])
            if not art.get("ok"):
                self.stats.note("fetch", f"{extract_domain(clip['link'])}: {art.get('error')}", limit=60)
                clip.setdefault("people", [])
                clip["people_checked"] = "seite nicht lesbar"
                continue
            text = art.get("text", "") + " " + art.get("meta_text", "")
            a = self.matcher.analyse(clip.get("title", ""), text, art.get("author", ""))
            if not a["people"] and self.matcher.mentions_any(art.get("page_text", "")):
                a = self.matcher.analyse(clip.get("title", ""), art.get("page_text", ""), art.get("author", ""))
            clip["people"] = a["people"]
            clip["byline"] = a["byline"]
            if art.get("author") and not clip.get("author"):
                clip["author"] = art["author"][:120]
            done += 1
        self.counts["enriched"] = done

    # ── run ──
    def run(self, mode="daily", start=None, end=None):
        started = datetime.now()
        budget_min = self.cfg.get("time_budget_minutes", {}).get(mode, 45 if mode == "daily" else 150)
        self.deadline = time.time() + budget_min * 60
        self.apply_review_decisions()
        if mode == "enrich":
            self.enrich()
            if not self.dry_run:
                save_json(data_path(self.cfg), self.clips)
            return [], write_report(self, mode, started, {})
        if mode == "backfill":
            cands = self.collect_backfill(start, end)
        else:
            cands = self.collect_daily()
        self.process(cands)
        first_wave = list(self.new)
        if mode == "backfill":
            targets = [c for c in self.clips if start.isoformat() <= c.get("date", "") <= end.isoformat()]
        else:
            targets = first_wave
        self.syndication_search(targets)

        if mode == "daily":
            self.enrich(limit=40)  # gradually add speakers to older clippings

        from placements import update_placements
        placement_report = update_placements(self.cfg, self.clips, dry_run=self.dry_run)

        if not self.dry_run:
            self.clips.sort(key=lambda x: x.get("date", ""), reverse=True)
            save_json(data_path(self.cfg), self.clips)
            save_json(review_path(self.cfg), self.review)
            self.state.save()
        self.counts["deferred"] = self.out_of_time
        report = write_report(self, mode, started, placement_report)
        return self.new, report


def run_search(cfg, mode="daily", start=None, end=None, dry_run=False):
    agent = Agent(cfg, dry_run=dry_run)
    new, report = agent.run(mode, start, end)
    return new
