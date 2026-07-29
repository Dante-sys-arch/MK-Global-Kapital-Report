# PressRadar DACH — Medien-Clipping-Agent (Multi-Kunden)

Automatischer Medien-Clipping-Agent für den DACH-Raum. Durchsucht täglich
deutschsprachige Medien (60+ RSS-Feeds + Google-Suche), validiert Treffer per
KI und generiert pro Kunde einen Excel-Report.

Ursprünglich gebaut für **MK Global Kapital** (erster Kunde, läuft unverändert
weiter) — jetzt als Mehrkunden-Produkt, das sich als Service verkaufen lässt.
**→ Siehe [GESCHAEFTSPLAN.md](GESCHAEFTSPLAN.md) für den Weg zu 10.000 € in 6 Monaten.**
**→ Verkaufsseite: [docs/produkt.html](docs/produkt.html) (via GitHub Pages).**

## Funktionsweise

1. **RSS-Scan**: 60+ deutschsprachige Finanz-/Wirtschaftsmedien (kostenlos, unbegrenzt)
2. **Google-Suche**: Web- + News-Queries via Google Custom Search API
3. **KI-Validierung**: Claude prüft jeden Treffer (keine Namensvetter, keine Werbung)
4. **Deduplizierung**: Neue Artikel werden gegen bestehende geprüft (URL + Titel/Medium)
5. **Tier-Zuordnung**: Tier 1 (Leitmedien) / Tier 2 (übrige Medien)
6. **Excel-Report**: Pro Kunde, mit Analysis-Sheet und Charts
7. **Commit**: Ergebnisse werden automatisch ins Repository committed

## Kunden verwalten

Jeder Kunde ist eine JSON-Datei in `clients/` (Vorlage: `clients/beispiel-kunde.json.example`).

**Neuen Kunden anlegen (2 Minuten):**

```bash
python src/new_client.py "Acme Invest GmbH" \
  --keywords "acme invest, peter mustermann" \
  --people "Peter Mustermann (CEO)" \
  --industry "Immobilienfonds, Sachwerte"
```

**Agent ausführen:**

```bash
python src/main.py                          # alle Kunden
python src/main.py --client acme-invest-gmbh  # ein Kunde
python src/main.py --report-only            # nur Reports neu bauen, keine Suche
```

Der GitHub-Actions-Zeitplan (3× täglich) nimmt neue Kunden automatisch mit.

## Zeitplan

- **Täglich 07:00 / 13:00 / 19:00 Uhr CET** (automatisch via GitHub Actions)
- **Manuell** auslösbar: Repository → Actions → "MK Clipping Agent" → "Run workflow"

## Setup

1. Repository → **Settings** → **Secrets and variables** → **Actions**
2. Secrets anlegen: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CX`
3. **Actions**-Tab: Workflows aktivieren
4. Erster Test: Actions → "MK Clipping Agent" → **Run workflow**

## Dateien

```
├── .github/workflows/
│   └── clipping-agent.yml       # GitHub Actions Zeitplan (alle Kunden)
├── clients/
│   ├── mk-global-kapital.json   # Kunde 1: MK Global Kapital
│   └── beispiel-kunde.json.example
├── src/
│   ├── main.py                  # Orchestrierung (alle Kunden / --client)
│   ├── client_config.py         # Kunden-Konfigurationen laden
│   ├── new_client.py            # Kunden-Onboarding-Tool
│   ├── search.py                # RSS + Google + Claude-Validierung
│   └── excel_writer.py          # Excel-Report-Generierung
├── data/
│   ├── clippings.json           # MK Global Kapital (historischer Pfad)
│   └── <kunde>/clippings.json   # weitere Kunden
├── docs/
│   ├── index.html               # MK-Dashboard (GitHub Pages)
│   ├── produkt.html             # Verkaufsseite PressRadar DACH
│   └── latest_report.xlsx       # aktuellster MK-Report
├── output/                      # generierte Excel-Reports (alle Kunden)
├── GESCHAEFTSPLAN.md            # Preismodell + Weg zu 10.000 € in 6 Monaten
└── requirements.txt
```

## Manuell Artikel hinzufügen

Artikel direkt in die `clippings.json` des Kunden einfügen:

```json
{
  "date": "2026-03-20",
  "outlet": "Handelsblatt",
  "title": "Artikeltitel",
  "country": "D",
  "type": "Online",
  "tier": 1,
  "link": "https://...",
  "added_at": "2026-03-20T10:00:00",
  "source": "manual"
}
```

## Tier-Klassifizierung

**Tier 1**: FAZ, Handelsblatt, Börsen-Zeitung, NZZ, Finews, Institutional Money,
DAS INVESTMENT, FONDS professionell, altii, Citywire, portfolio institutionell,
Handelszeitung, Der Standard, Die Presse, WirtschaftsWoche, Manager Magazin, Capital, SZ

**Tier 2**: Alle anderen deutschsprachigen Medien

Pro Kunde erweiterbar über `extra_tier1_keywords` in der Kunden-JSON.
