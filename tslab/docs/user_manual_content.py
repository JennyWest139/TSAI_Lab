"""Inhalt des TSLab-Benutzerhandbuchs (wird zu PDF gebaut)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManualSection:
    title: str
    body: str


MANUAL_TITLE = "TSLab Benutzerhandbuch"
MANUAL_SUBTITLE = "Zeitreihenanalyse · Diplomarbeit JW 2008 · Version 1.0"
MANUAL_VERSION = "2026-07"


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
  • Standard: Ohne KI (nur Analyse-Lauf)
  • Alternativ eines von vier Modellen: GPT-4o mini, GPT-5 mini, GPT-5 nano, Gemini
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
wurde, entstehen zusätzlich CORR_Bericht_<KI-Modell>.docx/.pdf im Laufordner.
        """.strip(),
    ),
    ManualSection(
        title="6. Time Series Analysis (TSA)",
        body="""
Modelle: ARMA, GARCH, ARMA-GARCH. Die Ordnung kann automatisch per AIC
gewählt werden oder als User-Order (p, q) für ARMA und GARCH.

Analysemodus thesis: Stichprobe ab 12/1987, kontinuierliche Renditen
ohne lineares Detrending (Diplomarbeit). Ausführlich: Kapitel 7.

Analysemodus extended: volle Historie, lineare Trendentfernung auf Renditen,
zweistufiges ARMA-GARCH. Ausführlich: Kapitel 7.

Training endet am Cutoff-Datum; Prognose bis forecast_end.
Output je Modellordner: Residuen-Diagnostik, Prognoseplots mit
Quantilbändern, Niveau-Rücktransformation, summary.txt und bei thesis
coefficient_abgleich.txt. Wenn ein KI-Modell gewählt wurde, entstehen
TSA_Bericht_<MODELL>_<KI-Modell>.docx/.pdf je Modellordner.
        """.strip(),
    ),
    ManualSection(
        title="7. Analysemodus — thesis und extended",
        body="""
In Korrelation und TSA wählen Sie oben den Analysemodus. Es handelt sich nicht um
zwei verschiedene Modellfamilien, sondern um zwei methodische Setups: thesis
repliziert die Diplomarbeit JW 2008 (R); extended nutzt eine längere Historie
und eine modernere Vorverarbeitung der Renditen.

Gemeinsame Basis — kontinuierliche Renditen
Beide Modi starten von Kursniveaus P_t (z. B. PDAX). Für Schätzung und
Korrelation werden Renditen verwendet:
  r_t = ln(P_t) − ln(P_{t−1})

Thesis — Renditen ohne lineares Detrending
  • Die Modellserie ist y_t = r_t (reine Log-Rendite).
  • Standard-Stichprobe: Dezember 1987 bis Juli 2007 (wie Diplomarbeit).
  • GARCH: Renditen werden vor der Schätzung um den Stichprobenmittelwert
    zentriert (y_t − ȳ); das GARCH-Modell hat Mittelwert Null.
  • ARMA-GARCH: gemeinsame Schätzung in einem Modell (AR-Mittelwert +
    GARCH-Volatilität), analog zu R rugarch mit arma(1,1)+garch(1,1).
  • coefficient_abgleich.txt und KI-Kapitel zum R-Abgleich nur im Modus thesis.

Extended — Renditen mit linearer Trendentfernung
  • Zuerst r_t wie oben, dann lineare Regression über die Zeit:
    r_t = α + β·t + ε_t. Die Modellserie ist das Residuum ε̂_t
    (Trend aus den Renditen entfernt).
  • Standard: volle verfügbare Historie der Zeitreihe (Von/Bis im UI
    schränkt weiter ein).
  • GARCH: ohne Vorab-Zentrierung der Renditen.
  • ARMA-GARCH: zweistufig — zuerst ARMA auf den Renditen, dann GARCH auf
    die ARMA-Residuen (nicht identisch mit der Diplomarbeitsschätzung).

Mathematisch — ARMA und GARCH (kurz)
ARMA(p,q) für den bedingten Mittelwert:
  φ(L)(y_t − μ) = θ(L) ε_t
GARCH(p,q) für die bedingte Varianz:
  σ_t² = ω + α ε_{t−1}² + β σ_{t−1}²
Im thesis-Modus wird bei reinem GARCH oft μ separat über ȳ behandelt; bei
ARMA-GARCH wird der Mittelwert im gemeinsamen arch-Modell mitgeschätzt.

Kreuzkorrelation (CORR)
Die Vorschau zeigt Kursniveaus und Trends. Die Berechnung der Lags verwendet
die transformierten Renditen gemäß Modus (thesis: r_t, extended: ε̂_t).
Pearson-Korrelation zwischen A(t) und B(t+h) bleibt gleich — geändert wird
nur die zugrunde liegende Serie.

Wann welchen Modus?
  • thesis — Vergleich mit Diplomarbeit, R-Koeffizienten, gleiche Stichprobe
  • extended — längere Daten, strukturelle Drifts in Renditen ausgleichen,
    zweistufiges ARMA-GARCH bei vielen Beobachtungen

Der Schalter steht in den Formularen „Korrelation“ und „TSA“ als
„Analysemodus“ (thesis / extended).
        """.strip(),
    ),
    ManualSection(
        title="8. Histogramme und Diagnostik",
        body="""
Histogramme in Phase 0 und bei Residuen enthalten eine eingezeichnete
Normalverteilungskurve (orange): gleicher Mittelwert und Standardabweichung
wie die Stichprobe, skaliert auf die Balkenhöhen.

Vergleichen Sie die Kurve mit den Balken: starke Abweichungen deuten auf
Schiefe, Ausreißer oder multimodale Verteilungen hin — wichtig vor GARCH.
        """.strip(),
    ),
    ManualSection(
        title="9. Output, Tags und KI-Berichte",
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
  • OPENAI_API_KEY für GPT-4o mini, GPT-5 mini und GPT-5 nano
  • GEMINI_API_KEY für Gemini (Provider noch in Entwicklung)
  • Web neu starten

Modellauswahl (5 Optionen im Formular)
  • Ohne KI — Standard, kein Word/PDF-Bericht
  • GPT-4o mini — OpenAI, Vision für Grafiken
  • GPT-5 mini — OpenAI, Vision für Grafiken
  • GPT-5 nano — OpenAI, Vision für Grafiken
  • Gemini — Google (API-Key erforderlich; Auswahl sichtbar auch ohne Key)

Ohne passenden API-Key erscheint das Modell ausgegraut („API-Key fehlt“).

Ablauf
  • Der Analyse-Lauf schreibt zuerst normale Artefakte in output/
  • Pro TSA-Modellordner: TSA_Bericht_<MODELL>_<KI>.docx/.pdf; Korrelation: CORR_Bericht_<KI>.docx/.pdf;
    bei mehreren TSA-Modellen zusaetzlich Reports/Modellvergleich_<KI>.docx/.pdf
  • Aufbau: Executive Summary (Eignung Ja/Nein/Beschränkt, Qualität 1–5), fachliche Auswertung,
    eingebettete Grafiken, Anhang mit summary.txt
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
        title="Analysemodus (thesis / extended)",
        body="Zentraler UI-Schalter für Korrelation und TSA. thesis = Diplomarbeit "
        "JW 2008: feste Stichprobe ab 12/1987, y_t = Δ ln P_t, zentrierte "
        "GARCH-Renditen, gemeinsames ARMA-GARCH. extended = längere Historie, "
        "lineare Detrending auf Renditen, zweistufiges ARMA-GARCH. "
        "Ausführlich im Handbuch Kapitel 7.",
    ),
    ManualSection(
        title="KI-Bericht — Modellauswahl",
        body="Fünf Optionen in Korrelation und TSA: (1) Ohne KI — Standard. "
        "(2) GPT-4o mini, (3) GPT-5 mini, (4) GPT-5 nano über OPENAI_API_KEY. "
        "(5) Gemini über GEMINI_API_KEY. OpenAI-Modelle analysieren PNG-Grafiken "
        "per Vision; Gemini ist konfiguriert, der Provider wird noch ergänzt.",
    ),
    ManualSection(
        title="Volatilität (bedingt)",
        body="σ_t² im GARCH-Modell: prognostizierte Varianz zum Zeitpunkt t "
        "gegeben die Information bis t−1. Grundlage für Value-at-Risk.",
    ),
]
