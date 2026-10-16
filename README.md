# PressRadar DACH — Medien-Clipping-Agent (Multi-Kunden)

Automatischer Medien-Clipping-Agent für den DACH-Raum. Durchsucht täglich
deutschsprachige Medien (60+ RSS-Feeds + Google-Suche), validiert Treffer per
KI und generiert pro Kunde einen Excel-Report.

Ursprünglich gebaut für **MK Global Kapital** (erster Kunde, läuft unverändert
weiter) — jetzt als Mehrkunden-Produkt, das sich als Service verkaufen lässt.
**→ Siehe [GESCHAEFTSPLAN.md](GESCHAEFTSPLAN.md) für den Weg zu 10.000 € in 6 Monaten.**
**→ Verkaufsseite: [docs/produkt.html](docs/produkt.html) (via GitHub Pages).**

## Funktionsweise (v5, maximale Trefferquote)

Jeder Lauf sammelt Hinweise aus sechs Kanälen und prüft **jeden** Hinweis auf der Artikelseite selbst:

| Kanal | Was | Wann |
|---|---|---|
| RSS | 50+ Feeds, inkl. Beschreibung, Volltext und Autorenzeile | jeder Lauf |
| Google News RSS | Suchfeeds je Ausgabe DE, CH, AT | jeder Lauf |
| Neue Artikel der Stammmedien | jede neue URL aus den Sitemaps, im Volltext gelesen | jeder Lauf |
| Seitensuche | WordPress-Suche der Stammmedien (ganzes Archiv, trifft Autorenzeilen) | 1× täglich |
| Google Websuche | SerpApi, Gratisplan 250 Suchen/Monat, 8 Suchen pro Tag (Secret `SERPAPI_KEY`) | 1× täglich |
| Bing News RSS | zweiter, von Google unabhängiger Nachrichtenindex (DE/CH/AT) | jeder Lauf |
| Serper | Google Web + News, optional (Secret `SERPER_API_KEY`), derzeit nicht genutzt | 1× täglich |
| Google Custom Search | für dieses Projekt ohne Zugang (Google nimmt keine Neukunden an), schaltet sich selbst ab | – |
| Syndikation | exakte Titelsuche für jedes neue Clipping, findet Kopien auf anderen Medien | nach jedem Fund |

Prüfung: Die Namen (Firma oder Personen) müssen im Artikel stehen (Titel, Autor, Haupttext).
Namen mit Namensvettern (z. B. Johannes Feist) brauchen Finanzkontext. Unklare Fälle entscheidet Claude.
Was danach unklar bleibt, landet in der **Prüfliste** (`data/review.json`, Dashboard-Tab „Prüfliste“),
nie ungeprüft in den Clippings. Entscheidungen trägt man in `data/review_decisions.csv` ein (`Link;ja` oder `Link;nein`).

Zählregeln: Jede Erscheinung zählt, auch Syndikationen auf anderen Medien (Feld `syndication_of`).
Französischsprachige Artikel (Romandie) werden verworfen. Englischsprachige kommen in die Prüfliste.
Das Datum kommt von der Artikelseite, sonst aus Feed/Suchtreffer, nie von Claude.

**Soll-Liste:** `data/placements.csv` (Semikolon-getrennt): Platzierungen mit Medium-Domain und erwartetem Datum.
Der Agent markiert sie als gefunden oder meldet sie nach 3 Tagen als überfällig.

**Überwachung:** Jeder Lauf schreibt `data/runs/<kunde>-latest.md` (lesbar) und `.json`.
Fällt ein Kanal ganz aus oder ist Claude nicht erreichbar, schlägt der Workflow fehl und GitHub verschickt eine Mail.
Das Dashboard zeigt den Status oben an.

**Sonderläufe** (Actions → MK Clipping Agent → Run workflow):
- `mode=backfill`, `date_from`, `date_to`: Zeitraum nachsuchen (Google News, Websuche, Seitensuche je Monat)
- `mode=enrich`: Sprecher und Autorenzeile für bestehende Clippings ergänzen
- `dry_run=true`: Testlauf, speichert nichts außer dem Laufbericht

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

- **Ein Tageslauf, Ergebnisse vor 08:30 Uhr (Berlin).** Geplant 23:17 UTC, Ersatztermine 02:13 und 04:41 UTC.
  GitHub startet geplante Läufe oft Stunden zu spät; die Ersatztermine laufen nur, wenn der Tageslauf
  für das Berliner Datum noch fehlt.
- **Sofortlauf:** Actions → "MK Clipping Agent" → "Run workflow", oder eine Zeile in `data/review_decisions.csv`
  eintragen (der Lauf übernimmt die Entscheidung direkt).

## Setup

1. Repository → **Settings** → **Secrets and variables** → **Actions**
2. Secrets anlegen: `ANTHROPIC_API_KEY`, `SERPAPI_KEY` (optional `SERPER_API_KEY`)
3. **Actions**-Tab: Workflows aktivieren
4. Erster Test: Actions → "MK Clipping Agent" → **Run workflow**

## Dateien

```
├── .github/workflows/
│   └── main.yml                 # GitHub Actions Zeitplan (alle Kunden)
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
