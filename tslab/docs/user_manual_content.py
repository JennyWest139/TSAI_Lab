"""Inhalt des TSLab-Benutzerhandbuchs (wird zu PDF gebaut)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManualSection:
    title: str
    body: str


MANUAL_TITLE = "TSLab Benutzerhandbuch"
MANUAL_SUBTITLE = "Zeitreihenanalyse · Diplomarbeit JW 2008 · Version 1.0"
MANUAL_VERSION = "2026-06"


SECTIONS: list[ManualSection] = [
    ManualSection(
        title="1. Einleitung",
        body="""
TSLab ist eine Arbeitsumgebung für die ökonometrische Analyse von Zeitreihen.
Sie unterstützt die Replikation und Erweiterung der Diplomarbeit JW 2008
(PDAX, Kreuzkorrelation, ARMA/GARCH-Modelle).

Das Handbuch wird schrittweise erweitert. Über das Fragezeichen-Symbol (?)
oben rechts in der Weboberfläche öffnen Sie diese PDF jederzeit in einem
neuen Fenster.
        """.strip(),
    ),
    ManualSection(
        title="2. Tutorial — Schnellstart (Web)",
        body="""
Schritt 1 — Datenbank vorbereiten
  • docker compose up -d  (oder lokaler PostgreSQL-Dienst)
  • python scripts/prepare_web_postgres.py
  • python scripts/run_web.py

Schritt 2 — Zeitreihe ansehen
  • Menü „Zeitreihen“ → auf PDAX klicken
  • Interaktive Grafik: Originalwerte + Trendkomponente
  • Mit der Maus über die Linie fahren → Datum und Wert

Schritt 3 — Kreuzkorrelation
  • Menü „Korrelation → Neue Analyse“
  • Serie A und B wählen (z. B. PDAX vs. Erwerbslose)
  • Von-Datum und Bis-Datum unabhängig setzen (Von < Bis)
  • Vorschau prüfen → „Korrelation starten“
  • Ergebnis: Output-Ordner mit PNG und CSV

Schritt 4 — Time Series Analysis (TSA)
  • Menü „TSA → Neue Analyse“
  • Zeitreihe, Training Von/Bis, Prognose bis wählen
  • Modell(e) ankreuzen → „TSA starten“

Optional — KI-Bericht
  • Modell im Abschnitt „KI-Bericht (optional)“ wählen
  • Bei Pausendialog: 1 Minute warten oder Bericht vorzeitig abschließen
        """.strip(),
    ),
    ManualSection(
        title="3. Oberfläche",
        body="""
Übersicht: Status der Datenbank, Schnelllinks.
Upload: CSV mit Datumsspalte und Wertspalte importieren.
Zeitreihen: Liste aller Reihen; Klick öffnet Detailgrafik.
Korrelation / TSA: Analyseformulare mit Historie früherer Läufe.
Output: Ergebnisordner öffnen, Dateien ansehen, Ordner als ZIP laden.
Tags: Zeitreihen und Läufe kategorisieren; Listen lassen sich filtern.
Hell/Dunkel: Umschalter oben rechts neben dem Hilfe-Button (?).
        """.strip(),
    ),
    ManualSection(
        title="4. Zeitreihen-Detailgrafik",
        body="""
Standardanzeige: Originalwerte (durchgezogen) und Trendkomponente
(gestrichelt) aus additiver/multiplikativer Saisonzerlegung (statsmodels).

Optional: Checkbox „Kontinuierliche Renditen als Zusatz“ — nur sinnvoll
bei Kursindizes (PDAX, DAX, Dow Jones) oder wenn Sie Renditen explizit
prüfen möchten.

Trend-Fußnote unter der Grafik erläutert die verwendete Zerlegungsmethode.
        """.strip(),
    ),
    ManualSection(
        title="5. Kreuzkorrelation",
        body="""
Vor der Berechnung zeigt die Vorschau beide Reihen im gewählten Fenster:
links Serie A, rechts Serie B — jeweils Original und Trend.

Die eigentliche Korrelation arbeitet auf transformierten Renditen gemäß
Analysemodus (thesis / extended). Die Vorschau zeigt bewusst die Niveaus,
damit Sie Datenqualität und Trends erkennen.

Ergebnisplots: Balkendiagramm der Lags, aligned_series.png mit
Originalwerten und Trends, lag_correlations.csv. Wenn ein KI-Modell gewählt
wurde, entstehen zusätzlich ai_bericht.docx und ai_bericht.pdf im Laufordner.
        """.strip(),
    ),
    ManualSection(
        title="6. Time Series Analysis (TSA)",
        body="""
Modelle: ARMA, GARCH, ARMA-GARCH. Die Ordnung kann automatisch per AIC
gewählt werden oder als User-Order (p, q) für ARMA und GARCH.

Analysemodus thesis: Stichprobe ab 12/1987, kontinuierliche Renditen
ohne lineares Detrending (Diplomarbeit).

Training endet am Cutoff-Datum; Prognose bis forecast_end.
Output je Modellordner: Residuen-Diagnostik, Prognoseplots mit
Quantilbändern, Niveau-Rücktransformation, summary.txt und bei thesis
coefficient_abgleich.txt. Wenn ein KI-Modell gewählt wurde, entstehen
ai_bericht.docx und ai_bericht.pdf je Modellordner.
        """.strip(),
    ),
    ManualSection(
        title="7. Histogramme und Diagnostik",
        body="""
Histogramme in Phase 0 und bei Residuen enthalten eine eingezeichnete
Normalverteilungskurve (orange): gleicher Mittelwert und Standardabweichung
wie die Stichprobe, skaliert auf die Balkenhöhen.

Vergleichen Sie die Kurve mit den Balken: starke Abweichungen deuten auf
Schiefe, Ausreißer oder multimodale Verteilungen hin — wichtig vor GARCH.
        """.strip(),
    ),
    ManualSection(
        title="8. Output, Tags und KI-Berichte",
        body="""
Output-Browser
  • Menü „Output“ oder Link aus einer Historie öffnen
  • Unterstützte Dateitypen: PNG/JPG, TXT/CSV/XLSX, PDF/DOCX, HTML/JSON
  • Ordner können als ZIP heruntergeladen werden

Tags
  • Tags sind mehrere Kategorien pro Zeitreihe oder Lauf
  • Neue Korrelationen/TSA-Läufe erben die Tags der beteiligten Zeitreihen
  • „Reporting“ ist reserviert und markiert berichtsrelevante Einträge

KI-Berichte aktivieren
  • TSLAB_AI_REPORTS_ENABLED=1 setzen
  • OPENAI_API_KEY setzen und Web neu starten
  • Modelle: openai:gpt-4o-mini oder openai:gpt-4o (Gemini ist vorbereitet,
    aber noch nicht implementiert)

Ablauf
  • Der Analyse-Lauf schreibt zuerst normale Artefakte in output/
  • Danach wertet die Report-Session PNG, TXT und Tabellen aus
  • Nach jeweils 5 KI-Anfragen oder bei Rate-Limits erscheint ein Dialog:
    1 Minute warten oder vorzeitig abschließen
  • Reports/laufbericht.pdf enthält Laufzeiten, Token, Langfuse-Status,
    Pausenereignisse und Links zu Berichten
        """.strip(),
    ),
]


GLOSSARY: list[ManualSection] = [
    ManualSection(
        title="ARMA(p,q)",
        body="AutoRegressive Moving Average: Modell für den bedingten Mittelwert "
        "einer Zeitreihe. AR(p) nutzt p vergangene Werte, MA(q) q vergangene "
        "Schocks. ARMA(1,1) ist Standard in der Diplomarbeit.",
    ),
    ManualSection(
        title="GARCH(p,q)",
        body="Generalized AutoRegressive Conditional Heteroskedasticity: Modell "
        "für die bedingte Varianz (Volatilität). Große Schocks begünstigen "
        "hohe Volatilität in Folgeperioden (Clustering).",
    ),
    ManualSection(
        title="Kontinuierliche Rendite",
        body="Log-Differenz: r_t = ln(P_t) − ln(P_{t−1}). Näherung an prozentuale "
        "Renditen bei kleinen Änderungen; additiv über Zeit — wichtig für "
        "ökonometrische Modelle.",
    ),
    ManualSection(
        title="Cutoff / Trainingsende",
        body="Letzter Zeitpunkt der Schätzung. Daten danach dienen als Holdout "
        "zur Prognosevalidierung (out-of-sample).",
    ),
    ManualSection(
        title="Kreuzkorrelation",
        body="Korrelation zwischen Serie A zum Zeitpunkt t und Serie B zum "
        "Zeitpunkt t+h (Lag h). Positives h: B führt A. Wird zur "
        "Lead-Lag-Analyse makroökonomischer Indikatoren genutzt.",
    ),
    ManualSection(
        title="PDAX",
        body="Performanceindex deutscher Aktien — in der Diplomarbeit zentrale "
        "Kursreihe. Monatsdaten aus Werte.csv.",
    ),
    ManualSection(
        title="Quantil / Quantilband",
        body="Prognoseintervall: z. B. 5 %- und 95 %-Quantil der bedingten "
        "Verteilung der Rendite/Volatilität — Risikomaß neben dem Median.",
    ),
    ManualSection(
        title="Residuen",
        body="Differenz zwischen beobachtetem Wert und Modellfit. Sollen "
        "ungekorreliert und möglichst normalverteilt sein (Diagnostik: "
        "AKF, Ljung-Box, QQ-Plot).",
    ),
    ManualSection(
        title="Saisonzerlegung / Trendkomponente",
        body="Zerlegung y = Trend + Saison + Residuum (additiv oder multiplikativ). "
        "Die Trendlinie in den Web-Grafiken stammt aus seasonal_decompose.",
    ),
    ManualSection(
        title="thesis vs. extended",
        body="thesis: Parameter und Stichprobe wie Diplomarbeit JW 2008. "
        "extended: längere Historie, lineare Trendentfernung auf Renditen, "
        "zweistufiges ARMA-GARCH.",
    ),
    ManualSection(
        title="Volatilität (bedingt)",
        body="σ_t² im GARCH-Modell: prognostizierte Varianz zum Zeitpunkt t "
        "gegeben die Information bis t−1. Grundlage für Value-at-Risk.",
    ),
]
