# Cursor TSLab

Zeitreihenanalyse nach Diplomarbeit JW 2008 (PDAX) – Python, PostgreSQL, später Flask-Dashboard.

## Daten

| Quelle | Pfad |
|--------|------|
| **Werte.csv** | `80_Abschlussarbeit/Material/DAX_Diplom/Werte.csv` |
| **PostgreSQL** | lokal via Docker oder eigene Instanz |

## PostgreSQL frisch installiert

1. Dienst muss laufen (`services.msc` → postgresql-… → **Gestartet**).
2. In **pgAdmin** oder **psql** als `postgres` einloggen (Installations-Passwort).
3. SQL ausfuehren: `scripts/sql/create_tslab_db.sql`  
   (legt User `tslab` / Passwort `tslab` und DB `tslab` an)
4. Im Projekt (`use_sqlite: false` in `config/defaults.yaml`):

```powershell
python scripts/db_check.py
python scripts/db_init.py
python scripts/db_seed_werte.py
python scripts/db_list_series.py
```

**Alternativ** (wenn Sie das postgres-Passwort in PowerShell setzen):

```powershell
$env:TSLAB_PG_ADMIN_URL = "postgresql+psycopg2://postgres:IHR_POSTGRES_PASSWORT@localhost:5432/postgres"
python scripts/setup_postgres.py
```

## Fehler „Connection refused“ auf Port 5432?

PostgreSQL **läuft nicht** auf Ihrem PC. Zuerst prüfen:

```powershell
python scripts/db_check.py
```

**Sofort testen (ohne DB):**

```powershell
python scripts/db_load_series.py pdax --from-csv --start 1987-12-01 --end 2007-06-30
```

**SQLite (ohne PostgreSQL-Server):**

```powershell
$env:TSLAB_DATABASE_URL = "sqlite:///data/tslab.db"
python scripts/db_init.py
python scripts/db_seed_werte.py
python scripts/db_load_series.py pdax --start 1987-12-01 --end 2007-06-30
```

## PostgreSQL einrichten

### 1. Datenbank starten (Docker)

```powershell
cd Cursor_TSLab
docker compose up -d
```

### 2. Python-Abhängigkeiten

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Tabellen anlegen & CSV importieren

```powershell
python scripts/db_init.py
python scripts/db_seed_werte.py
python scripts/db_list_series.py
```

Optional nur PDAX:

```powershell
python scripts/db_seed_werte.py --columns PDAX
```

### 4. Verbindung anpassen

Standard in `config/defaults.yaml`:

`postgresql+psycopg2://tslab:tslab@localhost:5432/tslab`

Überschreiben mit `.env` (siehe `.env.example`):

`TSLAB_DATABASE_URL=...`

### PostgreSQL unter Windows (ohne Docker)

1. Installer von [postgresql.org](https://www.postgresql.org/download/windows/) oder `winget install PostgreSQL.PostgreSQL`
2. Dienst **postgresql-x64-…** starten (Dienste-App / `services.msc`)
3. Datenbank anlegen (pgAdmin oder `psql`):

```sql
CREATE USER tslab WITH PASSWORD 'tslab';
CREATE DATABASE tslab OWNER tslab;
```

4. In `config/defaults.yaml` oder `.env` Zugangsdaten anpassen, falls abweichend.

## Analyse-Zeitfenster (Start / Ende / Cutoff)

| Modus | Parameter | Bedeutung |
|-------|-----------|-----------|
| **Korrelation** | `--start`, `--end` | Nur dieses Fenster wird analysiert |
| **TSA** | `--start`, `--end` | Analyse von Start bis **Ende**; **`end` = Cutoff** (letzter Trainingstag) |
| **TSA** | (automatisch) | Prognose ab dem **naechsten** Datum nach Cutoff bis `--forecast-end` (Standard: letztes verfuegbares Datum) |
| **TSA** | Holdout | Liegen nach Cutoff noch Ist-Werte vor, fliessen sie in **Prognosegrafiken** ein |

**Regel:** Wenn `--end-date` gesetzt ist, wird **Cutoff automatisch = Ende** (kein separates Cutoff noetig).

```powershell
# Korrelation
python scripts/db_load_series.py pdax --mode correlation --from-csv --start 1987-12-01 --end 2007-06-30

# TSA: Training bis 2007-06-30, Holdout Jul–Dez 2007 fuer Prognoseplots
python scripts/db_load_series.py pdax --mode tsa --from-csv --start 1987-12-01 --end 2007-06-30

python scripts/run_phase0_pdax.py --start-date 1987-12-01 --end-date 2007-06-30
```

## Phase 0 (Plots)

```powershell
python scripts/run_phase0_pdax.py --analysis-mode thesis --from-db
python scripts/run_phase0_pdax.py --analysis-mode extended --from-db --end-date 2007-06-30
```

`--analysis-mode` ist **Pflicht**: `thesis` (Diplomarbeit JW 2008) oder `extended` (volle Historie + lineares Detrending auf Renditen).

Ausgabe: `output/phase0_<modus>_<start>_to_<cutoff>/`

## Projektstruktur

| Modul | Aufgabe |
|-------|---------|
| `tslab/db/` | PostgreSQL-Modelle & Engine |
| `tslab/services/timeseries_store.py` | Import, Laden, Slugs |
| `tslab/services/analysis_window.py` | Start/Ende-Analysefenster |
| `tslab/services/ingest_werte.py` | CSV (Fallback) |
| `tslab/services/report_session.py` | optionale KI-Berichte mit Checkpoints / Rate-Limit-Pausen |
| `tslab/web/output_browser.py` | sicherer Zugriff auf Ergebnisdateien und ZIP-Download |
| `scripts/db_*.py` | DB-Setup & Tests |

## Korrelation (2 Zeitreihen)

Liest nur aus der Upload-DB (`observations`), **ohne** diese zu aendern.

```powershell
python scripts/db_init.py
python scripts/run_correlation.py pdax dax --start 1987-12-01 --end 2007-06-30 --max-lag 24
```

Ausgabe: `output/correlation_<a>_vs_<b>_<start>_to_<end>/`

- `lag_correlations.csv` – Tabelle aller Lags
- `cross_correlation.png` – Balkendiagramm
- `aligned_series.png` – beide Reihen im Fenster
- `summary.txt` – Kurzfassung
- Eintrag in `correlation_history` (PostgreSQL)

Verfuegbare Slugs: `python scripts/db_list_series.py`

## Phase 1 (TSA: ARMA, GARCH, ARMA-GARCH)

```powershell
python scripts/run_tsa.py --analysis-mode thesis --from-db
python scripts/run_tsa.py --analysis-mode extended --from-db --end-date 2007-06-30
python scripts/run_tsa.py --analysis-mode thesis --from-db --models garch,arma-garch
```

`--analysis-mode` ist **Pflicht** (`thesis` | `extended`).

Ausgabe: `output/tsa_<modus>_<start>_to_<cutoff>/`

| Ordner | Modell |
|--------|--------|
| `arma11/` | ARMA(1,1) Mittelwert |
| `garch11/` | GARCH(1,1) Volatilitaet (mean=Zero) |
| `arma11_garch11/` | ARMA(1,1) + GARCH(1,1) auf Residuen |

Pro Modell: Residuen/Volatilitaet, Prognose mit Quantilbaendern (0,5 % / 5 % / 50 % / 95 % / 99,5 %), `summary.txt`.

Im Web kann die Modellordnung automatisch per AIC gewaehlt werden oder als
User-Order (p, q) fuer ARMA und GARCH gesetzt werden. Prognoseplots zeigen
standardmaessig nur den rechten Ausschnitt um den Cutoff; das sichtbare
Fenster wird ueber `forecast_plot_window` in `config/defaults.yaml` oder im
TSA-Formular gesteuert.

## Web-Dashboard (Flask + PostgreSQL)

Standard in `config/defaults.yaml`: `database.use_sqlite: false`, URL `postgresql+psycopg2://tslab:tslab@localhost:5432/tslab`.

```powershell
docker compose up -d
python scripts/prepare_web_postgres.py
python scripts/run_web.py --no-mock-fallback
```

Ohne Docker (lokaler PostgreSQL-Dienst):

```powershell
python scripts/setup_postgres.py
python scripts/prepare_web_postgres.py
python scripts/run_web.py --no-mock-fallback
```

**Live (PostgreSQL):** Serienliste, Überlappung, Korrelation (`POST /api/correlation/run`), TSA (`POST /api/tsa/run`), Upload-Vorschau und CSV-Import.  
**Mock-Fallback:** Nur wenn die DB nicht erreichbar ist (`--mock` erzwingt Mock; `--no-mock-fallback` erzwingt PostgreSQL).

### Tags, Suche und Ergebnisordner

Die Web-Listen fuer Zeitreihen, Korrelationen und TSA-Laeufe unterstuetzen
Suche und Tag-Filter. Tags sind n:m-Zuordnungen in `entity_categories`; neue
Analyse-Laeufe erben die Vereinigung der Tags ihrer beteiligten Zeitreihen.
Die reservierte Kategorie `Reporting` markiert berichtsrelevante Eintraege und
kann nicht geloescht werden.

Ergebnisordner sind ueber `/output/browse/` erreichbar. Einzeldateien werden
nur fuer freigegebene Endungen ausgeliefert (`.png`, `.jpg`, `.txt`, `.csv`,
`.xlsx`, `.pdf`, `.docx`, `.html`, `.json`), Unterordner koennen als ZIP
heruntergeladen werden.

### Optionale KI-Berichte (Word/PDF)

KI-Berichte sind standardmaessig deaktiviert. Aktivierung fuer das Web:

```powershell
$env:TSLAB_AI_REPORTS_ENABLED = "1"
$env:OPENAI_API_KEY = "sk-..."
python scripts/run_web.py --no-mock-fallback
```

Alternativ koennen die Werte in einer lokalen `.env` oder in
`config/defaults.yaml` gesetzt werden; API-Keys nicht committen. Die
verfuegbaren Modelle kommen aus `ai_reports.models`. Aktuell ist OpenAI
implementiert (`openai:gpt-4o-mini`, `openai:gpt-4o`); Gemini ist vorbereitet,
aber im Provider noch nicht implementiert.

Workflow:

1. In Korrelation oder TSA im Abschnitt "KI-Bericht (optional)" ein Modell
   waehlen.
2. Der Analyse-Lauf schreibt zuerst die normalen Artefakte in `output/`.
3. Danach erzeugt die Report-Session KI-Auswertungen aus PNG, TXT und
   Tabellen. Bei TSA wird je Modellordner ein Bericht erstellt.
4. Nach jeweils 5 KI-Anfragen oder bei API-Rate-Limits fragt die Weboberflaeche
   nach einer 1-Minuten-Pause oder vorzeitigem Abschluss.

Artefakte:

- `ai_bericht.docx` und `ai_bericht.pdf` im Korrelationsordner bzw. je
  TSA-Modellordner.
- `Reports/laufbericht.pdf` mit Laufzeiten, Tokenverbrauch, Langfuse-Status,
  Rate-Limit-/Pausenereignissen und Links zu erzeugten Berichten.

Troubleshooting:

- Keine Modelloption sichtbar: `TSLAB_AI_REPORTS_ENABLED=1` und
  `OPENAI_API_KEY` pruefen, Web neu starten.
- "Keine Berichtsziele": Der Zielordner enthaelt keine passenden PNG/TXT/
  Tabellenartefakte.
- Rate-Limit-Dialog: "Pause" wartet 60 Sekunden und setzt den Checkpoint
  zurueck; "Abschliessen" erstellt einen unvollstaendigen Bericht mit Hinweis.

## Nächste Schritte

1. Gemini-Provider fertig implementieren und in `requirements.txt` ergaenzen.
2. Interaktive HTML-Charts fuer TSA-Ergebnisse vervollstaendigen.
3. Lang laufende Analysejobs in einen Hintergrund-Worker auslagern.
