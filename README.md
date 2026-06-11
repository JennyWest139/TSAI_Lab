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

## Nächste Schritte

1. Flask-Dashboard (Upload, Historie, Datumsauswahl in UI)
2. PDF-Berichte (Gleichungen, Parameter, Diagnostik)
3. KI-Bericht zur Korrelation (optional)
