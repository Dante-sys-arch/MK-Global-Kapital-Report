# Geschäftsplan: 10.000 € in 6 Monaten mit dem Clipping-Agenten

**Ehrlich vorab:** Keine App verdient von selbst Geld. Was du jetzt hast, ist ein
fertiges, automatisiertes Produkt mit nahezu null Betriebskosten — verdient wird
das Geld im Vertrieb. Dieser Plan zeigt den rechnerisch realistischen Weg.

## Was du verkaufst

**Automatisches Medien-Monitoring für den DACH-Raum** — als Service, nicht als Software:

- Tägliche Überwachung von 60+ deutschsprachigen Finanz- und Wirtschaftsmedien (RSS) plus Google-Suche
- KI-Validierung der Treffer (keine Namensvetter, keine Werbung, keine Sidebar-Links)
- Täglicher Excel-Report mit Analyse-Sheet (Tier-Split, Länder, Monatsverlauf, Charts)
- Web-Dashboard mit Download-Link
- Läuft vollautomatisch 3× täglich — der Kunde muss nichts tun

Der Beweis, dass es funktioniert, läuft bereits: **MK Global Kapital ist dein Referenzkunde**
(Einverständnis für die Referenznennung vorher einholen).

Zum Vergleich: Etablierte Anbieter wie Landau Media oder PMG kosten typischerweise
500–2.000 €+ pro Monat. Du positionierst dich darunter, als schlanker Spezialist
für Finanz-/Investment-Themen im DACH-Raum.

## Preismodell

| Paket | Leistung | Preis |
|---|---|---|
| **Setup** | Einrichtung, Suchprofil-Tuning, 2 Wochen Feinjustierung | 490 € einmalig |
| **Standard** | Tägliches Monitoring, Excel-Report, Dashboard | 349 €/Monat |
| **Agentur/White-Label** | Wie Standard, unter Marke der PR-Agentur, ab 3 Endkunden | 249 €/Monat pro Endkunde |

## Die Rechnung zu 10.000 €

Konservatives Szenario: **1 neuer Kunde pro Monat**, Standard-Paket.

| Monat | Kunden | Setup-Erlöse | Monatserlöse | Kumuliert |
|---|---|---|---|---|
| 1 | 1 | 490 € | 349 € | 839 € |
| 2 | 2 | 490 € | 698 € | 2.027 € |
| 3 | 3 | 490 € | 1.047 € | 3.564 € |
| 4 | 4 | 490 € | 1.396 € | 5.450 € |
| 5 | 5 | 490 € | 1.745 € | 7.685 € |
| 6 | 6 | 490 € | 2.094 € | **10.269 €** |

→ **6 Kunden in 6 Monaten = Ziel erreicht.** Danach laufen ~2.100 €/Monat wiederkehrend weiter.
Eine einzige Agentur mit 3–4 Endkunden verkürzt den Weg drastisch.

## Betriebskosten (pro Kunde und Monat)

- Google Custom Search API: 100 Anfragen/Tag kostenlos, darüber ~5 $/1.000 → ca. 0–10 €
- Anthropic API (Validierung): wenige Cent pro Lauf → ca. 2–5 €
- GitHub Actions + Pages: kostenlos (öffentl. Repo) bzw. im Free-Kontingent
- **Marge: über 90 %.** Dein Aufwand pro Kunde: ~2 h Onboarding, danach nahe null.

## Zielkunden (in dieser Reihenfolge)

1. **PR- und IR-Agenturen im Finanzbereich** — der wichtigste Hebel. Sie brauchen Clipping-Reports
   für *jeden* Mandanten, kaufen also mehrfach. Ein Abschluss = 3–10 Endkunden.
2. **Fondsboutiquen, Asset Manager, Emittenten** — genau das MK-Profil. Sie wollen wissen,
   wo CEO und Marke zitiert werden, und brauchen den Report für Vorstand/Investoren.
3. **Mittelständler mit aktiver Pressearbeit** — alle, die heute manuell googeln.

## Vertrieb: Was du konkret tust

**Woche 1–2:**
- Freigabe von MK Global Kapital als Referenz einholen
- `docs/produkt.html` mit deiner Kontaktadresse versehen und verlinken (GitHub Pages ist schon aktiv)
- Liste von 30 Finanz-PR-Agenturen und 30 Fondsboutiquen im DACH-Raum erstellen (LinkedIn, GoogleFinance-PR-Rankings, Anbieterverzeichnisse)

**Ab Woche 2 — pro Woche:**
- 10 personalisierte Kontakte (LinkedIn/E-Mail), Kernsatz: *"Ich betreibe das automatisierte
  Medien-Monitoring für einen Schweizer Asset Manager — täglicher Report, Bruchteil der Kosten
  von Landau/PMG. Ich richte Ihnen 14 Tage kostenlos ein Suchprofil ein."*
- Das kostenlose 14-Tage-Probeprofil ist dein stärkstes Argument: Es kostet dich
  2 Minuten (`python src/new_client.py ...`) und der Interessent bekommt echte Treffer
  über die eigene Firma — das verkauft sich selbst.

**Konversionsannahme:** 10 Kontakte/Woche → ~1 Demo/Woche → ~1 Abschluss/Monat. Das ist
die konservative Basis der Tabelle oben.

## Risiken & Pflichten (nicht überspringen)

- **Kein Selbstläufer:** Ohne die wöchentlichen 10 Kontakte passiert nichts. Der Engpass ist Vertrieb, nicht Technik.
- **Urheberrecht:** Das Tool speichert nur Titel, Quelle, Datum und Link — keine Volltexte. Dabei bleiben (Links sind zulässig, Volltext-Kopien nicht).
- **DSGVO/Vertrag:** Pro Kunde einen einfachen Dienstleistungsvertrag mit Laufzeit (3 Monate Mindestlaufzeit empfohlen) und AV-Klausel. Einmal vom Anwalt aufsetzen lassen (~300–500 €).
- **Gewerbe/Steuern:** Einnahmen anmelden (Gewerbe oder freiberuflich je nach Lage, Kleinunternehmerregelung bis 25.000 €/Jahr prüfen).
- **Privates Repo pro Kunde:** Kundendaten gehören nicht in ein öffentliches Repo. Für zahlende Kunden dieses Repo als private Vorlage nutzen (GitHub Template) oder ein privates Mono-Repo betreiben.

## Technik ist fertig — so legst du Kunde Nr. 2 an

```bash
python src/new_client.py "Acme Invest GmbH" \
  --keywords "acme invest, peter mustermann" \
  --people "Peter Mustermann (CEO)" \
  --industry "Immobilienfonds, Sachwerte"

python src/main.py --client acme-invest-gmbh   # Testlauf
```

Der GitHub-Actions-Zeitplan (3× täglich) nimmt jeden neuen Kunden automatisch mit.
