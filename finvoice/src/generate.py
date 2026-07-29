"""
FinVoice — Entwurfsgenerierung.

Erzeugt aus den gesammelten Aufhängern der Woche LinkedIn-Post-Entwürfe
in der Stimme des Kunden. Ausgabe ist bewusst ein ENTWURF: Der Betreiber
redigiert jeden Post (10–15 Min.), bevor er an den Kunden geht.
"""
import json
import os
import re

import anthropic

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

FORMATS = [
    "These (pointierte Meinung mit Begründung)",
    "Einordnung (was eine aktuelle Nachricht für die Branche bedeutet)",
    "Liste (3–5 knappe Lehren oder Beobachtungen)",
    "Frage (Diskussionsanstoß mit eigener Position)",
    "Erfahrung (kurze Anekdote aus der Praxis mit Schlussfolgerung)",
]

SYSTEM_PROMPT = """Du bist Ghostwriter für Führungskräfte der Finanzbranche im DACH-Raum.
Du schreibst LinkedIn-Post-ENTWÜRFE, die ein menschlicher Redakteur nachbearbeitet.

Regeln:
- Schreibe in der Ich-Perspektive der Führungskraft, in ihrer Tonalität (siehe Stilproben).
- 600–1.200 Zeichen pro Post. Erste Zeile muss ohne "Mehr anzeigen" neugierig machen.
- Konkret statt generisch: Zahlen, Beispiele, klare Position. Keine Buzzword-Ketten.
- KEINE Anlageberatung, KEINE Produktwerbung, KEINE Renditeversprechen —
  Thought Leadership, nicht Vertrieb. Regulierte Häuser: kein Bezug auf konkrete Wertpapiere.
- Keine Emojis-Flut (max. 1–2, nur wenn die Stilproben welche enthalten).
- 3–5 passende Hashtags ans Ende.
- Meide die Tabuthemen des Kunden strikt.
Antworte ausschließlich mit validem JSON."""


def _build_prompt(client: dict, hooks: list[dict]) -> str:
    n = client["posts_per_week"]
    voice = "\n\n---\n\n".join(client.get("voice_samples", [])) or "(keine Stilproben hinterlegt — neutraler, souveräner Ton)"
    positions = "\n".join(f"- {p}" for p in client.get("positions", [])) or "- (keine hinterlegt)"
    avoid = ", ".join(client.get("avoid", [])) or "(keine)"
    hooks_text = "\n\n".join(
        f"[{i+1}] {h['title']} ({h['source']}, {h['date']})\n{h['summary']}\nLink: {h['link']}"
        for i, h in enumerate(hooks)
    ) or "(diese Woche keine Feed-Treffer — schreibe zeitlose Posts zu den Kernthemen)"

    return f"""Kunde: {client['name']}, {client['role']} bei {client['company']}
Sprache: {"Deutsch" if client['language'] == 'de' else client['language']}
Kernthemen: {", ".join(client['topics'])}
Kernpositionen des Kunden:
{positions}
Tabuthemen: {avoid}

Stilproben (echte Posts des Kunden, Ton exakt treffen):
{voice}

Aktuelle Aufhänger dieser Woche:
{hooks_text}

Aufgabe: Schreibe genau {n} LinkedIn-Post-Entwürfe. Nutze unterschiedliche Formate
({"; ".join(FORMATS)}) und unterschiedliche Aufhänger. Mindestens ein Post darf
zeitlos sein (ohne Nachrichtenbezug).

Antworte als JSON-Array mit genau {n} Objekten:
[{{"format": "...", "hook_title": "..." oder null, "hook_link": "..." oder null,
  "post": "kompletter Post-Text inkl. Hashtags",
  "redaktionsnotiz": "1 Satz: was der Redakteur prüfen/persönlich ergänzen sollte"}}]"""


def generate_drafts(client: dict, hooks: list[dict]) -> list[dict]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY ist nicht gesetzt")
    response = anthropic.Anthropic(api_key=api_key).messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(client, hooks)}],
    )
    text = response.content[0].text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"Keine JSON-Antwort erhalten:\n{text[:500]}")
    drafts = json.loads(match.group(0))
    for d in drafts:
        d.setdefault("format", "These")
        d.setdefault("redaktionsnotiz", "")
    return drafts
