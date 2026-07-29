# Geschäftsplan: 10.000 € in 6 Monaten mit FinVoice

**Ehrlich vorab:** Auch dieses Produkt verkauft sich nicht von selbst — aber es hat
zwei Vorteile gegenüber dem Clipping-Agenten: einen **deutlich höheren Preis pro Kunde**
(Sie brauchen nur 4–5 Kunden statt 6) und **dieselbe Zielgruppe**, die Sie ohnehin
schon fürs Clipping ansprechen. Jedes Vertriebsgespräch kann beide Produkte verkaufen.

## Was Sie verkaufen

**LinkedIn-Ghostwriting für Finanz-Führungskräfte — als Service, nicht als Software:**

- Jeden Montag früh: 3 fertige Post-Entwürfe im O-Ton des CEOs, aufgehängt an
  aktuellen Branchennachrichten der Woche (automatisch aus themenrelevanten Feeds)
- Sie redigieren jeden Entwurf 10–15 Minuten (dafür gibt es den Humanizer-Workflow),
  der Kunde bekommt eine private Redaktionsseite mit Kopieren-Button
- Der Kunde postet selbst (oder seine Assistenz) — **nichts wird automatisch
  veröffentlicht**, damit gibt es kein LinkedIn-ToS-Problem und der Kunde behält Kontrolle

**Warum das jemand kauft:** Sichtbarkeit des CEOs ist im Asset Management direkt
vertriebsrelevant (Fondsboutiquen leben von Vertrauen in Personen). Klassisches
Executive-Ghostwriting kostet im DACH-Raum 1.000–3.000 €/Monat. Sie liegen mit
Automatisierung im Rücken deutlich darunter — bei besserer Aktualität, weil der
Agent jede Woche die frischen Aufhänger liefert.

## Preismodell

| Paket | Leistung | Preis |
|---|---|---|
| **Setup** | Stimmprofil (Interview + Stilproben), Themen- und Feed-Konfiguration | 490 € einmalig |
| **Sichtbar** | 3 redigierte Post-Entwürfe/Woche, Redaktionsseite | 590 €/Monat |
| **Sichtbar+** | 5 Entwürfe/Woche + monatliches 30-Min-Themengespräch | 890 €/Monat |
| **Agentur/White-Label** | Wie Sichtbar, unter Marke der PR-Agentur, ab 3 Führungskräften | 440 €/Monat pro Kopf |

## Die Rechnung zu 10.000 €

Konservatives Szenario: **1 neuer Kunde pro Monat**, Paket „Sichtbar".

| Monat | Kunden | Setup-Erlöse | Monatserlöse | Kumuliert |
|---|---|---|---|---|
| 1 | 1 | 490 € | 590 € | 1.080 € |
| 2 | 2 | 490 € | 1.180 € | 2.750 € |
| 3 | 3 | 490 € | 1.770 € | 5.010 € |
| 4 | 4 | 490 € | 2.360 € | 7.860 € |
| 5 | 5 | 490 € | 2.950 € | **11.300 €** |

→ **5 Kunden in 5 Monaten = Ziel übertroffen, mit einem Monat Puffer.**
Danach laufen ~3.000 €/Monat wiederkehrend weiter. Ein einziger Agentur-Deal
mit 3 Führungskräften (1.320 €/Monat) verkürzt den Weg drastisch.

## Ihr Aufwand & Kosten

- **Zeit:** 10–15 Min. Redaktion pro Post × 3 Posts × Kunden. Bei 5 Kunden:
  ~4 h pro Woche. Das ist der Preis für die hohe Marge — einplanen, nicht schönrechnen.
- **API-Kosten:** wenige Cent pro Wochenlauf und Kunde (~2–5 €/Monat gesamt)
- **Infrastruktur:** GitHub Actions + Pages, im Free-Kontingent
- **Marge: über 90 %** — aber anders als beim Clipping mit echtem Redaktionsanteil.

## Zielkunden (in dieser Reihenfolge)

1. **Ihre Clipping-Interessenten und -Kunden.** Das Clipping zeigt dem CEO, *wo* er
   zitiert wird — FinVoice sorgt dafür, dass es *mehr* wird. Perfektes Cross-Selling,
   ein Gespräch, zwei Produkte.
2. **Fondsboutiquen und Asset Manager**, deren Gründer/CEO auf LinkedIn präsent, aber
   unregelmäßig ist (Profil ansehen: letzter Post > 3 Wochen her = idealer Kandidat).
3. **Finanz-PR-Agenturen** als White-Label-Partner: Die verkaufen „Executive Visibility"
   längst — aber teuer und manuell. Sie liefern denen den Maschinenraum.

## Vertrieb: Was Sie konkret tun

**Woche 1–2:**
- Eigenes Schaufenster: Legen Sie **sich selbst** als ersten Kunden an und posten Sie
  6 Wochen lang 2–3× pro Woche. Ihr eigenes LinkedIn-Profil ist die Live-Demo.
- Liste von 30 Fondsboutiquen-CEOs mit verwaistem LinkedIn-Profil (letzter Post > 3 Wochen)
  plus die Finanz-PR-Agenturen aus Ihrer Clipping-Liste.

**Ab Woche 3 — pro Woche:**
- 10 personalisierte Kontakte. Der stärkste Öffner ist eine Arbeitsprobe:
  *„Ich habe testweise drei LinkedIn-Posts in Ihrem Ton geschrieben — aufgehängt an den
  Branchenthemen dieser Woche. Darf ich sie Ihnen schicken? Kostet Sie nichts."*
  Das kostet Sie pro Interessent 5 Minuten (`new_client.py` + ein Lauf) und ist
  konkreter als jede Broschüre.

**Konversionsannahme:** 10 Kontakte/Woche → ~1–2 ernsthafte Gespräche → ~1 Abschluss/Monat.
Das ist die konservative Basis der Tabelle oben.

## Risiken & Pflichten (nicht überspringen)

- **Kein Selbstläufer:** Ohne die wöchentlichen 10 Kontakte passiert nichts.
  Engpass ist Vertrieb, nicht Technik — wie beim Clipping.
- **Qualität = Redaktion:** Ungeprüfte KI-Posts unter dem Namen eines CEOs sind ein
  Reputationsrisiko — für den Kunden und für Sie. Die 10–15 Min. Redaktion pro Post
  sind nicht optional. Faktenaussagen im Entwurf immer gegen die Quelle prüfen.
- **Compliance regulierter Häuser:** Keine Produktwerbung, keine Renditeversprechen,
  keine Empfehlungen zu konkreten Wertpapieren (ist im System-Prompt verankert, muss
  aber redaktionell überwacht werden). Bei BaFin-/FINMA-regulierten Kunden den Posting-
  Freigabeprozess des Hauses respektieren — der Kunde gibt frei, nicht Sie.
- **Transparenz:** Der Kunde weiß, dass KI im Spiel ist (steht im Vertrag). Ghostwriting
  selbst ist branchenüblich und legal — der Kunde veröffentlicht unter eigenem Namen
  und trägt die inhaltliche Verantwortung, die Freigabe dokumentieren Sie.
- **Vertrag/DSGVO:** Dienstleistungsvertrag mit 3 Monaten Mindestlaufzeit,
  Verschwiegenheit, Nutzungsrechte an den Texten beim Kunden. Einmal vom Anwalt
  aufsetzen lassen (~300–500 €), Vorlage vom Clipping-Vertrag wiederverwenden.
- **Privates Repo:** Stimmprofile und Entwürfe zahlender Kunden sind vertraulich —
  dieses Projekt vor dem ersten zahlenden Kunden in ein **privates** Repo umziehen.
- **Steuern:** Einnahmen laufen zusammen mit den Clipping-Erlösen — Kleinunternehmergrenze
  (25.000 €/Jahr) im Blick behalten, ggf. früher Umsatzsteuer ausweisen.

## Technik ist fertig — so legen Sie Kunde Nr. 1 an

```bash
python finvoice/src/new_client.py "Dr. Max Berger" \
  --company "Berger Capital AG" --role CEO \
  --topics "Sachwerte, Zinswende, Private Markets" \
  --keywords "zinsen, immobilienfonds, private equity" \
  --feeds "https://www.dasinvestment.com/feed/" "https://www.institutional-money.com/rss/news/"

# → voice_samples/positions/avoid in clients/max-berger.json ausfüllen, dann:
python finvoice/src/main.py --client max-berger
```

Der GitHub-Actions-Zeitplan (montags früh) nimmt jeden neuen Kunden automatisch mit.
