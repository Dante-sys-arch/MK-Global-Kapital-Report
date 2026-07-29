"""
Kuratierte RSS-Feed-Pakete für den DACH-Raum.

Jeder Kunde wählt in seiner Config ein oder mehrere `feed_packs` und kann
über `extra_rss_feeds` eigene Feeds ergänzen. Die Pakete sind das
Kern-Asset des Produkts: internationale Billig-Tools (Mention, Brand24)
decken deutsche Fachmedien praktisch nicht ab.
"""

FEED_PACKS = {
    # Finanz- und Kapitalmarkt-Fachmedien DACH
    "finance_dach": [
        "https://www.faz.net/rss/aktuell/finanzen/",
        "https://www.handelsblatt.com/contentexport/feed/finanzen",
        "https://www.nzz.ch/finanzen.rss",
        "https://www.finews.ch/news/finanzplatz/rss/1finews",
        "https://www.dasinvestment.com/feed/",
        "https://www.fondsprofessionell.de/rss/news.xml",
        "https://www.institutional-money.com/rss/news/",
        "https://www.portfolio-institutionell.de/feed/",
        "https://www.boersen-zeitung.de/rss",
        "https://www.moneycab.com/feed/",
        "https://investrends.ch/feed/",
        "https://www.bondguide.de/feed/",
        "https://www.dfpa.info/feed/",
        "https://e-fundresearch.com/feeds/news",
        "https://www.finanznachrichten.de/rss-alle-nachrichten",
        "https://www.cash.ch/rss/news",
        "https://www.payoff.ch/feed/",
        "https://www.fondsexklusiv.de/feed/",
        "https://www.cash-online.de/feed/",
        "https://www.altii.de/feed/",
        "https://citywire.de/feed/",
        "https://www.private-banking-magazin.de/feed/",
        "https://www.fixed-income.org/feed/",
        "https://www.finanzwelt.de/feed/",
        "https://www.procontra-online.de/feed/",
        "https://www.boersen-kurier.at/feed/",
        "https://www.kreditwesen.de/feed/",
        "https://www.allnews.ch/rss",
        "https://www.geldmeisterin.com/feed/",
        "https://www.platow.de/feed/",
        "https://fondstrends.ch/feed/",
        "https://www.dpn-online.com/feed/",
        "https://www.versicherungsbote.de/feed/",
        "https://www.fundresearch.de/feed/",
    ],
    # Allgemeine Wirtschafts- und Tagesmedien DACH
    "general_dach": [
        "https://www.faz.net/rss/aktuell/wirtschaft/",
        "https://www.handelsblatt.com/contentexport/feed/unternehmen",
        "https://www.nzz.ch/wirtschaft.rss",
        "https://www.handelszeitung.ch/rss.xml",
        "https://www.derstandard.at/rss/wirtschaft",
        "https://diepresse.com/rss/Wirtschaft",
        "https://www.wiwo.de/contentexport/feed/rss/schlagzeilen/finanzen/",
        "https://www.manager-magazin.de/finanzen/index.rss",
        "https://www.capital.de/feed/rss",
        "https://rss.sueddeutsche.de/rss/Wirtschaft",
        "https://www.welt.de/feeds/section/finanzen.rss",
        "https://kurier.at/wirtschaft/rss",
        "https://www.srf.ch/news/wirtschaft/rss/feed",
        "https://www.n-tv.de/wirtschaft/rss",
        "https://www.tagesanzeiger.ch/wirtschaft/rss.xml",
        "https://www.markteinblicke.de/feed/",
    ],
    # Startup-, Gründer- und Tech-Medien DACH
    "startup_dach": [
        "https://www.gruenderszene.de/feed",
        "https://www.deutsche-startups.de/feed/",
        "https://t3n.de/rss.xml",
        "https://www.gruenderkueche.de/feed/",
        "https://www.basicthinking.de/blog/feed/",
        "https://www.trendingtopics.eu/feed/",
        "https://www.startupvalley.news/de/feed/",
    ],
    # Gesundheits- und Pharma-Fachmedien DACH
    "health_dach": [
        "https://www.aerztezeitung.de/rss/news.rss",
        "https://www.apotheke-adhoc.de/rss.xml",
        "https://www.pharmazeutische-zeitung.de/feed/",
        "https://www.kma-online.de/rss",
        "https://www.medinside.ch/de/rss",
    ],
    # Immobilien-Fachmedien DACH
    "realestate_dach": [
        "https://www.immobilien-zeitung.de/rss/nachrichten.xml",
        "https://www.haufe.de/xml/rss_129130.xml",
        "https://www.immobilienmanager.de/rss",
        "https://www.konii.de/feed",
    ],
}


def resolve_feeds(feed_packs, extra_feeds=None):
    """Feed-Pakete + kundenspezifische Feeds zu einer Liste auflösen."""
    feeds = []
    for pack in feed_packs or []:
        feeds.extend(FEED_PACKS.get(pack, []))
    feeds.extend(extra_feeds or [])
    # Reihenfolge erhalten, Duplikate entfernen
    seen = set()
    unique = []
    for f in feeds:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique
