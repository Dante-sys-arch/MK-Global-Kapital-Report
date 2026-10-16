"""
Claude decides the unclear cases only: names that other people also carry,
pages that could not be loaded (paywall, bot protection) and hits that appear
only in a search snippet. Claude never sets dates, outlets or titles.
If Claude is unavailable, every unclear case goes to the review list.
"""
import json
import os
import re

DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM = """Du prüfst Medienfundstellen für das Clipping-Reporting von {name}.
Zu {name} gehören diese Personen: {people}.
Es gibt Namensvettern, zum Beispiel einen Edeka-Marktleiter namens Johannes Feist. Nur Fundstellen über die Personen in ihrer Rolle bei {name} zählen.

Für jede Fundstelle bekommst du Titel, Medium, URL, Suchausschnitt und, wenn vorhanden, Textstellen aus dem Artikel.
Entscheide:
- "accept": Der Artikel erwähnt {name} oder eine der Personen in dieser Rolle (Zitat, Interview, Gastbeitrag, Erwähnung).
- "reject": Namensvetter, anderes Thema, nur Werbung, nur Link in einer Seitenleiste oder Linkliste, Stellenanzeige, Firmenprofil-Datenbank.
- "unsure": Aus den Angaben nicht sicher zu entscheiden.

Antworte ausschließlich mit einem JSON-Array, ein Objekt pro Fundstelle:
[{{"i": 1, "decision": "accept|reject|unsure", "reason": "kurz"}}]"""


def _excerpts(text, terms, width=260, limit=3):
    low = (text or "").lower()
    found = []
    for term in terms:
        for m in re.finditer(re.escape(term), low):
            a, b = max(0, m.start() - width), min(len(text), m.end() + width)
            found.append(text[a:b].replace("\n", " "))
            if len(found) >= limit:
                return found
    return found


class Validator:
    def __init__(self, cfg, matcher, stats):
        self.cfg = cfg
        self.matcher = matcher
        self.stats = stats
        self.model = cfg.get("validation_model") or os.environ.get("CLAUDE_MODEL") or DEFAULT_MODEL
        self.client = None
        key = os.environ.get("ANTHROPIC_API_KEY")
        if key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=key)
            except Exception as exc:
                stats.note("claude", f"Client-Start fehlgeschlagen: {type(exc).__name__}")
        else:
            stats.note("claude", "kein ANTHROPIC_API_KEY")

    def decide(self, items):
        """items: list of dicts with title, outlet, link, snippet, text. Returns list of (decision, reason)."""
        if not items:
            return []
        if not self.client:
            return [("unsure", "Claude nicht verfügbar")] * len(items)
        people = ", ".join(p["name"] for p in self.matcher.people)
        system = SYSTEM.format(name=self.cfg["name"], people=people)
        terms = self.matcher.terms()
        results = []
        for start in range(0, len(items), 12):
            batch = items[start:start + 12]
            blocks = []
            for n, it in enumerate(batch, 1):
                ex = _excerpts(it.get("text", ""), terms)
                blocks.append(
                    f"{n}. Titel: {it.get('title','')}\n   Medium: {it.get('outlet','')}\n   URL: {it.get('link','')}\n"
                    f"   Suchausschnitt: {it.get('snippet','')[:400]}\n"
                    + ("".join(f"   Textstelle: {e}\n" for e in ex) if ex else "   Textstellen: (Seite nicht lesbar oder Name nicht im Haupttext)\n")
                )
            st = self.stats.ch("claude")
            st["requests"] += 1
            try:
                resp = self.client.messages.create(
                    model=self.model, max_tokens=2000, system=system,
                    messages=[{"role": "user", "content": "\n".join(blocks)}],
                )
                text = "".join(getattr(b, "text", "") for b in resp.content)
                match = re.search(r"\[[\s\S]*\]", text)
                parsed = json.loads(match.group(0)) if match else []
                by_i = {int(p.get("i", 0)): p for p in parsed if isinstance(p, dict)}
                st["ok"] += 1
                for n in range(1, len(batch) + 1):
                    p = by_i.get(n)
                    if p and p.get("decision") in ("accept", "reject", "unsure"):
                        results.append((p["decision"], p.get("reason", "")))
                    else:
                        results.append(("unsure", "keine Antwort von Claude zu diesem Eintrag"))
            except Exception as exc:
                st["errors"] += 1
                self.stats.note("claude", f"{type(exc).__name__}: {str(exc)[:160]}")
                results.extend([("unsure", "Claude-Fehler")] * len(batch))
        return results


EXTRACT_SYSTEM = """Du liest Medienbelege für das Clipping-Reporting von {name} aus.
Zu {name} gehören diese Personen: {people}.
Die Vorlage kann ein Screenshot, ein PDF (z. B. E-Paper-Seite, Pressespiegel), eine Trefferliste eines Medienbeobachters
(z. B. PMG, Argus, Landau) oder ein frei eingegebener Text sein.

Gib jeden einzelnen Artikel als eigenes Objekt zurück. Nur Artikel, die {name} oder eine der Personen erwähnen.
Bei Trefferlisten eines Medienbeobachters gehört jede Zeile, die einen Artikel beschreibt, dazu.
Erfinde nichts: Felder, die nicht erkennbar sind, bleiben leer.

Antworte ausschließlich mit einem JSON-Array:
[{{"date": "YYYY-MM-DD", "outlet": "Medienname", "title": "Artikeltitel", "medium": "Print|E-Paper|Online",
   "link": "URL oder leer", "country": "D|CH|A oder leer", "people": ["Namen der genannten Personen"],
   "note": "Seite, Ausgabe oder Auffälliges, sonst leer"}}]
Keine Artikel erkennbar? Antworte: []"""


def _extract_json_list(text):
    match = re.search(r"\[[\s\S]*\]", text or "")
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict) and (d.get("title") or d.get("link"))]


def extract_clippings(validator, blocks):
    """blocks: Anthropic content blocks (text, image, document). Returns (items, error)."""
    if not validator.client:
        return [], "Claude nicht verfügbar"
    people = ", ".join(p["name"] for p in validator.matcher.people)
    system = EXTRACT_SYSTEM.format(name=validator.cfg["name"], people=people)
    st = validator.stats.ch("claude")
    st["requests"] += 1
    try:
        resp = validator.client.messages.create(model=validator.model, max_tokens=8000, system=system,
                                                messages=[{"role": "user", "content": blocks}])
        st["ok"] += 1
        return _extract_json_list("".join(getattr(b, "text", "") for b in resp.content)), ""
    except Exception as exc:
        st["errors"] += 1
        validator.stats.note("claude", f"Auslesen: {type(exc).__name__}: {str(exc)[:160]}")
        return [], f"Claude-Fehler: {type(exc).__name__}"
