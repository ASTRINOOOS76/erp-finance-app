# Copilot instructions (erp-finance-app)

## Big picture
- This is a single-file Streamlit ERP/finance app: the whole UI + logic lives in [app.py](app.py).
- Data is stored in a SQL database via a global SQLAlchemy `ENGINE`:
  - Default: local SQLite file (see `DB_FILE` resolution in [app.py](app.py)).
  - Prod/persistent: Postgres (Supabase) when `DATABASE_URL` is set (Streamlit Secrets preferred).
- Two tables form the core data model (created in `init_db()` in [app.py](app.py)):
  - `journal` (transactions)
  - `gl_codes` (GL lookup)

## Run/debug workflows
- Dev container auto-runs Streamlit on attach (see [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json)); app is on port `8501`.
- Manual run (local/dev): `streamlit run app.py`.
- Streamlit file watching is configured for containers (polling) in [.streamlit/config.toml](.streamlit/config.toml).
- Optional diagnostics:
  - `ERP_SHOW_DEBUG=1` shows build/commit stamp and a sidebar button to clear Streamlit caches + session state.

## Database + environment conventions
- Preferred config order for Postgres:
  1) `st.secrets["DATABASE_URL"]` (Streamlit Cloud)
  2) `DATABASE_URL` env var
- `DATABASE_URL` is normalized to ensure `postgresql://` and `sslmode=require` (see `_normalize_database_url()` in [app.py](app.py)).
- SQLite path can be overridden via `ERP_DB_PATH`.
- Streamlit Cloud special-case: SQLite is copied to `~/.erp_finance_app/…` for better persistence across redeploys, but Postgres is the recommended durable store (see [SUPABASE_SETUP.md](SUPABASE_SETUP.md)).

## Code patterns to follow (project-specific)
- DB access:
  - Writes use the helper wrappers `db_execute()`, `db_executemany()` (SQLAlchemy `text()` with `:named` params).
  - Reads often use `pd.read_sql_query(sql, ENGINE)`.
  - If you add/change schema, update `init_db()` and keep Postgres vs SQLite type differences in mind (`SERIAL` vs `AUTOINCREMENT`, `DOUBLE PRECISION` vs `REAL`).
- UI navigation is a single `menu = st.sidebar.radio(...)` list and a corresponding `if/elif` block in [app.py](app.py). Add new screens by extending both.
- Data cleanup uses `clean_dataframe(df)` (notably: numeric coercion, trimming strings, gross recalculation).
- First-run/empty DB flow imports transactions from an uploaded Excel file (expects a `Journal` sheet if present) — keep this path working when modifying columns.

## Integration points / files to know
- Supabase/Streamlit Cloud setup: [SUPABASE_SETUP.md](SUPABASE_SETUP.md)
- Example secrets format (do not commit real creds): [.streamlit/secrets.example.toml](.streamlit/secrets.example.toml)
- Dependencies: [requirements.txt](requirements.txt) (Postgres driver is `psycopg2-binary`)

## Guardrails
- Don’t introduce new modules/packages unless necessary; this repo is intentionally monolithic (`app.py`).
- Never log or commit real `DATABASE_URL` credentials; use secrets/env vars.
