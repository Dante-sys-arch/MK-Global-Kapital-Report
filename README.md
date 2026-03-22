# MK Global Kapital — DACH Clipping Agent

Automatischer Medien-Clipping-Agent für MK Global Kapital. Durchsucht täglich deutschsprachige DACH-Medien nach Erwähnungen und generiert einen Excel-Report.

## Funktionsweise

1. **Suche**: 6 spezialisierte Suchanfragen via Anthropic API + Web Search
2. **Deduplizierung**: Neue Artikel werden gegen bestehende geprüft (URL + Titel/Medium)
3. **Tier-Zuordnung**: Automatische Klassifizierung in Tier 1 (Leitmedien) und Tier 2
4. **Excel-Report**: Generierung im bestehenden Report-Format mit Analysis-Sheet
5. **Commit**: Ergebnisse werden automatisch ins Repository committed

## Zeitplan

- **Täglich 07:00 Uhr CET** (automatisch via GitHub Actions)
- **Manuell** auslösbar: Repository → Actions → "MK Clipping Agent" → "Run workflow"

## Setup

### 1. API-Key als GitHub Secret anlegen

1. Repository öffnen → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** klicken
3. Name: `ANTHROPIC_API_KEY`
4. Value: Dein Anthropic API Key
5. **Add secret**

### 2. GitHub Actions aktivieren

1. Repository → **Actions** Tab
2. Falls nötig: "I understand my workflows, go ahead and enable them" klicken

### 3. Erster Test

1. **Actions** → "MK Clipping Agent" → **Run workflow** → **Run workflow**
2. Warten bis der Workflow durchläuft (~2-3 Minuten)
3. Ergebnis: Neue Datei unter `output/` + aktualisierte `data/clippings.json`

## Dateien

```
├── .github/workflows/
│   └── clipping-agent.yml    # GitHub Actions Zeitplan
├── src/
│   ├── main.py               # Orchestrierung
│   ├── search.py              # Web-Suche via Anthropic API
│   └── excel_writer.py        # Excel-Report-Generierung
├── data/
│   └── clippings.json         # Alle gefundenen Clippings (persistenter Speicher)
├── output/                    # Generierte Excel-Reports
└── requirements.txt
```

## Manuell Artikel hinzufügen

Artikel direkt in `data/clippings.json` einfügen:

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

## Suchanfragen

1. `"MK Global Kapital" 2026`
2. `"Mikro Kapital" Mikrofinanz DACH 2026`
3. `"Michele Mattioda" "MK Global Kapital"`
4. `"Johannes Feist" Mikrofinanz 2026`
5. `"Mikro Kapital" "Private Debt" KMU`
6. `"MK Global Kapital" Anleihe Mikrofinanz`

## Tier-Klassifizierung

**Tier 1**: FAZ, Handelsblatt, Börsen-Zeitung, NZZ, Finews, Institutional Money, DAS INVESTMENT, FONDS professionell, altii, Citywire, portfolio institutionell

**Tier 2**: Alle anderen deutschsprachigen Medien
