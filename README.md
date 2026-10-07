# Telecom KPI Reporting Backend

Read-only FastAPI service for saved results from the [ML backend](https://github.com/Bored-Pawar/ML_Backend_JIO). The [frontend](https://github.com/Bored-Pawar/JIO_ML_APPLICATION-FRONTEND) uses this API to inspect training reports and inference anomalies. Reporting reads shared run storage directly, does not import ML modules, and does not train models or execute inference.

Developed by Aditya Pramod Pawar under the mentorship of Sanjana Chaudhary.

## Capabilities and API

The default prefix is `/api/v1`. All report routes are GET requests:

| Path below `/api/v1/reports` | Purpose |
| --- | --- |
| `/runs/{run_id}` | Manifest-derived run summary, attempts, inference readiness and invocation count. |
| `/runs/{run_id}/attempts/{attempt_id}` | Attempt summary and stage state. |
| `/runs/{run_id}/attempts/{attempt_id}/stages/{stage}` | Completed Part A–D report, summaries and artefact metadata/previews. Stage names accept forms such as `part-a`. |
| `/runs/{run_id}/inference` | Saved inference invocation list. |
| `/runs/{run_id}/inference/{invocation_id}` | Saved inference summary and artefact information. |
| `/runs/{run_id}/inference/{invocation_id}/results` | Filtered, sorted result page, anomalies first by default. |
| `/runs/{run_id}/inference/{invocation_id}/filter-options` | Available result filter values. |

Results default to `mode=anomalies`, `page=1`, `page_size=50`, `sort_by=timestamp`, and `sort_order=asc`. `mode=all` includes normal rows. Page sizes must be 1–100. Filters are `composite_id`, `circle`, `cluster`, `site_name`, `kpi`, `status`, `start_time`, and `end_time`. Text matching is exact and case-insensitive. Time bounds are inclusive; timestamps without an offset are interpreted as UTC. URL-encode timestamp offsets containing `+`.

Sorting accepts timestamp, series/identity, KPI, actual value and anomaly/status fields. Invalid settings return structured errors. Responses include `items`, `pagination`, `filters_applied`, and `source`. Filter options come from saved output metadata and CSV status values; neither route reruns inference.

Reports resolve `runs/<run_id>/manifest.json`, completed execution snapshots, and referenced outputs. Artefact paths must stay inside their owning run; recorded paths can be remapped when a whole run is relocated. Reports expose relative artefact metadata and bounded CSV previews, not an arbitrary file-browser/download endpoint. Preview rows default to 20 and can be configured from 0–500. There is no standalone raw-manifest endpoint; manifests supply report summaries.

## Stack and layout

Python, FastAPI, Uvicorn, Pydantic and Pydantic Settings; JSON/CSV reading uses the standard library. Runtime dependencies are in [requirements.txt](requirements.txt).

```text
app/main.py             FastAPI assembly, health and CORS
app/api/reports.py      GET report routes
app/core/               Settings, path boundary and exceptions
app/readers/            Manifests, snapshots and Part A–E outputs
app/services/           Report assembly
app/schemas/            Public report contracts
tests/test_reporting.py Fixture-based unittest tests
manual_smoke_test.py    Live-server checks with a local run path
.env.example            Example settings (see caveats below)
```

## Setup and server

Run from this repository root. The inspected shared development interpreter is Python 3.12; supported versions are not declared. Reporting needs read access to ML run storage and saved manifests/results. The frontend and ML server run separately.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:ML_RUNS_ROOT = (Resolve-Path '../ML_backend/runs').Path
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

The path command assumes sibling checkouts named `ML_backend` and `reporting_backend` and an existing ML `runs/` directory. Otherwise set `ML_RUNS_ROOT` to the absolute directory containing run folders. On POSIX shells activate with `source .venv/bin/activate` and use `export ML_RUNS_ROOT=/absolute/path/to/runs`.

**Listener configuration:** settings declare `REPORTING_HOST=127.0.0.1` and `REPORTING_PORT=8001`, but `app/main.py` does not pass them to Uvicorn. A bare Uvicorn command uses port 8000. The explicit command above serves **127.0.0.1:8001**. Change `--host`/`--port` and update the frontend reporting URL to change it.

**Environment-file location:** settings read `.env` from this repository's parent directory (`Path(__file__).resolve().parents[3]`), not this repository root. Copying `.env.example` to a repository-local `.env` alone has no effect. Use process variables as above, or deliberately configure the parent `.env`; process variables take precedence. Relative paths resolve against the current working directory.

Other settings include `REPORTING_API_PREFIX`, `DEFAULT_FILE_ENCODING`, `MAX_CSV_PREVIEW_ROWS`, and `CORS_ALLOWED_ORIGINS`. Use a JSON array for CORS:

```powershell
$env:CORS_ALLOWED_ORIGINS = '["http://localhost:5173","http://127.0.0.1:5173"]'
```

Code defaults allow these Vite origins, but `.env.example` specifies `http://localhost:3000`; adjust the example when using Vite. Restart after setting changes. `ML_REGISTRY_ROOT` is reserved and does not enable run discovery; `REPORT_OUTPUT_ROOT` does not cause current report routes to generate files. The service never writes below `ML_RUNS_ROOT`.

## API documentation and checks

At the explicit address above: [Swagger UI](http://127.0.0.1:8001/docs), [ReDoc](http://127.0.0.1:8001/redoc), and [OpenAPI JSON](http://127.0.0.1:8001/openapi.json). `GET /health` checks liveness, not readability of every saved run.

```powershell
python -m unittest discover -s tests -v
Invoke-RestMethod http://127.0.0.1:8001/health
```

Fixture tests cover reports, read-only access, pagination/filtering, malformed/missing artefacts, and path traversal/relocation without real training. `manual_smoke_test.py` additionally checks a live server but contains a machine-specific `RUN_DIRECTORY`; configure it before use. `REPORTING_BASE_URL` changes that script's server address.

## Troubleshooting and limitations

- Run not found: check that `ML_RUNS_ROOT` contains run-ID folders rather than pointing at one run. Reporting does not discover all runs through the registry.
- Address already in use: reuse the intended running server or choose another `--port` and update the frontend reporting URL.
- Unavailable report: verify the selected stage/invocation completed and its saved result references exist.
- Missing/unsafe artefact: preserve the full run and manifest references; arbitrary external paths are rejected.
- Browser CORS error: match the actual frontend origin in `CORS_ALLOWED_ORIGINS` and check the explicit listener port.
- Temporary-directory permission error in tests: use an environment that permits fixture creation and cleanup.
- Pagination bounds response size, but filtering/sorting scans referenced CSVs and holds matching rows in memory; there is no database-backed reporting index.

## Information Needed / Assumptions

No Docker/Compose files were found. Confirm supported Python versions and intended production/shared-storage deployment details. These instructions establish local development only.
