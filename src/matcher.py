"""
Decides from text whether an article is about the client.

Works on the normalized article text (title, author, main text). A hit on a
unique name (brand, rare person name) is accepted directly. Names that other
people also carry (e.g. "Johannes Feist", an Edeka store manager) need finance
context in the same text, otherwise the case goes to Claude or the review list.
"""
import re

from util import norm_text

DEFAULT_CONTEXT_TERMS = [
    "mikrofinanz", "microfinance", "private credit", "private debt", "impact",
    "emerging markets", "schwellenl", "anleihe", "kredit", "fonds", "investor",
    "anleger", "rendite", "tokenis", "kapitalmarkt", "asset manag", "vermögensverwalt",
    "ceo", "chief", "kmu", "finanz", "bank",
]

_DE = {"der", "die", "und", "das", "nicht", "ist", "mit", "für", "auf", "von", "den", "sich", "im", "zu", "eine", "auch", "wird", "bei"}
_FR = {"le", "la", "les", "et", "des", "est", "pour", "dans", "une", "du", "que", "sur", "pas", "au", "aux", "qui", "avec"}
_EN = {"the", "and", "of", "to", "is", "in", "for", "with", "that", "on", "are", "as", "this", "by", "from", "be"}


def detect_language(text):
    words = re.findall(r"[a-zäöüéèàçâêîôû]+", (text or "").lower()[:4000])
    if len(words) < 25:
        return ""
    scores = {
        "de": sum(w in _DE for w in words),
        "fr": sum(w in _FR for w in words),
        "en": sum(w in _EN for w in words),
    }
    lang, best = max(scores.items(), key=lambda kv: kv[1])
    return lang if best >= 3 else ""


class Matcher:
    def __init__(self, cfg):
        people = cfg.get("people") or []
        if not people:
            # Older client configs: derive from keywords.
            people = [{"name": k.title(), "variants": [k]} for k in cfg.get("keywords", []) if " " in k]
        self.people = []
        for p in people:
            variants = [norm_text(v) for v in (p.get("variants") or [p["name"]])]
            self.people.append({
                "name": p["name"],
                "variants": variants,
                "ambiguous": bool(p.get("ambiguous")),
                "spokesperson": bool(p.get("spokesperson")),
                "requires_brand": bool(p.get("requires_brand")),
                "exclude": [norm_text(x) for x in p.get("exclusion_terms", [])],
            })
        brands = cfg.get("brand_terms") or [k for k in cfg.get("keywords", []) if not any(
            k in v for p in self.people for v in p["variants"])]
        self.brands = [norm_text(b) for b in brands]
        self.weak_brands = [norm_text(b) for b in cfg.get("ambiguous_brand_terms", [])]
        self.context = [norm_text(c) for c in cfg.get("context_terms", DEFAULT_CONTEXT_TERMS)]
        self.exclusions = [norm_text(x) for x in cfg.get("exclusion_terms", [])]

    def focus(self, text, width=300):
        """Excerpt of the original text around the first client name, else its beginning."""
        text = text or ""
        if not hasattr(self, "_rx"):
            parts = [r"[\s\-_\u00a0]+".join(re.escape(w) for w in t.split()) for t in self.terms() if t]
            self._rx = re.compile("|".join(parts), re.I) if parts else None
        m = self._rx.search(text) if self._rx else None
        if not m:
            return text[: 2 * width]
        a, b = max(0, m.start() - width), min(len(text), m.end() + width)
        return text[a:b]

    # All search strings, used as cheap pre-filter on feeds and snippets.
    def terms(self):
        out = list(self.brands) + list(self.weak_brands)
        for p in self.people:
            out.extend(p["variants"])
        return out

    def mentions_any(self, text):
        t = norm_text(text)
        return any(term in t for term in self.terms())

    def analyse(self, title="", text="", author=""):
        """Return dict: decision ('accept'|'check'|'none'), people, brand, byline, reasons."""
        full = norm_text(" ".join([title or "", author or "", text or ""]))
        author_n = norm_text(author or "")
        brand_hit = [b for b in self.brands if b in full]
        weak_hit = [b for b in self.weak_brands if b in full]
        people_hit, unique_people, ambiguous_people, brand_only_people = [], [], [], []
        excluded = [x for x in self.exclusions if x in full]
        for p in self.people:
            if any(v in full for v in p["variants"]):
                people_hit.append(p["name"])
                person_excl = [x for x in p["exclude"] if x in full]
                if person_excl:  # namesake signal (e.g. Edeka): never accept directly, let Claude decide
                    excluded.extend(person_excl)
                    ambiguous_people.append(p["name"])
                elif p["requires_brand"]:
                    brand_only_people.append(p["name"])
                else:
                    (ambiguous_people if p["ambiguous"] else unique_people).append(p["name"])
        has_context = any(c in full for c in self.context)

        result = {
            "people": people_hit,
            "brand": bool(brand_hit),
            "byline": self._byline(people_hit, author_n, norm_text(text or "")),
            "reasons": [],
        }
        if brand_hit:
            result["decision"] = "accept"
            result["reasons"].append("brand:" + brand_hit[0])
        elif unique_people:
            result["decision"] = "accept"
            result["reasons"].append("person:" + unique_people[0])
        elif ambiguous_people and has_context and not excluded:
            result["decision"] = "accept"
            result["reasons"].append("person+context:" + ambiguous_people[0])
        elif ambiguous_people or weak_hit or brand_only_people:
            result["decision"] = "check"
            result["reasons"].append("ambiguous:" + (ambiguous_people or weak_hit or brand_only_people)[0]
                                     + (" excluded:" + excluded[0] if excluded else ""))
        else:
            result["decision"] = "none"
        return result

    def _byline(self, people_hit, author_n, text_n):
        """True if one of the found people is the author (guest article, commentary)."""
        for p in self.people:
            if p["name"] not in people_hit:
                continue
            for v in p["variants"]:
                if v in author_n:
                    return True
                head = text_n[:400]
                if re.search(r"(gastbeitrag|gastkommentar|kommentar|ein beitrag|autor(in)?|von)\s+(dr\s?\.?\s+)?" + re.escape(v), head):
                    return True
                tail = text_n[-700:]
                if re.search(re.escape(v) + r"\s*(,|ist|\(|–|-)\s*(dr\s?\.?\s+)?(ceo|chief|vorstand|ceo und|managing|member|mitglied|leiter|head)", tail):
                    return True
        return False
