# Supabase + Streamlit Cloud setup (persistent DB)

You asked for “make it persistent so data never disappears”. Streamlit Community Cloud does **not** guarantee persistence for local SQLite. The correct solution is to use a managed Postgres (Supabase).

## 1) Get the right connection string from Supabase

1. Open your Supabase project dashboard.
2. Go to **Project Settings → Database**.
3. Find **Connection string**.
4. Select **Transaction pooler** (recommended for Streamlit Cloud).
5. Copy the **URI** (it looks like `postgresql://...`).

Notes:
- Pooler often uses port **6543** (not 5432).
- Prefer the URI that already includes `sslmode=require`.

## 2) Add it to Streamlit Cloud Secrets

1. Open your Streamlit app.
2. Click **Manage app** (bottom-right).
3. Go to **Settings → Secrets**.
4. Paste this (TOML format):

```toml
DATABASE_URL = "PASTE_THE_SUPABASE_URI_HERE"
```

Important:
- Put it at the **top-level** (not inside `[section]`).
- Keep it in **quotes**.

## 3) Reboot the app

After saving secrets, wait ~1 minute, then click **Reboot app**.

## 4) Verify inside the app

- The app shows `Build: ... commit=...`.
- In **⚙️ Σύστημα** it should display `Τύπος Βάσης: postgres`.

## Common mistakes

- Using placeholders like `host` / `DBNAME` instead of the real Supabase host/database.
- Copying the “Direct connection” string when your project has network restrictions.
- Password contains special characters and the URI is not URL-encoded.

If you paste the diagnostics shown by the app (host/port/db/sslmode) I can tell you exactly which field is wrong, without you sharing passwords.
