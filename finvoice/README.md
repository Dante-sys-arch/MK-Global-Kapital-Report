# FinVoice — LinkedIn-Ghostwriting-Autopilot für Finanz-Führungskräfte

Neues, eigenständiges Produkt (bewusst kein Monitoring, kein Versand — nichts,
was es in den bestehenden Repos schon gibt): Der Agent sammelt jede Woche die
relevanten Branchennachrichten, schreibt daraus **LinkedIn-Post-Entwürfe in der
Stimme des jeweiligen CEOs** und stellt sie auf einer privaten Redaktionsseite
bereit. Redigiert wird von Hand, veröffentlicht vom Kunden selbst — es wird
**nichts automatisch gepostet**.

**→ Siehe [GESCHAEFTSPLAN.md](GESCHAEFTSPLAN.md) für den Weg zu 10.000 € in 6 Monaten
(5 Kunden à 590 €/Monat, gleiche Zielgruppe wie das Clipping — Cross-Selling).**

## Funktionsweise

1. **Sammeln** (`collect.py`): Themenrelevante RSS-Feeds des Kunden, letzte 7 Tage,
   nach Keyword-Relevanz bewertet → die 8 besten Aufhänger der Woche
2. **Schreiben** (`generate.py`): Claude erzeugt 3 Post-Entwürfe in der Tonalität
   des Kunden (Stilproben als Few-Shot), unterschiedliche Formate (These,
   Einordnung, Liste, Frage, Erfahrung), inkl. Redaktionsnotiz pro Post
3. **Bereitstellen** (`review_page.py`): Private HTML-Seite pro Kunde mit allen
   Wochen und Kopieren-Button (`finvoice/docs/<slug>/index.html`)
4. **Zeitplan**: Montags 06:00 Uhr automatisch via GitHub Actions
   (`.github/workflows/finvoice.yml`)

## Kunden verwalten

Jeder Kunde ist eine JSON-Datei in `finvoice/clients/`
(Vorlage: `clients/beispiel-ceo.json.example`).

```bash
python finvoice/src/new_client.py "Dr. Max Berger" \
  --company "Berger Capital AG" --role CEO \
  --topics "Sachwerte, Zinswende, Private Markets" \
  --keywords "zinsen, immobilienfonds, private equity" \
  --feeds "https://www.dasinvestment.com/feed/" "https://www.institutional-money.com/rss/news/"
```

Danach die drei wichtigsten Felder in der JSON von Hand füllen:

- **`voice_samples`** — 2–3 echte LinkedIn-Posts des Kunden (entscheidend für den Ton)
- **`positions`** — Kernthesen, die der Kunde öffentlich vertritt
- **`avoid`** — Tabuthemen (Politik, Wettbewerber, Produktempfehlungen …)

## Agent ausführen

```bash
pip install -r finvoice/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

python finvoice/src/main.py                      # alle Kunden
python finvoice/src/main.py --client max-berger  # ein Kunde
python finvoice/src/main.py --render-only        # nur Redaktionsseiten neu bauen
```

Benötigt nur `ANTHROPIC_API_KEY` (ist als Repo-Secret bereits vorhanden) —
keine Google-Keys, keine weiteren Dienste.

## Dateien

```
finvoice/
├── GESCHAEFTSPLAN.md            # Preismodell + Weg zu 10.000 € in 6 Monaten
├── requirements.txt
├── clients/
│   └── beispiel-ceo.json.example
├── src/
│   ├── main.py                  # Orchestrierung (alle Kunden / --client)
│   ├── client_config.py         # Kunden-Konfigurationen laden
│   ├── new_client.py            # Kunden-Onboarding (2 Minuten)
│   ├── collect.py               # RSS-Aufhänger der Woche sammeln
│   ├── generate.py              # Claude: Post-Entwürfe im Kundenton
│   └── review_page.py           # private Redaktionsseite pro Kunde
├── data/<kunde>/<woche>.json    # generierte Entwürfe (Archiv)
└── docs/<kunde>/index.html      # Redaktionsseite (Kopieren-Button)
```

## Wichtig, bevor Geld fließt

- **Vor dem ersten zahlenden Kunden in ein privates Repo umziehen** — Stimmprofile
  und Entwürfe sind vertraulich. Der Ordner ist eigenständig und lässt sich 1:1
  in ein neues Repo kopieren (nur den Workflow mitnehmen).
- Jeder Entwurf wird **redigiert, bevor er den Kunden erreicht** — Details und
  Compliance-Regeln im [GESCHAEFTSPLAN.md](GESCHAEFTSPLAN.md).
