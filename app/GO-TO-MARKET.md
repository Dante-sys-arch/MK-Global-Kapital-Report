# ClipRadar — Go-to-Market: 10.000 € Umsatz in 6 Monaten

## 1. Die Nische

**Zielgruppe:** Kleine PR-Agenturen (1–10 Personen), PR-Freelancer und
kommunikationsaktive KMU im DACH-Raum — besonders in Branchen mit starker
Fachpresse (Finanz, Startup, Health, Immobilien).

**Das Problem (validiert, Stand Juli 2026):**

| Bestehende Lösung | Warum sie für die Zielgruppe nicht funktioniert |
|---|---|
| Meltwater, Cision | Median-Vertrag ~25.000 $/Jahr, nur Jahresverträge, intransparente Preise, für Konzern-Kommunikation gebaut |
| Landau Media, PMG | Pressespiegel-Lizenzen + Clip-Gebühren, auf Konzern-Pressestellen ausgerichtet; Einstieg zwar ab ~50 €/Monat, aber ohne KI-Validierung und ohne Agentur-Workflow |
| Google Alerts | Kostenlos, aber: deutsche Fachmedien kaum indexiert, keine Dedup, keine False-Positive-Filterung, kein Report |
| Mention, Brand24 & Co. | 50–150 $/Monat, aber Social-Listening-first, deutsche Fachpresse praktisch nicht abgedeckt, kein Excel-Pressespiegel im deutschen Agentur-Format |

**Die Lücke:** Niemand liefert *deutschsprachiges Fachmedien-Monitoring mit
KI-Validierung und fertigem Pressespiegel* im Preisband 49–249 €/Monat.
Genau dort sitzt die Zahlungsbereitschaft kleiner Agenturen: Sie berechnen
Medienbeobachtung heute manuell an ihre Kunden weiter (typisch 150–500 €/Monat
pro Mandat als Teil des Retainers) — ClipRadar macht daraus Marge statt Handarbeit.

**Unfairer Vorteil:** Das Produkt existiert bereits als produktiver
Einzelkunden-Agent (MK Global Kapital) und läuft seit Monaten täglich.
Der Gründer kommt selbst aus der Ziel-Branche und hat direkten Zugang zu
den ersten Kunden.

## 2. Preise und Pfad zu 10.000 €

**Pläne:** Starter 49 € · Pro 99 € · Agentur 249 € (bis 5 Mandate, +39 €/weiteres)

**Konservatives Wachstumsszenario (kumulierter Umsatz):**

| Monat | Neu gewonnen | Bestand (St/Pro/Ag) | MRR | Kumuliert |
|---|---|---|---|---|
| 1 | 2 Pro (eigenes Netzwerk) | 0/2/0 | 198 € | 198 € |
| 2 | 1 Agentur, 1 Starter | 1/2/1 | 496 € | 694 € |
| 3 | 1 Agentur, 2 Pro | 1/4/2 | 943 € | 1.637 € |
| 4 | 1 Agentur, 2 Pro, 2 Starter | 3/6/3 | 1.488 € | 3.125 € |
| 5 | 1 Agentur, 3 Pro | 3/9/4 | 2.034 € | 5.159 € |
| 6 | 1 Agentur, 3 Pro, 2 Starter | 5/12/5 | 2.678 € | 7.837 € |

Basis-Szenario: ~7.800 € nach 6 Monaten; mit je einem Zusatz-Mandat bei nur
3 der 5 Agenturkunden (+39 €) und einem Setup-Paket „Einrichtung + 12 Monate
im Voraus" (2 Kunden × Jahresvorauszahlung) liegt der **kassierte Umsatz über
10.000 €**. Aggressiveres, aber realistisches Ziel bei aktivem Vertrieb ab
Woche 1: 15–20 zahlende Kunden = 10.000 € rein aus laufenden Monatsgebühren.

**Warum die Zahlen erreichbar sind:** 20 Kunden in 6 Monaten heißt
~1 Abschluss pro Woche ab Monat 2 — bei einer Zielgruppe von >40.000
PR-Schaffenden in Deutschland (GPRA/DPRG-Umfeld, Freelancer-Verzeichnisse)
und einem Produkt, das 10-fach billiger ist als die etablierte Alternative.

**Unit Economics pro Kunde/Monat:** API-Kosten (Claude-Validierung
~1–3 €/Monat, Google CSE innerhalb Free Tier bzw. ~5 €), Hosting 0 €
(GitHub Actions), E-Mail ~0 €. **Deckungsbeitrag >90 %.**

## 3. Vertriebskanäle (in Prioritätsreihenfolge)

1. **Eigenes Netzwerk (Monat 1):** Bestehende und ehemalige PR-Kunden und
   Agentur-Kontakte direkt ansprechen. Referenz: der laufende
   MK-Global-Kapital-Report als Demo-Objekt. Ziel: 2–3 Kunden vor Launch.
2. **Direktakquise kleiner PR-Agenturen (ab Monat 2):** GPRA-/DPRG-Mitgliederlisten,
   PR-Journal-Agenturverzeichnis. Personalisierte Mail mit einem echten,
   kostenlos erstellten Beispiel-Pressespiegel über die Agentur bzw. einen ihrer
   Kunden — das Produkt ist selbst das beste Pitch-Dokument („Hier ist Ihr
   Pressespiegel von heute Morgen — so sieht das jeden Tag aus").
3. **LinkedIn-Content (laufend):** 2 Posts/Woche zu „Medienbeobachtung ohne
   Meltwater-Budget", Vorher/Nachher-Beispiele, Screenshots des Digests.
4. **Partnerschaften (ab Monat 3):** Freelancer-Plattformen und PR-Software-Blogs
   (KomSoftware, PR-Journal) — Gastbeiträge und Affiliate (20 % im 1. Jahr).
5. **Nischen-SEO (ab Monat 3):** Landing-Pages je Branche
   („Medienmonitoring Fondsbranche", „Pressespiegel Startup") — geringes
   Suchvolumen, aber kaufbereite Suchen ohne Wettbewerb.

## 4. Launch-Checkliste

**Technik (Tag 1–3)**
- [ ] Domain registrieren (clipradar.de / pressespiegel-radar.de — Verfügbarkeit prüfen) und `app/landing/` z.B. via GitHub Pages/Netlify deployen
- [ ] `hallo@clipradar.example` in der Landing Page durch echte Adresse ersetzen
- [ ] Privates Betriebs-Repo anlegen (Kundendaten gehören nicht in dieses Repo!), `app/` dorthin kopieren, Secrets setzen: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CX`, `SMTP_*`
- [ ] GitHub-Actions-Workflow aktivieren (läuft täglich 05:00 UTC = 7:00 MESZ)
- [ ] Test-Lauf mit `demo.yml` und eigener E-Mail-Adresse

**Kaufmännisch (Woche 1)**
- [ ] Stripe Payment Links für 49/99/249 € Abos anlegen und in Landing Page verlinken
- [ ] Impressum, Datenschutz, AGB (Muster: eRecht24/IT-Recht-Kanzlei)
- [ ] Kleinunternehmer- oder USt-Frage mit Steuerberater klären
- [ ] Urheberrecht beachten: nur Headlines + Links ausliefern (macht ClipRadar bereits), keine Volltexte — bei Print-/Volltext-Wünschen an PMG-Lizenzen verweisen

**Vertrieb (Woche 1–2)**
- [ ] Liste der 50 wärmsten Kontakte, je 1 personalisierte Mail pro Tag
- [ ] 3 Beispiel-Pressespiegel über bekannte Firmen als Demo-Material erzeugen
- [ ] LinkedIn-Profil auf ClipRadar ausrichten, ersten Post veröffentlichen

## 5. Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| RSS-Feeds ändern sich / sterben | Feed-Health steht im Log jedes Laufs; monatliche Pflege der Pakete (bereits im Code: Fehler-tolerantes Scannen) |
| Presserechtliche Grauzone Volltexte | Es werden nur Titel, Quelle, Datum, Link gespeichert und ausgeliefert — keine Artikeltexte |
| Kunde will Print/Paywall | Ehrlich abgrenzen (steht in FAQ); Upsell-Partnerschaft mit PMG möglich |
| Churn nach Monat 1 | Persönliches Onboarding, Suchprofil-Tuning nach 2 Wochen, wöchentlicher Qualitäts-Check der False-Positive-Quote |
| Ein Wettbewerber kopiert das Modell | Geschwindigkeit + Nischenfokus + persönlicher Service; die kuratierten Feed-Pakete und Disambiguierungs-Profile sind der eigentliche Burggraben |

## 6. Ehrliche Einordnung

Kein Plan garantiert Umsatz. Dieser hier hat drei Dinge für sich:
das Produkt läuft bereits produktiv für einen echten Kunden, die Zielgruppe
ist dem Gründer persönlich zugänglich, und der Preis liegt eine Größenordnung
unter der etablierten Alternative bei nahezu 100 % Deckungsbeitrag.
Der Engpass ist nicht Technik, sondern Vertriebsdisziplin: ~50 persönliche
Ansprachen pro Monat sind der eigentliche Job in den ersten 6 Monaten.
