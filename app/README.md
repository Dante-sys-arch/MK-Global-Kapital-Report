# ClipRadar — KI-Medienmonitoring für den DACH-Raum

Multi-Kunden-SaaS auf Basis des MK-Clipping-Agents: tägliches Monitoring
deutschsprachiger Leit- und Fachmedien, KI-Validierung der Treffer,
Excel-Pressespiegel und E-Mail-Digest pro Kunde.

Geschäftsmodell, Preise und Vertriebsplan: siehe [GO-TO-MARKET.md](GO-TO-MARKET.md).

## Architektur

```
app/
├── clients/            # 1 YAML pro Kunde (_template.yml als Vorlage)
├── engine/
│   ├── config.py       # Config-Laden + Validierung
│   ├── feeds.py        # Kuratierte RSS-Feed-Pakete (finance/general/startup/health/realestate)
│   ├── monitor.py      # RSS + Google CSE -> Dedup -> Claude-Validierung -> Speichern
│   ├── report.py       # Excel-Pressespiegel mit Analyse-Sheet und Charts
│   ├── mailer.py       # HTML-Digest + Excel-Anhang per SMTP
│   └── runner.py       # CLI: alle oder einzelne Kunden verarbeiten
├── data/<kunde>/       # clippings.json pro Kunde (entsteht zur Laufzeit)
├── output/<kunde>/     # Excel-Reports pro Kunde (entsteht zur Laufzeit)
├── landing/index.html  # Produkt-Landing-Page (statisch deploybar)
└── tests/              # Offline-Smoke-Tests (kein Netz, keine Keys nötig)
```

## Schnellstart

```bash
pip install -r app/requirements.txt

# Tests (offline)
python -m pytest app/tests/ -v

# Einen Kunden lokal laufen lassen, ohne Mail
cd app && python -m engine.runner --client demo --no-mail

# Alle aktiven Kunden (Produktionslauf)
cd app && python -m engine.runner
```

## Umgebungsvariablen

| Variable | Zweck | Pflicht |
|---|---|---|
| `ANTHROPIC_API_KEY` | KI-Validierung der Treffer | empfohlen (sonst Auto-Klassifizierung) |
| `GOOGLE_API_KEY` / `GOOGLE_CX` | Google Custom Search zusätzlich zu RSS | optional |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | Report-Versand | optional (ohne: kein Versand) |
| `CLIPRADAR_MODEL` | Claude-Modell für Validierung (Default: `claude-sonnet-5`) | optional |

## Neuen Kunden anlegen

1. `app/clients/_template.yml` nach `app/clients/<kuerzel>.yml` kopieren
2. `name`, `keywords`, `context`, `feed_packs`, `delivery.emails` ausfüllen
3. Testlauf: `cd app && python -m engine.runner --client <kuerzel> --no-mail`
4. Committen — der tägliche GitHub-Actions-Lauf nimmt den Kunden automatisch mit

**Wichtig für den Produktivbetrieb:** Kundendaten (Configs, Clippings) gehören
in ein *privates* Betriebs-Repo, nicht in dieses. Dieses Repo enthält den
Produktcode und die Demo-Konfiguration.

## Betrieb

Der Workflow `.github/workflows/clipradar.yml` läuft täglich um 05:00 UTC
(07:00 MESZ), verarbeitet alle aktiven Kunden und committet neue Clippings
und Reports zurück ins Repo. Manueller Start: Actions → „ClipRadar" → Run workflow.
