# Reporting backend

Read-only FastAPI service for completed Telecom ML backend artifacts. It never imports
`ML_backend` modules and never writes below `ML_RUNS_ROOT`.

Configure it with environment variables or a local `.env` copied from `.env.example`.
Run with `uvicorn app.main:app --app-dir reporting_backend`.

Known report lookup uses `runs/<run_id>/manifest.json`; the optional registry setting is
reserved for future run discovery and is not used to resolve reports.
