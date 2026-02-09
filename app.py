import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import time
import subprocess
from typing import Any, Dict, Iterable, Optional, Set
from datetime import datetime, date
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


# --- Build / Debug stamp ---
# Helps verify that the running Streamlit instance is using THIS file and that edits are being picked up.
def _build_stamp() -> str:
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(__file__)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        mtime = "unknown"

    commit = "unknown"
    # Streamlit Community Cloud clones the repo; try to extract the commit hash.
    try:
        if os.path.isdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".git")):
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
    except Exception:
        pass

    return f"{mtime} | commit={commit} | pid={os.getpid()} | {os.path.abspath(__file__)}"

# --- 1. CONFIG ---
st.set_page_config(page_title="SalesTree ERP Final", layout="wide", page_icon="🏢")

# Theme management
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'  # default to light

# Optional diagnostics (disabled by default)
SHOW_DEBUG = os.getenv("ERP_SHOW_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
if SHOW_DEBUG:
    st.sidebar.caption(f"Build: {_build_stamp()}")
    with st.sidebar.expander("Debug", expanded=False):
        if st.button("Reset session + clear cache", width='stretch'):
            try:
                st.cache_data.clear()
            except Exception:
                pass
            try:
                st.cache_resource.clear()
            except Exception:
                pass
            try:
                st.session_state.clear()
            except Exception:
                pass
            st.rerun()
    st.caption(f"Build: {_build_stamp()}")

def _resolve_db_file() -> str:
    # Allow explicit override (useful for persistent external volumes).
    override = os.getenv("ERP_DB_PATH")
    if override:
        return override

    here = os.path.dirname(os.path.abspath(__file__))
    repo_db = os.path.join(here, "erp_tax_fixed_v2.db")

    # Prefer an existing DB in the user's home directory (persisted outside the repo).
    # This is useful in containers/dev where the repo working tree might be ephemeral.
    home_db = os.path.join(os.path.expanduser("~"), ".erp_finance_app", "erp_tax_fixed_v2.db")
    if os.path.exists(home_db):
        return home_db

    # Streamlit Community Cloud runs the app from /mount/src/<repo>.
    # Files under the repo directory may be replaced on redeploy; also permissions can vary.
    # Store the DB in the home directory to avoid "stale" DB resets.
    if os.path.abspath(__file__).startswith("/mount/src/"):
        db_dir = os.path.join(os.path.expanduser("~"), ".erp_finance_app")
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, "erp_tax_fixed_v2.db")

    return repo_db


DB_FILE = _resolve_db_file()


def _resolve_database_url() -> Optional[str]:
    # Prefer Streamlit secrets when available.
    try:
        if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
            v = str(st.secrets["DATABASE_URL"]).strip()
            return v or None
    except Exception:
        pass
    v = os.getenv("DATABASE_URL")
    return v.strip() if v else None


def _normalize_database_url(url: str) -> str:
    u = url.strip()
    if not u:
        return u

    # SQLAlchemy prefers postgresql:// over postgres://
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]

    parsed = urlparse(u)
    if parsed.scheme not in ("postgresql", "postgres"):  # allow only postgres here
        return u

    # Supabase typically requires SSL. If sslmode not specified, default may fail.
    qs = parse_qs(parsed.query)
    if "sslmode" not in qs:
        qs["sslmode"] = ["require"]
    query = urlencode(qs, doseq=True)

    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


def _safe_db_diagnostics() -> Dict[str, str]:
    if DB_DIALECT != "postgres" or not DATABASE_URL:
        return {"dialect": DB_DIALECT}
    parsed = urlparse(DATABASE_URL)
    qs = parse_qs(parsed.query)
    return {
        "dialect": DB_DIALECT,
        "host": parsed.hostname or "",
        "port": str(parsed.port or ""),
        "db": (parsed.path or "").lstrip("/"),
        "sslmode": (qs.get("sslmode", [""])[0] or ""),
    }


def _looks_like_placeholder(d: Dict[str, str]) -> bool:
    return (d.get("host") in {"host", "HOST", "example.com", "localhost", "127.0.0.1", ""}) or (
        d.get("db") in {"DBNAME", "dbname", "database", ""}
    )


DATABASE_URL = _resolve_database_url()
if DATABASE_URL:
    DATABASE_URL = _normalize_database_url(DATABASE_URL)
DB_DIALECT = "sqlite"
if DATABASE_URL and DATABASE_URL.startswith(("postgres://", "postgresql://")):
    DB_DIALECT = "postgres"

# Optional safety gate: prevent accidental writes to local SQLite when you expect Supabase.
ERP_REQUIRE_POSTGRES = os.getenv("ERP_REQUIRE_POSTGRES", "").strip().lower() in {"1", "true", "yes", "y"}
if ERP_REQUIRE_POSTGRES and DB_DIALECT != "postgres":
    st.error(
        "Απαιτείται Postgres/Supabase για μόνιμη αποθήκευση, αλλά δεν βρέθηκε έγκυρο DATABASE_URL. "
        "Βάλε `DATABASE_URL` (Streamlit Secrets ή env var) και κάνε reboot."
    )
    st.stop()


def _build_engine():
    if DB_DIALECT == "postgres":
        # Supabase provides a Postgres URL.
        return create_engine(DATABASE_URL, pool_pre_ping=True)
    # SQLite (local/dev). Use SQLAlchemy so code paths match Postgres.
    return create_engine(
        f"sqlite+pysqlite:///{DB_FILE}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )


ENGINE = _build_engine()


def db_execute(sql: str, params: Optional[Dict[str, Any]] = None) -> None:
    with ENGINE.begin() as conn:
        conn.execute(text(sql), params or {})


def db_executemany(sql: str, rows: Iterable[Dict[str, Any]]) -> None:
    with ENGINE.begin() as conn:
        conn.execute(text(sql), list(rows))


def db_scalar(sql: str, params: Optional[Dict[str, Any]] = None, default: Any = None) -> Any:
    try:
        with ENGINE.connect() as conn:
            res = conn.execute(text(sql), params or {})
            v = res.scalar()
            return default if v is None else v
    except Exception:
        return default

# Theme management
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'  # default to light

def apply_theme_css():
    if st.session_state.theme == 'dark':
        css = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            * { font-family: 'Inter', 'Segoe UI', sans-serif !important; }
            
            .stApp { 
                background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%) !important;
                color: #e0e0e0 !important;
            }
            
            h1 { 
                color: #ffffff !important; 
                font-size: 2.5rem !important;
                font-weight: 700 !important;
                letter-spacing: -1px !important;
                margin-bottom: 1.5rem !important;
            }
            
            h2 { 
                color: #b0b0b0 !important; 
                font-size: 2rem !important;
                font-weight: 700 !important;
                margin-top: 1.5rem !important;
                margin-bottom: 1rem !important;
            }
            
            h3, h4 { 
                color: #c0c0c0 !important;
                font-weight: 600 !important;
            }
            
            p, span, label, li { 
                color: #d0d0d0 !important;
                font-size: 0.95rem !important;
                line-height: 1.6 !important;
            }
            
            [data-testid="stSidebar"] { 
                background: linear-gradient(180deg, #2d2d2d 0%, #1a1a1a 100%) !important;
                border-right: 2px solid #404040 !important;
            }
            
            [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
                color: #ffffff !important;
            }
            
            div[data-testid="metric-container"] {
                background: linear-gradient(135deg, #3a3a3a 0%, #2d2d2d 100%) !important;
                border: 2px solid #404040 !important;
                padding: 15px !important;
                border-radius: 8px !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
            }
            
            div[data-testid="metric-container"] label { 
                color: #b0b0b0 !important;
                font-weight: 600 !important;
                font-size: 0.85rem !important;
                text-transform: uppercase !important;
                letter-spacing: 0.5px !important;
            }
            
            div[data-testid="metric-container"] [data-testid="stMetricValue"] { 
                color: #ffffff !important;
                font-weight: 700 !important;
                font-size: 1.8rem !important;
            }
            
            .stTextInput input, .stNumberInput input { 
                background-color: #404040 !important;
                color: #e0e0e0 !important;
                border: 1.5px solid #606060 !important;
                border-radius: 6px !important;
                font-size: 0.95rem !important;
                padding: 8px 12px !important;
            }
            
            .stTextInput input:focus, .stNumberInput input:focus { 
                border: 1.5px solid #808080 !important;
                box-shadow: 0 0 0 3px rgba(128, 128, 128, 0.1) !important;
            }
            
            .stSelectbox div { 
                background-color: #404040 !important;
                color: #e0e0e0 !important;
                border: 1.5px solid #606060 !important;
                border-radius: 6px !important;
            }
            
            .stButton>button {
                background: linear-gradient(135deg, #606060 0%, #808080 100%) !important;
                color: #ffffff !important;
                border: none !important;
                border-radius: 6px !important;
                font-weight: 600 !important;
                font-size: 0.95rem !important;
                padding: 10px 24px !important;
                cursor: pointer !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
                transform: translateY(0) !important;
            }
            
            .stButton>button:hover {
                background: linear-gradient(135deg, #808080 0%, #a0a0a0 100%) !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
                transform: translateY(-2px) scale(1.02) !important;
            }
            
            .stInfo {
                background-color: #2d4a5a !important;
                border-left: 4px solid #606060 !important;
            }
            
            .stSuccess {
                background-color: #2d5a2d !important;
                border-left: 4px solid #4a8a4a !important;
                animation: successPulse 0.6s ease-out !important;
            }
            
            .stWarning {
                background-color: #5a4a2d !important;
                border-left: 4px solid #8a7a4a !important;
            }
            
            .stError {
                background-color: #5a2d2d !important;
                border-left: 4px solid #8a4a4a !important;
            }
            
            .stDataFrame {
                background-color: #3a3a3a !important;
                color: #e0e0e0 !important;
            }
            
            .stDataFrame th {
                background-color: #2d2d2d !important;
                color: #ffffff !important;
            }
            
            .stDataFrame td {
                background-color: #3a3a3a !important;
                color: #e0e0e0 !important;
            }
            
            /* Mobile Responsiveness */
            @media (max-width: 768px) {
                .main .block-container {
                    padding-left: 0.5rem !important;
                    padding-right: 0.5rem !important;
                }
                
                h1 {
                    font-size: 1.75rem !important;
                    margin-bottom: 1rem !important;
                }
                
                h2 {
                    font-size: 1.25rem !important;
                    margin-top: 1rem !important;
                    margin-bottom: 0.75rem !important;
                }
                
                .stButton>button {
                    padding: 0.75rem 1rem !important;
                    font-size: 0.9rem !important;
                    width: 100% !important;
                    margin-bottom: 0.5rem !important;
                }
                
                .stTextInput input, .stNumberInput input, .stSelectbox div {
                    font-size: 0.9rem !important;
                    padding: 0.5rem !important;
                }
                
                .stDataFrame {
                    font-size: 0.8rem !important;
                }
                
                .stDataFrame th, .stDataFrame td {
                    padding: 0.5rem !important;
                }
                
                div[data-testid="metric-container"] {
                    padding: 1rem !important;
                    margin-bottom: 1rem !important;
                }
                
                div[data-testid="metric-container"] [data-testid="stMetricValue"] {
                    font-size: 1.5rem !important;
                }
            }

            /* Hide expander chevrons ("arrow") for cleaner UI */
            div[data-testid="stExpander"] details summary svg {
                display: none !important;
            }
        </style>
        """
    else:
        css = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            * { font-family: 'Inter', 'Segoe UI', sans-serif !important; }
            
            .stApp { 
                background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%) !important;
            }
            
            h1 { 
                color: #1a365d !important; 
                font-size: 2.5rem !important;
                font-weight: 700 !important;
                letter-spacing: -1px !important;
                margin-bottom: 1.5rem !important;
            }
            
            h2 { 
                color: #2d5a8c !important; 
                font-size: 2rem !important;
                font-weight: 700 !important;
                margin-top: 1.5rem !important;
                margin-bottom: 1rem !important;
            }
            
            h3, h4 { 
                color: #34568b !important;
                font-weight: 600 !important;
            }
            
            p, span, label, li { 
                color: #0f172a !important;
                font-size: 0.95rem !important;
                line-height: 1.6 !important;
            }
            
            [data-testid="stSidebar"] { 
                background: linear-gradient(180deg, #f8f9fa 0%, #e8ecf1 100%) !important;
                border-right: 2px solid #cbd5e0 !important;
            }
            
            [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
                color: #1a365d !important;
            }
            
            div[data-testid="metric-container"] {
                background: linear-gradient(135deg, #ffffff 0%, #f0f4f8 100%) !important;
                border: 2px solid #cbd5e0 !important;
                padding: 15px !important;
                border-radius: 8px !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
            }
            
            div[data-testid="metric-container"] label { 
                color: #34568b !important;
                font-weight: 600 !important;
                font-size: 0.85rem !important;
                text-transform: uppercase !important;
                letter-spacing: 0.5px !important;
            }
            
            div[data-testid="metric-container"] [data-testid="stMetricValue"] { 
                color: #1a365d !important;
                font-weight: 700 !important;
                font-size: 1.8rem !important;
            }
            
            .stTextInput input, .stNumberInput input { 
                background-color: #ffffff !important;
                color: #0f172a !important;
                border: 1.5px solid #cbd5e0 !important;
                border-radius: 6px !important;
                font-size: 0.95rem !important;
                padding: 8px 12px !important;
            }
            
            .stTextInput input:focus, .stNumberInput input:focus { 
                border: 1.5px solid #2d5a8c !important;
                box-shadow: 0 0 0 3px rgba(45, 90, 140, 0.1) !important;
            }
            
            .stSelectbox div { 
                background-color: #ffffff !important;
                color: #0f172a !important;
                border: 1.5px solid #cbd5e0 !important;
                border-radius: 6px !important;
            }
            
            .stButton>button {
                background: linear-gradient(135deg, #2d5a8c 0%, #1a365d 100%) !important;
                color: #ffffff !important;
                border: none !important;
                border-radius: 6px !important;
                font-weight: 600 !important;
                font-size: 0.95rem !important;
                padding: 10px 24px !important;
                cursor: pointer !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                box-shadow: 0 2px 8px rgba(45, 90, 140, 0.2) !important;
                transform: translateY(0) !important;
            }
            
            .stButton>button:hover {
                background: linear-gradient(135deg, #1a365d 0%, #0f1f3c 100%) !important;
                box-shadow: 0 4px 12px rgba(45, 90, 140, 0.3) !important;
                transform: translateY(-2px) scale(1.02) !important;
            }
            
            .stInfo {
                background-color: #e8f4f8 !important;
                border-left: 4px solid #2d5a8c !important;
            }
            
            .stSuccess {
                background-color: #e8f8e8 !important;
                border-left: 4px solid #2d8a2d !important;
                animation: successPulse 0.6s ease-out !important;
            }
            
            @keyframes successPulse {
                0% { transform: scale(1); opacity: 0; }
                50% { transform: scale(1.05); opacity: 1; }
                100% { transform: scale(1); opacity: 1; }
            }
            
            .stWarning {
                background-color: #fdf8e8 !important;
                border-left: 4px solid #8a7a2d !important;
            }
            
            .stError {
                background-color: #fce8e8 !important;
                border-left: 4px solid #8a2d2d !important;
            }
            
            /* Mobile Responsiveness */
            @media (max-width: 768px) {
                .main .block-container {
                    padding-left: 0.5rem !important;
                    padding-right: 0.5rem !important;
                }
                
                h1 {
                    font-size: 1.75rem !important;
                    margin-bottom: 1rem !important;
                }
                
                h2 {
                    font-size: 1.25rem !important;
                    margin-top: 1rem !important;
                    margin-bottom: 0.75rem !important;
                }
                
                .stButton>button {
                    padding: 0.75rem 1rem !important;
                    font-size: 0.9rem !important;
                    width: 100% !important;
                    margin-bottom: 0.5rem !important;
                }
                
                .stTextInput input, .stNumberInput input, .stSelectbox div {
                    font-size: 0.9rem !important;
                    padding: 0.5rem !important;
                }
                
                .stDataFrame {
                    font-size: 0.8rem !important;
                }
                
                .stDataFrame th, .stDataFrame td {
                    padding: 0.5rem !important;
                }
                
                div[data-testid="metric-container"] {
                    padding: 1rem !important;
                    margin-bottom: 1rem !important;
                }
                
                div[data-testid="metric-container"] [data-testid="stMetricValue"] {
                    font-size: 1.5rem !important;
                }
            }

            /* Hide expander chevrons ("arrow") for cleaner UI */
            div[data-testid="stExpander"] details summary svg {
                display: none !important;
            }
        </style>
        """
    st.markdown(css, unsafe_allow_html=True)

# --- 2. CSS (ΧΡΩΜΑΤΑ ΚΑΙ ΤΥΠΟΓΡΑΦΙΑ) ---
apply_theme_css()

# --- 3. DATABASE SETUP ---
# NOTE: The app now uses SQLAlchemy Engine (ENGINE) so it can run on SQLite locally
# and on a persistent Postgres (e.g., Supabase) in Streamlit Cloud.

def clean_dataframe(df):
    """Καθαρίζει τα δεδομένα - αντικαθιστά NaN με 0 για numeric columns"""
    numeric_cols = ['amount_net', 'vat_amount', 'amount_gross']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    # Replace 'nan' strings and None with empty string in text columns
    text_cols = [
        'counterparty',
        'description',
        'payment_method',
        'bank_account',
        'doc_no',
        'doc_type',
        'status',
        'gl_code',
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna('')
            df[col] = df[col].astype(str).replace(['nan', 'None', '<NA>'], '')
            df[col] = df[col].str.strip()
    
    # Ensure amount_gross = amount_net + vat_amount if amount_gross is 0
    if all(col in df.columns for col in ['amount_gross', 'amount_net', 'vat_amount']):
        df.loc[df['amount_gross'] == 0, 'amount_gross'] = df['amount_net'] + df['vat_amount']
    
    return df

def init_db():
    if DB_DIALECT == "postgres":
        db_execute(
            """CREATE TABLE IF NOT EXISTS journal (
                id SERIAL PRIMARY KEY,
                doc_date DATE,
                doc_no TEXT,
                doc_type TEXT,
                counterparty TEXT,
                description TEXT,
                gl_code TEXT,
                amount_net DOUBLE PRECISION,
                vat_amount DOUBLE PRECISION,
                amount_gross DOUBLE PRECISION,
                payment_method TEXT,
                bank_account TEXT,
                status TEXT
            )"""
        )
        db_execute(
            """CREATE TABLE IF NOT EXISTS gl_codes (
                code TEXT PRIMARY KEY,
                description TEXT
            )"""
        )
        db_execute(
            """CREATE TABLE IF NOT EXISTS counterparties (
                name TEXT PRIMARY KEY,
                kind TEXT NOT NULL DEFAULT 'other'
            )"""
        )
        db_execute(
            """CREATE TABLE IF NOT EXISTS bank_accounts (
                name TEXT PRIMARY KEY,
                kind TEXT NOT NULL DEFAULT 'bank'
            )"""
        )
    else:
        db_execute(
            """CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_date DATE, doc_no TEXT, doc_type TEXT,
                counterparty TEXT, description TEXT, gl_code TEXT,
                amount_net REAL, vat_amount REAL, amount_gross REAL,
                payment_method TEXT, bank_account TEXT, status TEXT
            )"""
        )
        db_execute(
            """CREATE TABLE IF NOT EXISTS gl_codes (
                code TEXT PRIMARY KEY, description TEXT
            )"""
        )
        db_execute(
            """CREATE TABLE IF NOT EXISTS counterparties (
                name TEXT PRIMARY KEY,
                kind TEXT NOT NULL DEFAULT 'other'
            )"""
        )
        db_execute(
            """CREATE TABLE IF NOT EXISTS bank_accounts (
                name TEXT PRIMARY KEY,
                kind TEXT NOT NULL DEFAULT 'bank'
            )"""
        )

    _ensure_journal_schema()
    
    # Create indices for common queries
    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_doc_date ON journal(doc_date)",
        "CREATE INDEX IF NOT EXISTS idx_counterparty ON journal(counterparty)",
        "CREATE INDEX IF NOT EXISTS idx_doc_type ON journal(doc_type)",
        "CREATE INDEX IF NOT EXISTS idx_bank_account ON journal(bank_account)",
        "CREATE INDEX IF NOT EXISTS idx_status ON journal(status)",
    ]:
        try:
            db_execute(stmt)
        except Exception:
            pass

    # Normalize legacy mixed-type values (SQLite-only; Postgres enforces types)
    if DB_DIALECT == "sqlite":
        try:
            db_execute("UPDATE journal SET doc_type = '' WHERE doc_type IS NULL")
            mixed_doc_type = db_scalar(
                "SELECT count(*) FROM journal WHERE doc_type IS NOT NULL AND typeof(doc_type) != 'text'",
                default=0,
            )
            if mixed_doc_type and mixed_doc_type > 0:
                db_execute(
                    "UPDATE journal SET doc_type = CAST(doc_type AS TEXT) WHERE doc_type IS NOT NULL AND typeof(doc_type) != 'text'"
                )
        except Exception:
            pass

    defaults = [
        {"code": "100", "description": "Πωλήσεις"},
        {"code": "200", "description": "Αγορές"},
        {"code": "300", "description": "Ταμείο"},
        {"code": "400", "description": "Τράπεζες"},
        {"code": "600", "description": "Γενικά Έξοδα"},
    ]
    for row in defaults:
        try:
            db_execute(
                "INSERT INTO gl_codes (code, description) VALUES (:code, :description)",
                row,
            )
        except Exception:
            # Ignore duplicates
            pass


def _journal_expected_columns() -> Dict[str, str]:
    if DB_DIALECT == "postgres":
        return {
            "doc_date": "DATE",
            "doc_no": "TEXT",
            "doc_type": "TEXT",
            "counterparty": "TEXT",
            "description": "TEXT",
            "gl_code": "TEXT",
            "amount_net": "DOUBLE PRECISION",
            "vat_amount": "DOUBLE PRECISION",
            "amount_gross": "DOUBLE PRECISION",
            "payment_method": "TEXT",
            "bank_account": "TEXT",
            "status": "TEXT",
        }
    return {
        "doc_date": "DATE",
        "doc_no": "TEXT",
        "doc_type": "TEXT",
        "counterparty": "TEXT",
        "description": "TEXT",
        "gl_code": "TEXT",
        "amount_net": "REAL",
        "vat_amount": "REAL",
        "amount_gross": "REAL",
        "payment_method": "TEXT",
        "bank_account": "TEXT",
        "status": "TEXT",
    }


def _get_journal_columns() -> Set[str]:
    try:
        if DB_DIALECT == "postgres":
            cols_df = pd.read_sql_query(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'journal'",
                ENGINE,
            )
            return set(cols_df["column_name"].tolist())
        cols_df = pd.read_sql_query("PRAGMA table_info(journal)", ENGINE)
        return set(cols_df["name"].tolist())
    except Exception:
        return set()


def _ensure_journal_schema() -> None:
    expected_cols = _journal_expected_columns()
    existing_cols = _get_journal_columns()
    missing_cols = [col for col in expected_cols if col not in existing_cols]
    if not missing_cols:
        return
    for col in missing_cols:
        col_type = expected_cols[col]
        if DB_DIALECT == "postgres":
            db_execute(f"ALTER TABLE journal ADD COLUMN IF NOT EXISTS {col} {col_type}")
        else:
            db_execute(f"ALTER TABLE journal ADD COLUMN {col} {col_type}")


def _counterparty_kind_for_doc_type(doc_type: str) -> str:
    dt = (doc_type or "").strip()
    if dt in {"Income", "Cash Deposit"}:
        return "customer"
    if dt in {"Expense", "Bill"}:
        return "supplier"
    return "other"


def _bank_kind_from_name(name: str) -> str:
    n = (name or "").strip().casefold()
    if not n:
        return "bank"
    if n.startswith("ταμείο") or "ταμείο" in n or n.startswith("cash") or "cash" in n:
        return "cash"
    if n.startswith("ταμειο") or "ταμειο" in n:
        return "cash"
    if n.startswith("ταμείο -") or n.startswith("ταμειο -"):
        return "cash"
    if n.startswith("τράπεζ") or n.startswith("τραπεζ"):
        return "bank"
    return "bank"


def upsert_counterparty(name: str, kind: str) -> None:
    nm = (name or "").strip()
    kd = (kind or "other").strip() or "other"
    if not nm:
        return
    if DB_DIALECT == "postgres":
        db_execute(
            "INSERT INTO counterparties (name, kind) VALUES (:name, :kind) ON CONFLICT (name) DO UPDATE SET kind = EXCLUDED.kind",
            {"name": nm, "kind": kd},
        )
    else:
        # SQLite supports ON CONFLICT with DO UPDATE
        db_execute(
            "INSERT INTO counterparties (name, kind) VALUES (:name, :kind) ON CONFLICT(name) DO UPDATE SET kind=excluded.kind",
            {"name": nm, "kind": kd},
        )


def upsert_bank_account(name: str, kind: str) -> None:
    nm = (name or "").strip()
    kd = (kind or "bank").strip() or "bank"
    if not nm:
        return
    if DB_DIALECT == "postgres":
        db_execute(
            "INSERT INTO bank_accounts (name, kind) VALUES (:name, :kind) ON CONFLICT (name) DO UPDATE SET kind = EXCLUDED.kind",
            {"name": nm, "kind": kd},
        )
    else:
        db_execute(
            "INSERT INTO bank_accounts (name, kind) VALUES (:name, :kind) ON CONFLICT(name) DO UPDATE SET kind=excluded.kind",
            {"name": nm, "kind": kd},
        )


def migrate_placeholders_to_lookups() -> None:
    """Migrate legacy Settings 'placeholder' rows from journal into lookup tables.

    Older versions stored Customers/Suppliers/Bank accounts by inserting 0-amount rows
    into `journal`. Those rows should not pollute the Archive.
    """
    try:
        df_cp = pd.read_sql_query(
            """
            SELECT DISTINCT counterparty AS name, doc_type
            FROM journal
            WHERE counterparty IS NOT NULL AND counterparty != ''
              AND description = '(αρχικοποίηση)'
              AND COALESCE(amount_net,0)=0 AND COALESCE(vat_amount,0)=0 AND COALESCE(amount_gross,0)=0
            """,
            ENGINE,
        )
        if not df_cp.empty:
            for r in df_cp.itertuples(index=False):
                upsert_counterparty(str(r.name), _counterparty_kind_for_doc_type(str(r.doc_type)))
            db_execute(
                """
                DELETE FROM journal
                WHERE description = '(αρχικοποίηση)'
                  AND COALESCE(amount_net,0)=0 AND COALESCE(vat_amount,0)=0 AND COALESCE(amount_gross,0)=0
                """
            )
    except Exception:
        pass

    try:
        df_ba = pd.read_sql_query(
            """
            SELECT DISTINCT bank_account AS name
            FROM journal
            WHERE bank_account IS NOT NULL AND bank_account != ''
              AND description = '(άνοιγμα λογαριασμού)'
              AND COALESCE(amount_net,0)=0 AND COALESCE(vat_amount,0)=0 AND COALESCE(amount_gross,0)=0
            """,
            ENGINE,
        )
        if not df_ba.empty:
            for r in df_ba.itertuples(index=False):
                nm = str(r.name)
                upsert_bank_account(nm, _bank_kind_from_name(nm))
            db_execute(
                """
                DELETE FROM journal
                WHERE description = '(άνοιγμα λογαριασμού)'
                  AND COALESCE(amount_net,0)=0 AND COALESCE(vat_amount,0)=0 AND COALESCE(amount_gross,0)=0
                """
            )
    except Exception:
        pass

try:
    if not st.session_state.get("db_initialized"):
        init_db()
        migrate_placeholders_to_lookups()
        st.session_state["db_initialized"] = True
except OperationalError:
    st.error("❌ Δεν μπορώ να συνδεθώ στη βάση Postgres (DATABASE_URL).")
    diag = _safe_db_diagnostics()
    st.write(diag)
    if _looks_like_placeholder(diag):
        st.warning(
            "Φαίνεται ότι έβαλες placeholder τιμές (π.χ. `host` / `DBNAME`) αντί για πραγματικό Supabase connection string."
        )
    st.info(
        "Για να το φτιάξεις: Supabase → Project Settings → Database → Connection string → επέλεξε 'Transaction pooler' και κάνε copy το URI. "
        "Μετά στο Streamlit Cloud: Manage app → Settings → Secrets βάλε `DATABASE_URL = \"...\"` και κάνε Reboot. "
        "Οδηγός: SUPABASE_SETUP.md"
    )
    st.stop()
except Exception as e:
    st.error("❌ Σφάλμα αρχικοποίησης βάσης.")
    st.write(_safe_db_diagnostics())
    st.write(f"Type: {type(e).__name__}")
    st.stop()

# --- 4. CALCULATOR LOGIC ---
if 'calc_net' not in st.session_state: st.session_state.calc_net = 0.0
if 'calc_vat_rate' not in st.session_state: st.session_state.calc_vat_rate = 24
if 'calc_vat_val' not in st.session_state: st.session_state.calc_vat_val = 0.0
if 'calc_gross' not in st.session_state: st.session_state.calc_gross = 0.0

def calculate_vat():
    """Υπολογίζει ΦΠΑ και σύνολο βάσει καθαρού ποσού και ποσοστού"""
    net = float(st.session_state.calc_net) if st.session_state.calc_net else 0.0
    rate = float(st.session_state.calc_vat_rate) if st.session_state.calc_vat_rate else 0.0
    vat = round(net * (rate / 100.0), 2)
    gross = round(net + vat, 2)
    st.session_state.calc_vat_val = vat
    st.session_state.calc_gross = gross

# --- 4.5 CACHED DATA LOADERS ---
@st.cache_data
def load_gl_codes():
    """Load GL codes with caching (rarely changes)"""
    gl_df = pd.read_sql_query("SELECT code, description FROM gl_codes ORDER BY code", ENGINE)
    return gl_df.apply(lambda x: f"{x['code']} - {x['description']}", axis=1).tolist()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_journal_data():
    """Load journal data with short-term caching"""
    return pd.read_sql_query("SELECT * FROM journal", ENGINE)


@st.cache_data(ttl=300)
def load_counterparties(doc_types: Optional[tuple[str, ...]] = None) -> list[str]:
    """Load distinct counterparties, optionally filtered by doc_type."""
    # From journal
    base = (
        "SELECT DISTINCT counterparty AS name "
        "FROM journal "
        "WHERE counterparty IS NOT NULL AND counterparty != ''"
    )
    if doc_types:
        types_sql = ", ".join([f"'{t}'" for t in doc_types])
        sql_j = f"{base} AND doc_type IN ({types_sql})"
    else:
        sql_j = base

    # From lookup table (filtered by inferred kind when doc_types provided)
    kind_filter_sql = ""
    params: Dict[str, Any] = {}
    if doc_types:
        kinds = {_counterparty_kind_for_doc_type(t) for t in doc_types}
        # Only narrow when the inferred kinds are meaningful
        if kinds <= {"customer"}:
            kind_filter_sql = "WHERE kind = :k"
            params["k"] = "customer"
        elif kinds <= {"supplier"}:
            kind_filter_sql = "WHERE kind = :k"
            params["k"] = "supplier"
        else:
            kind_filter_sql = ""

    sql = (
        f"SELECT name FROM ({sql_j} UNION SELECT name FROM counterparties {kind_filter_sql}) u "
        "ORDER BY name"
    )
    # Use SQLAlchemy `text()` so named parameters (e.g. :k) work on Postgres.
    df = pd.read_sql_query(text(sql), ENGINE, params=params)
    if df.empty:
        return []
    vals = [str(x).strip() for x in df["name"].tolist() if str(x).strip()]
    vals = sorted(set(vals), key=str.casefold)
    return vals


@st.cache_data(ttl=300)
def load_bank_accounts() -> list[str]:
    """Load distinct bank accounts for dropdowns."""
    df = pd.read_sql_query(
        """
        SELECT name FROM (
            SELECT DISTINCT bank_account AS name
            FROM journal
            WHERE bank_account IS NOT NULL AND bank_account != ''
            UNION
            SELECT name
            FROM bank_accounts
            WHERE name IS NOT NULL AND name != ''
        ) u
        ORDER BY name
        """,
        ENGINE,
    )
    if df.empty:
        return []
    vals = [str(x).strip() for x in df["name"].tolist() if str(x).strip()]
    vals = sorted(set(vals), key=str.casefold)
    return vals

# --- 4.6 INPUT VALIDATION ---
def validate_transaction_input(trans_data):
    """Validate transaction data before database insert."""
    errors = []
    
    # Check required fields
    if not trans_data.get('partner') or trans_data['partner'].strip() == '':
        errors.append("Παραλήπτης/Προμηθευτής είναι υποχρεωτικό")
    if not trans_data.get('description') or trans_data['description'].strip() == '':
        errors.append("Περιγραφή είναι υποχρεωτική")
    
    # Check numeric values are valid
    if trans_data.get('amount_net', 0) < 0:
        errors.append("Καθαρό ποσό δεν μπορεί να είναι αρνητικό")
    if trans_data.get('vat_amount', 0) < 0:
        errors.append("ΦΠΑ δεν μπορεί να είναι αρνητικό")
    if trans_data.get('amount_gross', 0) < 0:
        errors.append("Σύνολο δεν μπορεί να είναι αρνητικό")
    
    # Check that gross >= net
    if trans_data.get('amount_gross', 0) < trans_data.get('amount_net', 0):
        errors.append("Σύνολο δεν μπορεί να είναι μικρότερο από καθαρό")
    
    return errors

# --- 5. INITIAL DATA LOAD ---
count = db_scalar("SELECT count(*) FROM journal", default=0)


def _import_excel_to_db(excel_source) -> int:
    """Import an Excel file (path or file-like) into the journal table.

    Returns the total row count in `journal` after the import.
    """
    xl = pd.ExcelFile(excel_source, engine="openpyxl")
    sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
    df = pd.read_excel(excel_source, sheet_name=sheet)
    df.columns = df.columns.astype(str).str.strip()

    def _to_float(v) -> float:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0.0
        if isinstance(v, (int, float)):
            try:
                return float(v)
            except Exception:
                return 0.0
        s = str(v).strip()
        if not s or s.lower() in {"nan", "none", "<na>"}:
            return 0.0
        # Normalize common currency/thousand/decimal formats (€, spaces, 1.234,56, 1,234.56)
        s = s.replace("€", "").replace(" ", "")
        if "," in s and "." in s:
            # If last comma is after last dot => comma decimal
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")
        try:
            return float(s)
        except Exception:
            return 0.0

    rows = []

    # Format A: legacy/expected "Journal"-style sheet
    # (used by older versions or user-provided exports)
    rename_map = {
        "Date": "DocDate",
        "Net": "Amount (Net)",
        "Gross": "Amount (Gross)",
        "Type": "DocType",
        "Counterparty": "counterparty",
        "Bank Account": "bank_account",
    }
    df_journal = df.rename(columns=rename_map).copy()

    # Format B: bundled finance_data.xlsx (Greek cashflow sheet, e.g. "Ταμείο")
    is_cashflow = ("Ημερομηνία" in df.columns) and (
        ("Έσοδα (€)" in df.columns) or ("Έξοδα (€)" in df.columns) or ("Μερίσματα" in df.columns)
    )

    if is_cashflow:
        for _, r in df.iterrows():
            parsed_date = pd.to_datetime(r.get("Ημερομηνία"), errors="coerce")
            d_date = (
                parsed_date.strftime("%Y-%m-%d")
                if pd.notna(parsed_date)
                else date.today().strftime("%Y-%m-%d")
            )

            income = _to_float(r.get("Έσοδα (€)", 0))
            expense = _to_float(r.get("Έξοδα (€)", 0))
            dividends = _to_float(r.get("Μερίσματα", 0))

            amount_net = income if income else (expense if expense else dividends)
            doc_type = "Income" if income else ("Expense" if (expense or dividends) else "")

            category = str(r.get("Κατηγορία", "")).strip()
            desc = str(r.get("Περιγραφή", "")).strip()
            if category and desc:
                desc = f"[{category}] {desc}"
            elif category:
                desc = category

            rows.append(
                {
                    "doc_date": d_date,
                    "doc_no": "",
                    "doc_type": doc_type,
                    "counterparty": str(r.get("Στέλεχος", "")).strip(),
                    "description": desc,
                    "gl_code": "999",
                    "amount_net": amount_net,
                    "vat_amount": 0.0,
                    "amount_gross": amount_net,
                    "payment_method": str(r.get("Τρόπος Πληρωμής", "")).strip(),
                    "bank_account": "",
                    "status": str(r.get("Έγκριση", "")).strip(),
                }
            )
    else:
        for _, r in df_journal.iterrows():
            parsed_date = pd.to_datetime(r.get("DocDate"), errors="coerce")
            d_date = (
                parsed_date.strftime("%Y-%m-%d")
                if pd.notna(parsed_date)
                else date.today().strftime("%Y-%m-%d")
            )
            amount_net = _to_float(r.get("Amount (Net)", 0))
            vat_amount = _to_float(r.get("VAT Amount", 0))
            amount_gross = _to_float(r.get("Amount (Gross)", 0))
            if amount_gross == 0.0:
                amount_gross = amount_net + vat_amount

            rows.append(
                {
                    "doc_date": d_date,
                    "doc_no": str(r.get("DocNo", "")),
                    "doc_type": str(r.get("DocType", "")),
                    "counterparty": str(r.get("counterparty", "")),
                    "description": str(r.get("Description", "")),
                    "gl_code": "999",
                    "amount_net": amount_net,
                    "vat_amount": vat_amount,
                    "amount_gross": amount_gross,
                    "payment_method": str(r.get("Payment Method", "")),
                    "bank_account": str(r.get("bank_account", "")),
                    "status": str(r.get("Status", "")),
                }
            )

    db_executemany(
        """INSERT INTO journal (
                doc_date, doc_no, doc_type, counterparty, description, gl_code,
                amount_net, vat_amount, amount_gross, payment_method, bank_account, status
            ) VALUES (
                :doc_date, :doc_no, :doc_type, :counterparty, :description, :gl_code,
                :amount_net, :vat_amount, :amount_gross, :payment_method, :bank_account, :status
            )""",
        rows,
    )
    return int(db_scalar("SELECT count(*) FROM journal", default=0) or 0)

if count == 0:
    st.title("⚠️ Εγκατάσταση")
    st.info("Η βάση είναι κενή.")
    if DB_DIALECT == "postgres":
        st.caption("DB: Postgres (DATABASE_URL)")
    else:
        st.caption(f"DB file: {DB_FILE}")
        if os.path.abspath(__file__).startswith("/mount/src/"):
            st.warning(
                "Streamlit Cloud: τοπική SQLite μπορεί να χαθεί σε reboot/redeploy. "
                "Για 100% μόνιμη αποθήκευση βάλε Postgres/Supabase (DATABASE_URL)."
            )
    c1, c2 = st.columns(2)

    repo_excel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance_data.xlsx")
    if os.path.exists(repo_excel):
        c2.caption("📦 Βρέθηκε τοπικό αρχείο: finance_data.xlsx")
        if c2.button("Import bundled finance_data.xlsx", width='stretch'):
            try:
                inserted = _import_excel_to_db(repo_excel)
                st.success(f"✅ Import ολοκληρώθηκε. Εγγραφές στη βάση: {inserted}")
                st.stop()
            except Exception as e:
                st.error("❌ Error loading bundled Excel")
                st.exception(e)

    up = c1.file_uploader(
        "Upload Excel (finance_data.xlsx)",
        type=["xlsx"],
        help="Προτεινόμενο όνομα: finance_data.xlsx (οποιοδήποτε .xlsx γίνεται δεκτό).",
    )
    if up:
        try:
            c1.caption(f"📄 Uploaded: {getattr(up, 'name', 'unknown')}")
            inserted = _import_excel_to_db(up)
            st.success(f"✅ Import ολοκληρώθηκε. Εγγραφές στη βάση: {inserted}")
            st.info("Κάνε refresh ή πάτα Start Fresh αν θέλεις κενή βάση.")
            st.stop()
        except Exception as e:
            st.error("❌ Error loading Excel")
            st.exception(e)
    
    if c2.button("🚀 Start Fresh (Blank DB)"):
        db_execute("DELETE FROM journal")
        st.rerun()
    st.stop()

# --- 6. AUTH ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("🔐 Login")
    u = st.text_input("User"); p = st.text_input("Pass", type="password")
    if st.button("Enter"):
        if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"): st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
    st.stop()

# --- 7. MAIN APP ---
st.sidebar.markdown(
        """
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">
            <div style="width:10px; height:28px; background:#00d084; border-radius:6px;"></div>
            <div style="font-size:1.25rem; font-weight:800; color:#0b2b4c; line-height:1;">SalesTree ERP</div>
        </div>
        """,
        unsafe_allow_html=True,
)
st.sidebar.divider()

st.sidebar.markdown("<div style='font-weight:700; color:#0b2b4c; margin:0.25rem 0 0.5rem 0;'>Μενού</div>", unsafe_allow_html=True)

menu = st.sidebar.radio("ΜΕΝΟΥ", [
    "Dashboard",
    "Νέα Εγγραφή",
    "ΦΠΑ & Φόροι (Report)",
    "Καρτέλες (Ledgers)",
    "Αρχείο & Διορθώσεις",
    "Ταμείο & Τράπεζες",
    "Ρυθμίσεις GL"
], label_visibility="collapsed")

# Theme toggle
st.sidebar.divider()
theme_option = st.sidebar.selectbox("Θέμα", ["Φωτεινό", "Σκοτεινό"], index=0 if st.session_state.theme == 'light' else 1)
if theme_option == "Σκοτεινό" and st.session_state.theme == 'light':
    st.session_state.theme = 'dark'
    st.rerun()
elif theme_option == "Φωτεινό" and st.session_state.theme == 'dark':
    st.session_state.theme = 'light'
    st.rerun()

 

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Γενική Εικόνα")
    
    with st.spinner("Φόρτωση δεδομένων..."):
        df = load_journal_data()
    
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    cy = datetime.now().year
    df_y = df[df['doc_date'].dt.year == cy]
    
    inc = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
    exp = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Πωλήσεις (YTD)", f"€{inc:,.0f}")
    c2.metric("Έξοδα (YTD)", f"€{exp:,.0f}")
    c3.metric("Κέρδος", f"€{inc-exp:,.0f}")
    
    st.divider()
    st.subheader("📈 Μηνιαία Ανάλυση")
    monthly = df_y.copy()
    monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
    grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
    
    # Create professional chart
    fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group',
                 title="Μηνιαία Κίνηση Εσόδων/Εξόδων",
                 labels={'mo': 'Μήνας', 'amount_net': 'Ποσό (€)', 'doc_type': 'Τύπος'})
    
    # Color mapping for professional palette
    color_map = {
        'Income': '#10b981',      # Green
        'Expense': '#ef4444',     # Red
        'Bill': '#f59e0b'         # Amber
    }
    
    fig.for_each_trace(lambda t: t.update(
        marker=dict(
            color=color_map.get(t.name, '#2d5a8c'),
            line=dict(color='rgba(255,255,255,0.2)', width=1)
        ),
        hovertemplate='<b>%{fullData.name}</b><br>Περίοδος: %{x}<br>Ποσό: €%{y:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        plot_bgcolor='#f8f9fa',
        paper_bgcolor='#ffffff',
        hovermode='x unified',
        font=dict(family='Inter, sans-serif', color='#0f172a', size=12),
        xaxis_title="Περίοδος",
        yaxis_title="Ποσό (€)",
        title=None,
        showlegend=True,
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor='#cbd5e0',
            borderwidth=1,
            font=dict(size=11, color='#0f172a')
        ),
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(203, 213, 224, 0.4)',
            zeroline=False,
            color='#34568b',
            tickfont=dict(size=11, color='#0f172a')
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(203, 213, 224, 0.4)',
            zeroline=False,
            color='#34568b',
            tickfont=dict(size=11, color='#0f172a')
        ),
        margin=dict(l=60, r=20, t=20, b=60),
        height=400
    )
    
    st.plotly_chart(fig, width='stretch')
    
    st.divider()
    st.subheader("📋 Τελευταίες Εγγραφές")
    
    df_display = df.copy()
    df_display['doc_date'] = df_display['doc_date'].dt.strftime('%d/%m/%Y')
    
    # Ensure amounts are clean
    for col in ['amount_net', 'vat_amount', 'amount_gross']:
        df_display[col] = pd.to_numeric(df_display[col], errors='coerce').fillna(0.0)
    
    # Sort by date descending and show last 20
    df_display = df_display.sort_values('doc_date', ascending=False).head(20)
    
    # Select columns to display
    display_cols = ['doc_date', 'doc_no', 'doc_type', 'counterparty', 'description', 'amount_net', 'vat_amount', 'amount_gross', 'payment_method', 'status']
    df_display = df_display[display_cols].copy()
    
    # Rename columns for display
    df_display.columns = ['Ημερ/νία', 'Αρ. Παρ/κου', 'Τύπος', 'Συναλλασσόμενος', 'Περιγραφή', 'Καθαρό', 'ΦΠΑ', 'Σύνολο', 'Πληρωμή', 'Κατάσταση']
    
    # Format currency columns
    for col in ['Καθαρό', 'ΦΠΑ', 'Σύνολο']:
        df_display[col] = df_display[col].apply(lambda x: f"€{x:,.2f}")
    
    st.dataframe(df_display, width='stretch', hide_index=True)

# --- NEW ENTRY ---
elif menu == "Νέα Εγγραφή":
    st.title("📝 Νέα Εγγραφή - Συναλλαγές Λογιστηρίου")

    gl_list = load_gl_codes()
    
    # Initialize VAT calculator state for this section
    if 'vat_calc_active' not in st.session_state:
        st.session_state.vat_calc_active = True
        if st.session_state.calc_net == 0.0:  # Only initialize if empty
            st.session_state.calc_net = 0.0
            st.session_state.calc_vat_rate = 24
    
    # Transaction type selection
    st.subheader("📌 Επιλέξτε τύπο συναλλαγής")
    
    trans_type = st.radio("Κατηγορία Συναλλαγής", [
        "💰 Εισπράξεις (Πωλήσεις)",
        "💸 Πληρωμές (Έξοδα)",
        "📄 Τιμολόγια Αγορών",
        "🔄 Μεταφορές Λογαριασμών",
        "💵 Αναλήψεις Ταμείου",
        "💳 Καταθέσεις Ταμείου",
        "🏦 Τραπεζικές Λειτουργίες",
        "📊 Άλλη Συναλλαγή"
    ], horizontal=False)
    
    st.divider()
    
    with st.container():
        # Common fields
        c1, c2, c3 = st.columns(3)
        d_date = c1.date_input("Ημερομηνία", date.today())
        d_no = c2.text_input("Αρ. Παρ/κου / Αναφορά")
        gl_choice = c3.selectbox("Λογαριασμός (GL)", gl_list if gl_list else ["999"])

        # Default status (can be overridden per transaction)
        status = "Paid"
        
        # Transaction-specific fields
        if trans_type == "💰 Εισπράξεις (Πωλήσεις)":
            st.subheader("📊 Στοιχεία Εισπράξης")
            customers = load_counterparties(("Income", "Cash Deposit"))
            if customers:
                sel_customer = st.selectbox(
                    "Πελάτης (επιλογή)",
                    ["(Νέος Πελάτης)"] + customers,
                    key="partner_income_select",
                )
                if sel_customer == "(Νέος Πελάτης)":
                    partner = st.text_input("Πελάτης", "", key="partner_income_text")
                else:
                    partner = sel_customer
            else:
                partner = st.text_input("Πελάτης", "", key="partner_income_text_only")
            descr = st.text_input("Περιγραφή", "Εισπράξη πωλήσεων")
            
            st.divider()
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.session_state.calc_net = st.number_input("Καθαρό (€)", step=10.0, value=st.session_state.calc_net, min_value=0.0)
            with col2:
                vat_opts = [24, 13, 6, 0]
                vat_idx = vat_opts.index(st.session_state.calc_vat_rate) if st.session_state.calc_vat_rate in vat_opts else 0
                st.session_state.calc_vat_rate = st.selectbox("ΦΠΑ %", vat_opts, index=vat_idx)
            
            calculate_vat()
            
            with col3:
                st.number_input("ΦΠΑ (€)", value=st.session_state.calc_vat_val, disabled=True, key="display_vat_1")
            with col4:
                st.number_input("Σύνολο (€)", value=st.session_state.calc_gross, disabled=True, key="display_gross_1")
            
            vat = st.session_state.calc_vat_val
            gross = st.session_state.calc_gross
            
            p1, p2 = st.columns(2)
            pay = p1.selectbox("Τρόπος Εισπράξης", ["Τράπεζα", "Μετρητά", "Επί Πιστώσει"])
            status_label = p1.selectbox(
                "Κατάσταση",
                ["✅ Πληρωμένη", "⏳ Εκκρεμής"],
                index=1 if pay == "Επί Πιστώσει" else 0,
                key="status_income",
            )
            status = "Unpaid" if "Εκκρεμής" in status_label else "Paid"
            if pay == "Τράπεζα":
                bank_accounts = load_bank_accounts()
                if bank_accounts:
                    sel_bank = p2.selectbox(
                        "Λογαριασμός (επιλογή)",
                        ["(Νέος Λογαριασμός)"] + bank_accounts,
                        key="bank_income_select",
                    )
                    if sel_bank == "(Νέος Λογαριασμός)":
                        bank = p2.text_input("Λογαριασμός", "", key="bank_income_text")
                    else:
                        bank = sel_bank
                else:
                    bank = p2.text_input("Λογαριασμός", "", key="bank_income_text_only")
            elif pay == "Μετρητά":
                bank = "Ταμείο"
                p2.text_input("Λογαριασμός", bank, disabled=True, key="bank_income_cash")
            else:
                bank = ""
                p2.text_input("Λογαριασμός", bank, disabled=True, key="bank_income_credit")
            d_type = "Income"
        
        elif trans_type == "💸 Πληρωμές (Έξοδα)":
            st.subheader("📊 Στοιχεία Πληρωμής")
            suppliers = load_counterparties(("Expense", "Bill"))
            if suppliers:
                sel_supplier = st.selectbox(
                    "Προμηθευτής (επιλογή)",
                    ["(Νέος Προμηθευτής/Δαπάνη)"] + suppliers,
                    key="partner_expense_select",
                )
                if sel_supplier == "(Νέος Προμηθευτής/Δαπάνη)":
                    partner = st.text_input("Προμηθευτής / Δαπάνη", "", key="partner_expense_text")
                else:
                    partner = sel_supplier
            else:
                partner = st.text_input("Προμηθευτής / Δαπάνη", "", key="partner_expense_text_only")
            descr = st.text_input("Περιγραφή", "Έξοδο λειτουργίας")
            
            st.divider()
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.session_state.calc_net = st.number_input("Καθαρό (€)", step=10.0, value=st.session_state.calc_net, min_value=0.0)
            with col2:
                vat_opts = [24, 13, 6, 0]
                vat_idx = vat_opts.index(st.session_state.calc_vat_rate) if st.session_state.calc_vat_rate in vat_opts else 0
                st.session_state.calc_vat_rate = st.selectbox("ΦΠΑ %", vat_opts, index=vat_idx)
            
            calculate_vat()
            
            with col3:
                st.number_input("ΦΠΑ (€)", value=st.session_state.calc_vat_val, disabled=True, key="display_vat_2")
            with col4:
                st.number_input("Σύνολο (€)", value=st.session_state.calc_gross, disabled=True, key="display_gross_2")
            
            vat = st.session_state.calc_vat_val
            gross = st.session_state.calc_gross
            
            p1, p2 = st.columns(2)
            pay = p1.selectbox("Τρόπος Πληρωμής", ["Τράπεζα", "Μετρητά", "Επί Πιστώσει"])
            status_label = p1.selectbox(
                "Κατάσταση",
                ["✅ Πληρωμένη", "⏳ Εκκρεμής"],
                index=1 if pay == "Επί Πιστώσει" else 0,
                key="status_expense",
            )
            status = "Unpaid" if "Εκκρεμής" in status_label else "Paid"
            if pay == "Τράπεζα":
                bank_accounts = load_bank_accounts()
                if bank_accounts:
                    sel_bank = p2.selectbox(
                        "Λογαριασμός (επιλογή)",
                        ["(Νέος Λογαριασμός)"] + bank_accounts,
                        key="bank_expense_select",
                    )
                    if sel_bank == "(Νέος Λογαριασμός)":
                        bank = p2.text_input("Λογαριασμός", "", key="bank_expense_text")
                    else:
                        bank = sel_bank
                else:
                    bank = p2.text_input("Λογαριασμός", "", key="bank_expense_text_only")
            elif pay == "Μετρητά":
                bank = "Ταμείο"
                p2.text_input("Λογαριασμός", bank, disabled=True, key="bank_expense_cash")
            else:
                bank = ""
                p2.text_input("Λογαριασμός", bank, disabled=True, key="bank_expense_credit")
            d_type = "Expense"
        
        elif trans_type == "📄 Τιμολόγια Αγορών":
            st.subheader("📊 Στοιχεία Τιμολογίου Αγοράς")
            suppliers = load_counterparties(("Expense", "Bill"))
            if suppliers:
                sel_supplier = st.selectbox(
                    "Προμηθευτής (επιλογή)",
                    ["(Νέος Προμηθευτής)"] + suppliers,
                    key="partner_bill_select",
                )
                if sel_supplier == "(Νέος Προμηθευτής)":
                    partner = st.text_input("Προμηθευτής", "", key="partner_bill_text")
                else:
                    partner = sel_supplier
            else:
                partner = st.text_input("Προμηθευτής", "", key="partner_bill_text_only")
            descr = st.text_input("Περιγραφή Αγοράς", "Αγορά αγαθών/υπηρεσιών")
            
            st.divider()
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.session_state.calc_net = st.number_input("Καθαρό (€)", step=10.0, value=st.session_state.calc_net, min_value=0.0)
            with col2:
                vat_opts = [24, 13, 6, 0]
                vat_idx = vat_opts.index(st.session_state.calc_vat_rate) if st.session_state.calc_vat_rate in vat_opts else 0
                st.session_state.calc_vat_rate = st.selectbox("ΦΠΑ %", vat_opts, index=vat_idx)
            
            calculate_vat()
            
            with col3:
                st.number_input("ΦΠΑ (€)", value=st.session_state.calc_vat_val, disabled=True, key="display_vat_3")
            with col4:
                st.number_input("Σύνολο (€)", value=st.session_state.calc_gross, disabled=True, key="display_gross_3")
            
            vat = st.session_state.calc_vat_val
            gross = st.session_state.calc_gross
            
            p1, p2 = st.columns(2)
            pay = p1.selectbox("Κατάσταση", ["Επί Πιστώσει", "Πληρωμένο"])
            status_label = p1.selectbox(
                "Κατάσταση Πληρωμής",
                ["✅ Πληρωμένη", "⏳ Εκκρεμής"],
                index=1 if pay == "Επί Πιστώσει" else 0,
                key="status_bill",
            )
            status = "Unpaid" if "Εκκρεμής" in status_label else "Paid"
            bank_accounts = load_bank_accounts()
            if bank_accounts:
                sel_bank = p2.selectbox(
                    "Λογαριασμός (επιλογή)",
                    ["(Κενό)", "(Νέος Λογαριασμός)"] + bank_accounts,
                    key="bank_bill_select",
                )
                if sel_bank == "(Κενό)":
                    bank = ""
                elif sel_bank == "(Νέος Λογαριασμός)":
                    bank = p2.text_input("Λογαριασμός", "", key="bank_bill_text")
                else:
                    bank = sel_bank
            else:
                bank = p2.text_input("Λογαριασμός", "", key="bank_bill_text_only")
            d_type = "Bill"
        
        elif trans_type == "🔄 Μεταφορές Λογαριασμών":
            st.subheader("💳 Μεταφορά Ποσού μεταξύ Λογαριασμών")
            partner = st.text_input("Περιγραφή", "Μεταφορά χρημάτων")
            
            from_acc = st.selectbox("Από Λογαριασμό", ["Ταμείο", "Alpha Bank", "Piraeus Bank", "Gamma Bank"])
            to_acc = st.selectbox("Προς Λογαριασμό", ["Ταμείο", "Alpha Bank", "Piraeus Bank", "Gamma Bank"])
            
            descr = f"Μεταφορά από {from_acc} σε {to_acc}"
            
            st.divider()
            st.session_state.calc_net = st.number_input("Ποσό (€)", step=10.0, value=st.session_state.calc_net, min_value=0.0)
            
            k1, k2 = st.columns(2)
            k1.write(f"**Από:** {from_acc}")
            k2.write(f"**Προς:** {to_acc}")
            
            bank = f"{from_acc} → {to_acc}"
            pay = "Μεταφορά"
            vat = 0.0
            gross = st.session_state.calc_net
            d_type = "Transfer"
            status = "Paid"
        
        elif trans_type == "💵 Αναλήψεις Ταμείου":
            st.subheader("💳 Ανάληψη Χρημάτων από Τράπεζα")
            partner = st.text_input("Τράπεζα", "Alpha Bank")
            descr = st.text_input("Περιγραφή", "Ανάληψη μετρητών")
            
            st.divider()
            st.session_state.calc_net = st.number_input("Ποσό (€)", step=10.0, value=st.session_state.calc_net, min_value=0.0)
            bank = st.text_input("Λογαριασμός Τράπεζας", "Alpha Bank")
            
            vat = 0.0
            gross = st.session_state.calc_net
            pay = "Ανάληψη"
            d_type = "Cash Withdrawal"
            status = "Paid"
        
        elif trans_type == "💳 Καταθέσεις Ταμείου":
            st.subheader("💳 Κατάθεση Χρημάτων στην Τράπεζα")
            partner = st.text_input("Τράπεζα", "Alpha Bank")
            descr = st.text_input("Περιγραφή", "Κατάθεση μετρητών")
            
            st.divider()
            st.session_state.calc_net = st.number_input("Ποσό (€)", step=10.0, value=st.session_state.calc_net, min_value=0.0)
            bank = st.text_input("Λογαριασμός Τράπεζας", "Alpha Bank")
            
            vat = 0.0
            gross = st.session_state.calc_net
            pay = "Κατάθεση"
            d_type = "Cash Deposit"
            status = "Paid"
        
        elif trans_type == "🏦 Τραπεζικές Λειτουργίες":
            st.subheader("🏦 Τραπεζική Συναλλαγή")
            descr = st.selectbox("Τύπος", ["Τόκοι", "Προμήθεια", "Επιστροφή Επιταγής", "Άλλο"])
            partner = st.text_input("Τράπεζα", "Alpha Bank")
            
            st.divider()
            st.session_state.calc_net = st.number_input("Ποσό (€)", step=1.0, value=st.session_state.calc_net, min_value=0.0)
            bank = st.text_input("Λογαριασμός", "Alpha Bank")
            
            vat = 0.0
            gross = st.session_state.calc_net
            pay = "Τράπεζα"
            d_type = "Bank Operation"
            status = "Paid"
        
        else:  # Άλλη Συναλλαγή
            st.subheader("📊 Στοιχεία Συναλλαγής")
            partners = load_counterparties(None)
            if partners:
                sel_partner = st.selectbox(
                    "Συναλλασσόμενος (επιλογή)",
                    ["(Νέος Συναλλασσόμενος)"] + partners,
                    key="partner_other_select",
                )
                if sel_partner == "(Νέος Συναλλασσόμενος)":
                    partner = st.text_input("Συναλλασσόμενος", "", key="partner_other_text")
                else:
                    partner = sel_partner
            else:
                partner = st.text_input("Συναλλασσόμενος", "", key="partner_other_text_only")
            descr = st.text_input("Περιγραφή", "")
            
            st.divider()
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.session_state.calc_net = st.number_input("Καθαρό (€)", step=10.0, value=st.session_state.calc_net, min_value=0.0)
            with col2:
                vat_opts = [24, 13, 6, 0]
                vat_idx = vat_opts.index(st.session_state.calc_vat_rate) if st.session_state.calc_vat_rate in vat_opts else 0
                st.session_state.calc_vat_rate = st.selectbox("ΦΠΑ %", vat_opts, index=vat_idx)
            
            calculate_vat()
            
            with col3:
                st.number_input("ΦΠΑ (€)", value=st.session_state.calc_vat_val, disabled=True, key="display_vat_other")
            with col4:
                st.number_input("Σύνολο (€)", value=st.session_state.calc_gross, disabled=True, key="display_gross_other")
            
            pay = st.selectbox("Κατηγορία", ["Income", "Expense", "Bill", "Other"])
            status_label = st.selectbox(
                "Κατάσταση",
                ["✅ Πληρωμένη", "⏳ Εκκρεμής"],
                index=0,
                key="status_other",
            )
            status = "Unpaid" if "Εκκρεμής" in status_label else "Paid"
            bank_accounts = load_bank_accounts()
            if bank_accounts:
                sel_bank = st.selectbox(
                    "Λογαριασμός (επιλογή)",
                    ["(Κενό)", "(Νέος Λογαριασμός)"] + bank_accounts,
                    key="bank_other_select",
                )
                if sel_bank == "(Κενό)":
                    bank = ""
                elif sel_bank == "(Νέος Λογαριασμός)":
                    bank = st.text_input("Λογαριασμός", "", key="bank_other_text")
                else:
                    bank = sel_bank
            else:
                bank = st.text_input("Λογαριασμός", "", key="bank_other_text_only")
            vat = st.session_state.calc_vat_val
            gross = st.session_state.calc_gross
            d_type = pay
        
        st.divider()

        # Clear, consistent summary before saving
        try:
            summary_partner = (partner or "").strip() if isinstance(partner, str) else str(partner)
        except Exception:
            summary_partner = ""
        summary_partner = summary_partner or "—"
        try:
            summary_bank = (bank or "").strip() if isinstance(bank, str) else str(bank)
        except Exception:
            summary_bank = ""
        summary_bank = summary_bank or "—"
        summary_gl = (gl_choice or "999")
        summary_status_gr = "✅ Πληρωμένη" if (status == "Paid") else "⏳ Εκκρεμής"
        try:
            summary_total = float(gross)
        except Exception:
            summary_total = 0.0
        st.info(
            f"**Σύνοψη Καταχώρησης**\n\n"
            f"- Τύπος: **{d_type}**\n"
            f"- Συναλλασσόμενος: **{summary_partner}**\n"
            f"- Λογαριασμός: **{summary_bank}**\n"
            f"- GL: **{summary_gl}**\n"
            f"- Κατάσταση: **{summary_status_gr}**\n"
            f"- Σύνολο: **€{summary_total:,.2f}**"
        )
        if st.button("ΑΠΟΘΗΚΕΥΣΗ", type="primary", width='stretch'):
            # Validate input
            trans_data = {
                'partner': partner,
                'description': descr,
                'amount_net': float(st.session_state.calc_net),
                'vat_amount': float(st.session_state.calc_vat_val),
                'amount_gross': float(st.session_state.calc_gross)
            }
            
            validation_errors = validate_transaction_input(trans_data)
            if validation_errors:
                for error in validation_errors:
                    st.error(f"❌ {error}")
            else:
                try:
                    # Get the correct values based on transaction type
                    if trans_type in ["💰 Εισπράξεις (Πωλήσεις)", "💸 Πληρωμές (Έξοδα)", "📄 Τιμολόγια Αγορών"]:
                        net_amount = float(st.session_state.calc_net)
                        vat_amount = float(st.session_state.calc_vat_val)
                        gross_amount = float(st.session_state.calc_gross)
                    else:
                        net_amount = 0.0
                        vat_amount = 0.0
                        gross_amount = float(st.session_state.calc_net) if st.session_state.calc_net else 0.0
                    
                    gl_val = gl_choice.split(" - ")[0] if gl_choice else "999"
                    doc_date_iso = d_date.strftime('%Y-%m-%d') if hasattr(d_date, 'strftime') else str(d_date)

                    db_execute(
                        """INSERT INTO journal (
                                doc_date, doc_no, doc_type, counterparty, description, gl_code,
                                amount_net, vat_amount, amount_gross, payment_method, bank_account, status
                            ) VALUES (
                                :doc_date, :doc_no, :doc_type, :counterparty, :description, :gl_code,
                                :amount_net, :vat_amount, :amount_gross, :payment_method, :bank_account, :status
                            )""",
                        {
                            "doc_date": doc_date_iso,
                            "doc_no": d_no,
                            "doc_type": d_type,
                            "counterparty": partner,
                            "description": descr,
                            "gl_code": gl_val,
                            "amount_net": net_amount,
                            "vat_amount": vat_amount,
                            "amount_gross": gross_amount,
                            "payment_method": pay,
                            "bank_account": bank,
                            "status": status,
                        },
                    )
                    # Keep Settings lookup lists in sync (so you can edit/delete there)
                    try:
                        upsert_counterparty(partner, _counterparty_kind_for_doc_type(d_type))
                    except Exception:
                        pass
                    try:
                        if bank and str(bank).strip():
                            upsert_bank_account(bank, _bank_kind_from_name(bank))
                    except Exception:
                        pass
                    st.cache_data.clear()  # Clear cache after new transaction
                    st.success("✅ Καταχωρήθηκε με επιτυχία!")
                    # Reset values
                    st.session_state.calc_net = 0.0
                    st.session_state.calc_vat_val = 0.0
                    st.session_state.calc_gross = 0.0
                    st.session_state.calc_vat_rate = 24
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Σφάλμα κατά την αποθήκευση: {str(e)}")

            # Do not force rerun on validation/errors; otherwise messages flash and disappear.

# --- VAT & TAX REPORT (FIXED LOGIC) ---
elif menu == "ΦΠΑ & Φόροι (Report)":
    st.title("📊 Αναλυτική Έκθεση ΦΠΑ & Φόρων")

    df = load_journal_data()
    
    # Convert date to datetime and clean data
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    df = clean_dataframe(df)
    
    # 1. ΠΕΡΙΟΔΟΣ ΕΠΙΛΟΓΗΣ
    st.subheader("📅 Επιλογή Περιόδου")
    col_type, col_yr, col_mo = st.columns(3)
    
    period_type = col_type.selectbox("Τύπος Περιόδου", ["Μηνιαία", "Τριμηνιαία", "Ετήσια"])
    sel_year = col_yr.number_input("Έτος", min_value=2000, max_value=2100, value=datetime.now().year)
    
    if period_type == "Μηνιαία":
        sel_month = col_mo.selectbox("Μήνας", range(1, 13), index=datetime.now().month - 1)
        mask = (df['doc_date'].dt.year == sel_year) & (df['doc_date'].dt.month == sel_month)
        period_label = f"{sel_month:02d}/{sel_year}"
    elif period_type == "Τριμηνιαία":
        sel_quarter = col_mo.selectbox("Τρίμηνο", [1, 2, 3, 4])
        start_month = (sel_quarter - 1) * 3 + 1
        end_month = sel_quarter * 3
        mask = (df['doc_date'].dt.year == sel_year) & (df['doc_date'].dt.month.isin(range(start_month, end_month + 1)))
        period_label = f"Τ{sel_quarter}/{sel_year}"
    else:
        mask = (df['doc_date'].dt.year == sel_year)
        period_label = str(sel_year)
    
    df_period = df[mask].copy()
    
    # Ensure all numeric columns are properly formatted
    for col in ['amount_net', 'vat_amount', 'amount_gross']:
        df_period[col] = pd.to_numeric(df_period[col], errors='coerce').fillna(0.0)
    
    # Ensure amount_gross = amount_net + vat_amount if missing
    df_period.loc[df_period['amount_gross'] == 0, 'amount_gross'] = df_period['amount_net'] + df_period['vat_amount']
    
    if df_period.empty:
        st.warning(f"⚠️ Δεν βρέθηκαν δεδομένα για την περίοδο {period_label}")
        st.stop()
    
    # 2. ΚΎΡΙΑ ΣΤΟΙΧΕΊΑ ΠΕΡΙΌΔΟΥ
    st.divider()
    st.subheader(f"📈 Σύνοψη Περιόδου {period_label}")
    
    # Calculations
    income_net = df_period[df_period['doc_type'] == 'Income']['amount_net'].sum()
    income_vat = df_period[df_period['doc_type'] == 'Income']['vat_amount'].sum()
    income_gross = df_period[df_period['doc_type'] == 'Income']['amount_gross'].sum()
    
    expense_net = df_period[df_period['doc_type'].isin(['Expense', 'Bill'])]['amount_net'].sum()
    expense_vat = df_period[df_period['doc_type'].isin(['Expense', 'Bill'])]['vat_amount'].sum()
    expense_gross = df_period[df_period['doc_type'].isin(['Expense', 'Bill'])]['amount_gross'].sum()
    
    net_profit = income_net - expense_net
    
    # Display KPIs
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Πωλήσεις (Καθαρό)", f"€{income_net:,.2f}", help="Σύνολο καθαρών εσόδων")
    m2.metric("Αγορές (Καθαρό)", f"€{expense_net:,.2f}", help="Σύνολο καθαρών εξόδων")
    m3.metric("Κέρδος Χρήσης", f"€{net_profit:,.2f}", help="Πωλήσεις - Αγορές")
    m4.metric("Συναλλαγές", f"{len(df_period)}", help="Σύνολο καταχωρήσεων")
    
    # 3. ΑΝΑΛΥΣΗ ΦΠΑ
    st.divider()
    st.subheader("📋 Αναλυτικά Στοιχεία ΦΠΑ")
    
    tab_vat, tab_tax, tab_data = st.tabs(["ΦΠΑ", "Φόρος Εισοδήματος", "Λεπτομέρειες"])
    
    with tab_vat:
        vat_collected = income_vat
        vat_deductible = expense_vat
        vat_payable = vat_collected - vat_deductible
        
        v1, v2, v3 = st.columns(3)
        v1.metric("ΦΠΑ Πωλήσεων (Εκροές)", f"€{vat_collected:,.2f}", 
                  help="ΦΠΑ που εισπράχθηκε από πελάτες")
        v2.metric("ΦΠΑ Αγορών (Εισροές)", f"€{vat_deductible:,.2f}", 
                  help="ΦΠΑ που πληρώθηκε σε προμηθευτές")
        v3.metric("ΦΠΑ Προς Πληρωμή", f"€{vat_payable:,.2f}", 
                  delta="Πληρώνεται" if vat_payable > 0 else "Επιστροφή", 
                  delta_color="off")
        
        st.divider()
        
        # VAT Table by type
        st.write("**Ανάλυση κατά τύπο συναλλαγής:**")
        vat_summary = df_period.groupby('doc_type').agg({
            'amount_net': 'sum',
            'vat_amount': 'sum',
            'amount_gross': 'sum'
        }).round(2)
        vat_summary.columns = ['Καθαρό', 'ΦΠΑ', 'Σύνολο']
        vat_summary['ΦΠΑ %'] = (vat_summary['ΦΠΑ'] / vat_summary['Καθαρό'] * 100).round(1)
        # Replace .applymap with lambda
        vat_summary = vat_summary.map(lambda x: f"€{x:,.2f}" if isinstance(x, (int, float)) else x)
        st.dataframe(vat_summary, width='stretch')
    
    with tab_tax:
        st.write("**Υπολογισμός Φόρου Εισοδήματος**")
        
        tax_col1, tax_col2 = st.columns([3, 1])
        with tax_col1:
            tax_rate = st.slider("Συντελεστής Φόρου (%)", min_value=0.0, max_value=50.0, value=24.0, step=0.1)
        
        st.divider()
        
        # Tax calculation
        if net_profit > 0:
            tax_amount = net_profit * (tax_rate / 100.0)
            final_profit = net_profit - tax_amount
            profit_after_tax = final_profit
            status = "profitable"
        else:
            tax_amount = 0.0
            final_profit = net_profit
            profit_after_tax = net_profit
            status = "loss"
        
        t1, t2, t3 = st.columns(3)
        t1.metric("Κέρδος Προ Φόρων", f"€{net_profit:,.2f}")
        t2.metric(f"Φόρος ({tax_rate:.1f}%)", f"€{tax_amount:,.2f}", 
                  help="Φόρος εισοδήματος υπό υπολογισμό")
        t3.metric("Κέρδος Μετά Φόρων", f"€{profit_after_tax:,.2f}", 
                  delta="Κέρδη" if status == "profitable" else "Ζημιές",
                  delta_color="normal" if status == "profitable" else "inverse")
        
        if status == "loss":
            st.warning("⚠️ **Ζημιοποίηση Περιόδου:** Δεν υπολογίζεται φόρος εισοδήματος")
    
    with tab_data:
        st.write("**Λεπτομέρειες Συναλλαγών Περιόδου**")
        
        df_display = df_period.copy()
        df_display['doc_date'] = df_display['doc_date'].dt.strftime('%d/%m/%Y')
        df_display = df_display.sort_values('doc_date', ascending=False)
        
        # Select and rename columns
        cols_to_show = ['doc_date', 'doc_no', 'doc_type', 'counterparty', 'description', 
                       'amount_net', 'vat_amount', 'amount_gross', 'payment_method', 'status']
        df_display = df_display[cols_to_show].copy()
        df_display.columns = ['Ημερ/νία', 'Αρ. Παρ/κου', 'Τύπος', 'Συναλλασσόμενος', 'Περιγραφή',
                             'Καθαρό', 'ΦΠΑ', 'Σύνολο', 'Πληρωμή', 'Κατάσταση']
        
        # Format currency
        for col in ['Καθαρό', 'ΦΠΑ', 'Σύνολο']:
            df_display[col] = df_display[col].apply(lambda x: f"€{x:,.2f}")
        
        st.dataframe(df_display, width='stretch', hide_index=True)
        
        # Download as CSV
        csv = df_display.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Λήψη Έκθεσης (CSV)",
            data=csv,
            file_name=f"fpa_foroi_{period_label}.csv",
            mime="text/csv"
        )

# --- LEDGERS ---
elif menu == "Καρτέλες (Ledgers)":
    st.title("📇 Καρτέλες Συναλλασσομένων")

    partners_df = pd.read_sql_query(
        text("SELECT DISTINCT counterparty FROM journal WHERE counterparty IS NOT NULL AND counterparty != ''"),
        ENGINE,
    )
    partners = sorted(partners_df['counterparty'].tolist())
    
    if not partners:
        st.warning("⚠️ Δεν υπάρχουν καταχωρημένοι συναλλασσόμενοι")
        st.stop()
    
    # Επιλογή συναλλασσόμενου
    st.subheader("🔍 Φίλτρα")
    sel = st.selectbox("Επιλογή Συναλλασσόμενου", partners, help="Επιλέξτε τον συναλλασσόμενο για να δείτε τις συναλλαγές του")
    
    if sel:
        df = pd.read_sql_query(
            text("SELECT * FROM journal WHERE counterparty = :counterparty ORDER BY doc_date DESC"),
            ENGINE,
            params={"counterparty": sel},
        )
        
        if df.empty:
            st.warning("⚠️ Δεν υπάρχουν συναλλαγές για τον επιλεγμένο συναλλασσόμενο")
            st.stop()
        
        # Convert date and clean data
        df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
        df = clean_dataframe(df)
        
        # Date and type filters
        has_dates = df['doc_date'].notna().any()
        col1, col2, col3 = st.columns(3)
        with col1:
            min_date = df['doc_date'].min()
            start_default = date.today() if pd.isna(min_date) else min_date.date()
            start_date = st.date_input("Από", value=start_default, help="Ημερομηνία έναρξης")
        
        with col2:
            max_date = df['doc_date'].max()
            end_default = date.today() if pd.isna(max_date) else max_date.date()
            end_date = st.date_input("Ως", value=end_default, help="Ημερομηνία λήξης")
        
        with col3:
            doc_types_in_data = sorted(
                {str(t).strip() for t in df['doc_type'].dropna().unique()
                 if str(t).strip() and str(t).strip().casefold() not in {"nan", "none", "<na>"}},
                key=str.casefold,
            )
            if not doc_types_in_data:
                doc_types_in_data = ["Income", "Expense", "Bill", "Transfer"]
            doc_type_filter = st.multiselect(
                "Τύπος Συναλλαγής",
                doc_types_in_data,
                default=doc_types_in_data,
                help="Επιλέξτε τύπους συναλλαγών προς εμφάνιση",
            )
        
        # Apply filters
        if has_dates:
            mask = (df['doc_date'].dt.date >= start_date) & (df['doc_date'].dt.date <= end_date)
        else:
            mask = pd.Series(True, index=df.index)
        if doc_type_filter:
            mask = mask & (df['doc_type'].isin(doc_type_filter))
        
        df_filtered = df[mask].copy()
        df_filtered = df_filtered.sort_values("doc_date", ascending=False)
        
        # Ensure all numeric columns are properly formatted
        for col in ['amount_net', 'vat_amount', 'amount_gross']:
            df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce').fillna(0.0)
        
        # Ensure amount_gross = amount_net + vat_amount if missing
        df_filtered.loc[df_filtered['amount_gross'] == 0, 'amount_gross'] = df_filtered['amount_net'] + df_filtered['vat_amount']
        
        if df_filtered.empty:
            st.warning("⚠️ Δεν βρέθηκαν συναλλαγές για τα επιλεγμένα κριτήρια")
        else:
            st.divider()
            st.subheader(f"📊 Καρτέλα: {sel}")
            
            # Calculations
            total_income = df_filtered[df_filtered['doc_type'] == 'Income']['amount_gross'].sum()
            total_expense = df_filtered[df_filtered['doc_type'].isin(['Expense', 'Bill'])]['amount_gross'].sum()
            unpaid_amount = df_filtered[df_filtered['status'] == 'Unpaid']['amount_gross'].sum()
            paid_amount = df_filtered[df_filtered['status'] == 'Paid']['amount_gross'].sum()
            
            # KPI Cards
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Εισροές", f"€{total_income:,.2f}", help="Σύνολο εισροών")
            k2.metric("Εκροές", f"€{total_expense:,.2f}", help="Σύνολο εκροών")
            k3.metric("Υπόλοιπο", f"€{total_income - total_expense:,.2f}", 
                     help="Εισροές - Εκροές")
            k4.metric("Πληρωμένα", f"€{paid_amount:,.2f}", help="Συναλλαγές με status 'Paid'")
            k5.metric("Ανοιχτά", f"€{unpaid_amount:,.2f}", help="Συναλλαγές με status 'Unpaid'",
                     delta="Πληρώνονται" if unpaid_amount > 0 else "Κάλυψη", delta_color="off")
            
            st.divider()
            st.subheader("📋 Λεπτομέρειες Συναλλαγών")
            
            # Format for display
            df_display = df_filtered.copy()
            df_display['doc_date'] = df_display['doc_date'].dt.strftime('%d/%m/%Y')
            
            cols_to_show = ['doc_date', 'doc_no', 'doc_type', 'description', 'amount_net', 
                           'vat_amount', 'amount_gross', 'payment_method', 'status']
            df_display = df_display[cols_to_show].copy()
            df_display.columns = ['Ημερ/νία', 'Αρ. Παρ/κου', 'Τύπος', 'Περιγραφή',
                                 'Καθαρό', 'ΦΠΑ', 'Σύνολο', 'Πληρωμή', 'Κατάσταση']
            
            # Format currency
            for col in ['Καθαρό', 'ΦΠΑ', 'Σύνολο']:
                df_display[col] = df_display[col].apply(lambda x: f"€{x:,.2f}")
            
            st.dataframe(df_display, width='stretch', hide_index=True)
            
            st.divider()
            # Summary by transaction type
            st.subheader("📊 Ανάλυση κατά Τύπο")
            summary = df_filtered.groupby('doc_type').agg({
                'amount_net': 'sum',
                'vat_amount': 'sum',
                'amount_gross': 'sum'
            }).round(2)
            summary.columns = ['Καθαρό', 'ΦΠΑ', 'Σύνολο']
            
            # Format summary
            summary_display = summary.copy()
            for col in summary_display.columns:
                summary_display[col] = summary_display[col].apply(lambda x: f"€{x:,.2f}")
            
            st.dataframe(summary_display, width='stretch')
            
            st.divider()
            # Download button
            csv = df_display.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Εξαγωγή Καρτέλας (CSV)",
                data=csv,
                file_name=f"kartela_{sel}_{start_date}_{end_date}.csv",
                mime="text/csv"
            )

# --- ARCHIVE ---
elif menu == "Αρχείο & Διορθώσεις":
    st.title("📚 Αρχείο & Διορθώσεις")

    with st.spinner("Φόρτωση αρχείου..."):
        df = load_journal_data()
    
    if df.empty:
        st.info("📭 Δεν υπάρχουν καταχωρήσεις στο αρχείο")
        st.stop()
    
    # Cleaning and conversion
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    df = clean_dataframe(df)
    df['id'] = df['id'].astype(int)  # ΣΗΜΑΝΤΙΚΟ: Μετατροπή id σε int
    
    st.subheader("📋 Όλες οι Εγγραφές")

    # Avoid writing to widget keys after instantiation.
    # If another action requested a display-mode switch, apply it BEFORE the selectbox is created.
    if "arch_display" not in st.session_state:
        st.session_state["arch_display"] = "Λίστα"
    if "arch_next_display" in st.session_state:
        st.session_state["arch_display"] = st.session_state.pop("arch_next_display")
    
    # Advanced Filters (toggle instead of expander to avoid chevrons)
    show_adv = st.toggle("🔍 Προηγμένα Φίλτρα", value=False, key="arch_adv_toggle")
    if show_adv:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("**Από Ημερομηνία**")
            st.caption("Επιλέξτε την αρχική ημερομηνία για φιλτράρισμα")
            date_from = st.date_input(
                "Από Ημερομηνία",
                value=df['doc_date'].min().date() if not df.empty else date.today(),
                key="arch_date_from",
            )

        with col2:
            st.markdown("**Έως Ημερομηνία**")
            st.caption("Επιλέξτε την τελική ημερομηνία για φιλτράρισμα")
            date_to = st.date_input(
                "Έως Ημερομηνία",
                value=df['doc_date'].max().date() if not df.empty else date.today(),
                key="arch_date_to",
            )

        with col3:
            st.markdown("**Ελάχιστο Ποσό**")
            st.caption("Εμφάνιση συναλλαγών άνω του ποσού αυτού")
            amount_min = st.number_input(
                "Ελάχιστο Ποσό (€)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="arch_amount_min",
            )

        with col4:
            st.markdown("**Μέγιστο Ποσό**")
            st.caption("Εμφάνιση συναλλαγών κάτω του ποσού αυτού")
            amount_max = st.number_input(
                "Μέγιστο Ποσό (€)",
                min_value=0.0,
                value=float(df['amount_gross'].max()) if not df.empty else 10000.0,
                step=10.0,
                key="arch_amount_max",
            )
    else:
        date_from = df['doc_date'].min().date() if not df.empty else date.today()
        date_to = df['doc_date'].max().date() if not df.empty else date.today()
        amount_min = 0.0
        amount_max = float(df['amount_gross'].max()) if not df.empty else 10000.0
    
    # Basic Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        sort_by = st.selectbox("Ταξινόμηση", 
                              ["Πιο Πρόσφατες", "Πιο Παλιές", "Μεγαλύτερα Ποσά", "Μικρότερα Ποσά"],
                              key="arch_sort")
    
    with col2:
        display_mode = st.selectbox("Εμφάνιση",
                                   ["Λίστα", "Λεπτομέρειες"],
                                   key="arch_display")
    
    with col3:
        search_term = st.text_input("Αναζήτηση", placeholder="Όνομα ή περιγραφή...", key="arch_search")
    
    with col4:
        # Normalize doc types to strings to avoid mixed-type sorting (e.g. str vs float)
        doc_type_raw = df.get('doc_type', pd.Series([], dtype=object))
        doc_type_series = doc_type_raw.fillna("").astype(str).str.strip()
        doc_types = sorted(
            {
                s
                for s in (str(v).strip() for v in doc_type_raw.unique())
                if s and s.casefold() not in ("nan", "none", "<na>")
            },
            key=str.casefold,
        )
        selected_type = st.multiselect(
            "Τύπος",
            doc_types,
            default=doc_types,
            key="arch_type",
        )
    
    # Apply filters
    mask = doc_type_series.isin(selected_type)
    
    # Date range filter
    mask = mask & (df['doc_date'].dt.date >= date_from) & (df['doc_date'].dt.date <= date_to)
    
    # Amount range filter
    mask = mask & (df['amount_gross'] >= amount_min) & (df['amount_gross'] <= amount_max)
    
    if search_term:
        mask = mask & (
            (df['counterparty'].str.contains(search_term, case=False, na=False)) |
            (df['description'].str.contains(search_term, case=False, na=False)) |
            (df['doc_no'].str.contains(search_term, case=False, na=False))
        )
    
    df_filtered = df[mask].copy()
    
    # Apply sorting
    if sort_by == "Πιο Πρόσφατες":
        df_filtered = df_filtered.sort_values('doc_date', ascending=False)
    elif sort_by == "Πιο Παλιές":
        df_filtered = df_filtered.sort_values('doc_date', ascending=True)
    elif sort_by == "Μεγαλύτερα Ποσά":
        df_filtered = df_filtered.sort_values('amount_gross', ascending=False)
    else:  # Μικρότερα Ποσά
        df_filtered = df_filtered.sort_values('amount_gross', ascending=True)
    
    if df_filtered.empty:
        st.warning("⚠️ Δεν βρέθηκαν εγγραφές")
    else:
        st.markdown(f"**Σύνολο:** {len(df_filtered)} εγγραφών")
        st.divider()
        
        if display_mode == "Λίστα":
            # ΑΠΛΗ ΛΙΣΤΑ
            for row in df_filtered.itertuples(index=False):
                rid = int(row.id)
                ddate = row.doc_date.strftime('%d/%m/%Y')
                cparty = row.counterparty if row.counterparty else '—'
                dtype = row.doc_type
                status = row.status
                amount = row.amount_gross
                
                # Icons
                type_icon = {'Income': '📥', 'Expense': '📤', 'Bill': '📋', 'Transfer': '🔄'}.get(dtype, '📍')
                status_text = "✅ Πληρωμένη" if status == "Paid" else "⏳ Εκκρεμής"
                
                with st.container(border=True):
                    st.markdown(f"{type_icon} **{cparty}** • {ddate} • **€{amount:,.2f}**")
                    st.caption(f"{dtype} | {status_text}")
                    
                    col_edit, col_del, col_id = st.columns([2, 2, 1])
                    with col_edit:
                        if st.button("Επεξεργασία", key=f"list_edit_{rid}", width='stretch'):
                            st.session_state["arch_next_display"] = "Λεπτομέρειες"
                            st.session_state["arch_focus_id"] = rid
                            st.rerun()
                    with col_del:
                        if st.button("Διαγραφή", key=f"list_del_{rid}", width='stretch'):
                            db_execute("DELETE FROM journal WHERE id = :id", {"id": rid})
                            st.success("Διαγράφηκε!")
                            time.sleep(0.3)
                            st.rerun()
                    with col_id:
                        st.caption(f"#{rid}")
        
        else:
            # ΛΕΠΤΟΜΕΡΕΙΕΣ
            # Always edit ONE record at a time.
            focus_id = st.session_state.pop("arch_focus_id", None)
            ids = [int(x) for x in df_filtered["id"].astype(int).tolist()] if not df_filtered.empty else []
            if not ids:
                st.warning("⚠️ Δεν βρέθηκαν εγγραφές για εμφάνιση")
                st.stop()

            # Pick default id: clicked one -> existing selector value -> first
            default_id = None
            if focus_id is not None:
                try:
                    fid = int(focus_id)
                    if fid in ids:
                        default_id = fid
                except Exception:
                    pass
            if default_id is None:
                try:
                    current_sel = int(st.session_state.get("arch_detail_id"))
                    if current_sel in ids:
                        default_id = current_sel
                except Exception:
                    pass
            if default_id is None:
                default_id = ids[0]

            # Nice label per id
            label_by_id = {}
            try:
                tmp = df_filtered.copy()
                tmp["doc_date"] = pd.to_datetime(tmp["doc_date"], errors="coerce")
                for r in tmp.itertuples(index=False):
                    rid0 = int(r.id)
                    d = r.doc_date.strftime('%d/%m/%Y') if hasattr(r.doc_date, "strftime") and pd.notna(r.doc_date) else "—"
                    cp = r.counterparty if getattr(r, "counterparty", None) else "—"
                    amt = float(getattr(r, "amount_gross", 0.0) or 0.0)
                    label_by_id[rid0] = f"#{rid0} • {d} • {cp} • €{amt:,.2f}"
            except Exception:
                pass

            selected_id = st.selectbox(
                "Επιλογή Εγγραφής",
                options=ids,
                index=ids.index(default_id),
                format_func=lambda x: label_by_id.get(int(x), f"#{int(x)}"),
                key="arch_detail_id",
            )

            row = next(df_filtered[df_filtered["id"].astype(int) == int(selected_id)].itertuples(index=False))
            rid = int(row.id)
            ddate = row.doc_date.strftime('%d/%m/%Y')
            cparty = row.counterparty if row.counterparty else '—'
            
            with st.container(border=True):
                st.markdown(f"### #{rid} - {cparty}")
                
                # Display current values
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Ημ/νία:** {ddate}")
                    st.write(f"**Τύπος:** {row.doc_type}")
                with col2:
                    st.write(f"**Αρ. Παρ/κου:** {row.doc_no if row.doc_no else '—'}")
                    st.write(f"**Κατάσταση:** {row.status}")
                with col3:
                    st.write(f"**Καθαρό:** €{row.amount_net:,.2f}")
                    st.write(f"**Σύνολο:** €{row.amount_gross:,.2f}")
                
                st.write(f"**Περιγραφή:** {row.description if row.description else '—'}")
                
                st.divider()
                st.subheader("Διόρθωση")
                
                # Edit form
                f1, f2, f3 = st.columns(3)

                types = ["Income", "Expense", "Bill", "Transfer", "Cash Withdrawal", "Cash Deposit", "Bank Operation"]
                if row.doc_type not in types:
                    types.append(row.doc_type)

                with f1:
                    new_date = st.date_input("Ημερομηνία", value=row.doc_date, key=f"ed_dt_{rid}")
                    new_type = st.selectbox("Τύπος", types, index=types.index(row.doc_type), key=f"ed_tp_{rid}")
                    new_partner = st.text_input("Συναλλασσόμενος", value=row.counterparty, key=f"ed_cp_{rid}")

                with f2:
                    new_docno = st.text_input("Αρ. Παρ/κου", value=row.doc_no, key=f"ed_dn_{rid}")
                    new_descr = st.text_input("Περιγραφή", value=row.description, key=f"ed_dc_{rid}")
                    pays = ["Τράπεζα", "Μετρητά", "Επί Πιστώσει"]
                    cur_pay = row.payment_method if row.payment_method in pays else pays[0]
                    new_pay = st.selectbox("Πληρωμή", pays, index=pays.index(cur_pay), key=f"ed_py_{rid}")
                    bank_accounts = load_bank_accounts()
                    cur_bank = str(row.bank_account or "").strip()
                    bank_opts = ["(Κενό)", "(Νέος Λογαριασμός)"] + bank_accounts
                    if cur_bank and cur_bank in bank_accounts:
                        bank_idx = bank_opts.index(cur_bank)
                    elif not cur_bank:
                        bank_idx = 0
                    else:
                        bank_idx = 1
                    sel_bank = st.selectbox("Λογαριασμός", bank_opts, index=bank_idx, key=f"ed_ba_sel_{rid}")
                    if sel_bank == "(Κενό)":
                        new_bank = ""
                    elif sel_bank == "(Νέος Λογαριασμός)":
                        new_bank = st.text_input("Νέος Λογαριασμός", value=cur_bank, key=f"ed_ba_new_{rid}")
                    else:
                        new_bank = sel_bank
                    
                    with f3:
                        new_net = st.number_input("Καθαρό €", value=float(row.amount_net), key=f"ed_net_{rid}")
                        vat_r = 24
                        if row.amount_net > 0 and row.vat_amount > 0:
                            vat_r = int(row.vat_amount / row.amount_net * 100)
                        vat_r = max(0, min(vat_r, 24))
                        new_vat_rate = st.selectbox("ΦΠΑ %", [24, 13, 6, 0], 
                                                   index=[24, 13, 6, 0].index(vat_r) if vat_r in [24, 13, 6, 0] else 0, 
                                                   key=f"ed_vr_{rid}")
                        stats = ["Paid", "Unpaid"]
                        new_stat = st.selectbox("Κατάσταση", stats, 
                                               index=stats.index(row.status) if row.status in stats else 1,
                                               key=f"ed_st_{rid}")
                        gl_list = load_gl_codes()
                        cur_gl = str(row.gl_code or "").strip()
                        gl_opts = gl_list if gl_list else ["999"]
                        # Map stored code to display option
                        gl_display = cur_gl
                        if cur_gl:
                            for opt in gl_opts:
                                if str(opt).split(" - ")[0] == cur_gl:
                                    gl_display = opt
                                    break
                        if gl_display in gl_opts:
                            gl_idx = gl_opts.index(gl_display)
                        else:
                            gl_idx = 0
                        new_gl_choice = st.selectbox("GL", gl_opts, index=gl_idx, key=f"ed_gl_{rid}")
                        new_gl = str(new_gl_choice).split(" - ")[0] if new_gl_choice else "999"
                    
                    new_vat = round(new_net * (new_vat_rate / 100), 2)
                    new_gross = round(new_net + new_vat, 2)
                    st.info(f"ΦΠΑ: €{new_vat:,.2f} | Σύνολο: €{new_gross:,.2f}")
                    
                    st.divider()
                    
                    col_upd, col_del = st.columns(2)
                    with col_upd:
                        if st.button("Ενημέρωση", key=f"det_upd_{rid}", width='stretch', type="primary"):
                            # Validate updated data
                            upd_data = {
                                'partner': new_partner,
                                'description': new_descr,
                                'amount_net': new_net,
                                'vat_amount': new_vat,
                                'amount_gross': new_gross
                            }
                            upd_errors = validate_transaction_input(upd_data)
                            if upd_errors:
                                for error in upd_errors:
                                    st.error(f"❌ {error}")
                            else:
                                try:
                                    db_execute(
                                        """UPDATE journal SET
                                                doc_date = :doc_date,
                                                doc_no = :doc_no,
                                                doc_type = :doc_type,
                                                counterparty = :counterparty,
                                                description = :description,
                                                gl_code = :gl_code,
                                                amount_net = :amount_net,
                                                vat_amount = :vat_amount,
                                                amount_gross = :amount_gross,
                                                payment_method = :payment_method,
                                                bank_account = :bank_account,
                                                status = :status
                                            WHERE id = :id""",
                                        {
                                            "doc_date": new_date.strftime('%Y-%m-%d') if hasattr(new_date, 'strftime') else str(new_date),
                                            "doc_no": new_docno,
                                            "doc_type": new_type,
                                            "counterparty": new_partner,
                                            "description": new_descr,
                                            "gl_code": new_gl,
                                            "amount_net": float(new_net),
                                            "vat_amount": float(new_vat),
                                            "amount_gross": float(new_gross),
                                            "payment_method": new_pay,
                                            "bank_account": new_bank,
                                            "status": new_stat,
                                            "id": rid,
                                        },
                                    )
                                    st.cache_data.clear()  # Clear cache after update
                                    st.session_state.pop("arch_focus_id", None)
                                    st.success("✓ Ενημερώθηκε!")
                                    time.sleep(0.3)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Σφάλμα κατά την ενημέρωση: {str(e)}")
                    with col_del:
                        if st.button("Διαγραφή", key=f"det_del_{rid}", width='stretch', type="secondary"):
                            try:
                                db_execute("DELETE FROM journal WHERE id = :id", {"id": rid})
                                st.cache_data.clear()  # Clear cache after delete
                                st.session_state.pop("arch_focus_id", None)
                                st.session_state.pop("arch_detail_id", None)
                                st.error("✗ Διαγράφηκε!")
                                time.sleep(0.3)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Σφάλμα κατά τη διαγραφή: {str(e)}")

# --- TREASURY ---
elif menu == "Ταμείο & Τράπεζες":
    st.title("💵 Διαχείριση Διαθεσίμων")

    df_all = load_journal_data()
    
    df_all['doc_date'] = pd.to_datetime(df_all['doc_date'], errors='coerce')
    df_all = clean_dataframe(df_all)
    
    # Filter only paid transactions
    df = df_all[df_all['status'] == 'Paid'].copy()
    
    if df.empty:
        st.warning("⚠️ Δεν υπάρχουν πληρωμένες συναλλαγές")
        st.stop()
    
    # Calculate cash flow
    df['flow'] = df.apply(
        lambda x: x['amount_gross'] if x['doc_type'] == 'Income' else -x['amount_gross'],
        axis=1
    )
    df['bank_account'] = df['bank_account'].fillna('Ταμείο').astype(str)
    
    st.subheader("📊 Σύνοψη Διαθεσίμων")
    
    # Separate cash and bank accounts
    cash_mask = df['bank_account'].str.contains("Ταμείο|Cash|Μετρητά", case=False, na=False)
    cash_df = df[cash_mask]
    bank_df = df[~cash_mask]
    
    # Calculate totals
    total_cash_flow = cash_df['flow'].sum() if not cash_df.empty else 0.0
    total_bank_flow = bank_df['flow'].sum() if not bank_df.empty else 0.0
    total_available = total_cash_flow + total_bank_flow
    
    # Display KPIs
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    kpi1.metric(
        "💶 Ταμείο (Μετρητά)",
        f"€{total_cash_flow:,.2f}",
        help="Σύνολο διαθεσίμων σε μετρητά"
    )
    
    kpi2.metric(
        "🏦 Σύνολο Τραπεζών",
        f"€{total_bank_flow:,.2f}",
        help="Σύνολο διαθεσίμων σε τραπεζικούς λογαριασμούς"
    )
    
    kpi3.metric(
        "💰 Συνολικά Διαθέσιμα",
        f"€{total_available:,.2f}",
        help="Ταμείο + Τράπεζες"
    )
    
    # Incoming and outgoing
    income_total = df[df['doc_type'] == 'Income']['amount_gross'].sum()
    expense_total = df[df['doc_type'].isin(['Expense', 'Bill', 'Cash Withdrawal'])]['amount_gross'].sum()
    
    kpi4.metric(
        "📈 Ροή Κεφαλαίων",
        f"€{income_total - expense_total:,.2f}",
        delta=f"Εισροές: €{income_total:,.0f}" if income_total > 0 else "Αρνητικά"
    )
    
    st.divider()
    
    # Detailed breakdown by account
    st.subheader("🏦 Λογαριασμοί & Υπόλοιπα")
    
    # Get all unique accounts
    all_accounts = df['bank_account'].unique()
    
    account_summary = []
    for account in sorted(all_accounts):
        acc_df = df[df['bank_account'] == account]
        balance = acc_df['flow'].sum()
        is_cash = account.lower().find("ταμείο") >= 0 or account.lower().find("cash") >= 0
        acc_type = "💶 Μετρητά" if is_cash else "🏦 Τράπεζα"
        
        account_summary.append({
            'Λογαριασμός': f"{acc_type} {account}",
            'Υπόλοιπο': f"€{balance:,.2f}",
            'Εισροές': f"€{acc_df[acc_df['doc_type']=='Income']['amount_gross'].sum():,.2f}",
            'Εκροές': f"€{acc_df[acc_df['doc_type'].isin(['Expense','Bill','Cash Withdrawal'])]['amount_gross'].sum():,.2f}",
            'Συναλλαγές': len(acc_df)
        })
    
    if account_summary:
        acc_df_display = pd.DataFrame(account_summary)
        st.dataframe(acc_df_display, width='stretch', hide_index=True)
    
    st.divider()
    
    # Cash flow trends
    st.subheader("📈 Τάσεις Ταμείου - Τελευταίες Συναλλαγές")
    
    # Sort by date descending
    df_sorted = df.sort_values('doc_date', ascending=False)
    
    # Show recent transactions
    recent = st.selectbox(
        "Εμφάνιση τελευταίων:",
        options=[10, 20, 50],
        format_func=lambda x: f"{x} συναλλαγές",
        key="treasury_recent"
    )
    
    df_recent = df_sorted.head(recent).sort_values('doc_date', ascending=True).copy()
    df_recent['doc_date_str'] = df_recent['doc_date'].dt.strftime('%d/%m/%Y')
    
    # Create display dataframe
    display_cols = {
        'doc_date_str': 'Ημερ/νία',
        'doc_type': 'Τύπος',
        'counterparty': 'Συναλλασσόμενος',
        'bank_account': 'Λογαριασμός',
        'amount_gross': 'Ποσό'
    }
    
    df_display = df_recent[[col for col in display_cols.keys()]].copy()
    df_display.columns = [col for col in display_cols.values()]
    
    # Format amount based on type
    df_display['Ποσό'] = df_recent.apply(
        lambda x: f"+€{x['amount_gross']:,.2f}" if x['doc_type'] == 'Income' else f"-€{x['amount_gross']:,.2f}",
        axis=1
    )
    
    st.dataframe(df_display, width='stretch', hide_index=True)
    
    # Monthly balance chart
    st.divider()
    st.subheader("📊 Ιστορικό Υπολοίπων (Ανά Μήνα)")
    
    df_monthly = df.copy()
    df_monthly['month'] = df_monthly['doc_date'].dt.to_period('M')
    monthly_flow = df_monthly.groupby('month')['flow'].sum().reset_index()
    monthly_flow['month'] = monthly_flow['month'].astype(str)
    monthly_flow = monthly_flow.sort_values('month')
    
    if not monthly_flow.empty:
        # Calculate cumulative balance
        monthly_flow['cumulative'] = monthly_flow['flow'].cumsum()
        
        fig = px.bar(
            monthly_flow,
            x='month',
            y='flow',
            title='Μηνιαία Ροή Κεφαλαίων',
            labels={'month': 'Περίοδος', 'flow': 'Ροή (€)'},
            color='flow',
            color_continuous_scale=['#ef4444', '#10b981']  # Red for negative, Green for positive
        )
        
        fig.update_layout(
            plot_bgcolor='#f8f9fa',
            paper_bgcolor='#ffffff',
            hovermode='x unified',
            xaxis_title="Μήνας",
            yaxis_title="Ποσό (€)",
            showlegend=False,
            height=400
        )
        
        st.plotly_chart(fig, width='stretch')
        
        st.info(f"📌 **Τελευταία ενημέρωση:** {df['doc_date'].max().strftime('%d/%m/%Y')}")
    
    st.divider()
    st.subheader("💡 Σημειώσεις")
    st.markdown("""
    - **Ταμείο:** Μετρητά που είναι φυσικά σε κατάθεση ή χέρι
    - **Τράπεζες:** Λογαριασμοί σε τραπεζικές ιδρύματα
    - **Ροή Κεφαλαίων:** Εισροές (θετικές) - Εκροές (αρνητικές)
    - **Εμφανίζονται μόνο** πληρωμένες συναλλαγές (Status = Paid)
    """)

# --- SETTINGS ---
elif menu == "Ρυθμίσεις GL":
    st.title("⚙️ Διαχείριση Ρυθμίσεων")
    
    
    # Create tabs for different settings
    tab_gl, tab_customers, tab_suppliers, tab_banks, tab_system = st.tabs([
        "📚 GL Codes", 
        "👥 Πελάτες", 
        "🏭 Προμηθευτές",
        "🏦 Τραπεζικοί Λογαριασμοί",
        "⚙️ Σύστημα"
    ])
    
    # --- TAB 1: GL CODES ---
    with tab_gl:
        st.subheader("📚 Λογαριασμοί GL (Γενικό Καθολικό)")
        
        # Load GL codes
        df_gl = pd.read_sql_query("SELECT * FROM gl_codes ORDER BY code", ENGINE)
        df_gl['code'] = df_gl['code'].astype(str)
        
        # Show current GL codes
        st.write(f"**Σύνολο GL Codes:** {len(df_gl)}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Υπάρχουσες Ρυθμίσεις:**")
            edited_gl = st.data_editor(df_gl, num_rows="dynamic", width='stretch', key="gl_editor")
            
            if st.button("Αποθήκευση GL Codes", width='stretch', type="primary"):
                try:
                    db_execute("DELETE FROM gl_codes")
                    rows = [
                        {
                            "code": str(r.get('code', '')).strip(),
                            "description": str(r.get('description', '')).strip(),
                        }
                        for _, r in edited_gl.iterrows()
                        if str(r.get('code', '')).strip()
                    ]
                    if rows:
                        db_executemany(
                            "INSERT INTO gl_codes (code, description) VALUES (:code, :description)",
                            rows,
                        )
                    st.cache_data.clear()
                    st.success("✓ GL Codes αποθηκεύτηκαν!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Σφάλμα: {str(e)}")
        
        with col2:
            st.write("**Προσθήκη Νέου:**")
            new_code = st.text_input("Κωδικός", placeholder="π.χ. 500")
            new_desc = st.text_input("Περιγραφή", placeholder="π.χ. Πωλήσεις Υπηρεσιών")
            
            if st.button("Προσθήκη GL", width='stretch'):
                if new_code and new_desc:
                    try:
                        db_execute(
                            "INSERT INTO gl_codes (code, description) VALUES (:code, :description)",
                            {"code": str(new_code).strip(), "description": str(new_desc).strip()},
                        )
                        st.cache_data.clear()
                        st.success("✓ Προστέθηκε!")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Σφάλμα: {str(e)}")
                else:
                    st.warning("Συμπληρώστε όλα τα πεδία")
    
    # --- TAB 2: CUSTOMERS ---
    with tab_customers:
        st.subheader("👥 Διαχείριση Πελατών")
        df_customers = pd.read_sql_query(
            "SELECT name FROM counterparties WHERE kind = 'customer' ORDER BY name",
            ENGINE,
        )
        customers = df_customers["name"].tolist() if not df_customers.empty else []
        
        st.write(f"**Σύνολο Πελατών:** {len(customers)}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Υπάρχοντες Πελάτες:**")
            if customers:
                customers_df = pd.DataFrame({'Όνομα Πελάτη': customers})
                st.dataframe(customers_df, width='stretch', hide_index=True)
            else:
                st.info("Δεν υπάρχουν εγγεγραμμένοι πελάτες ακόμα")
        
        with col2:
            st.write("**Προσθήκη Νέου Πελάτη:**")
            customer_name = st.text_input("Όνομα Πελάτη", placeholder="π.χ. ΑΒΓ ΑΕ")
            
            if st.button("Προσθήκη Πελάτη", width='stretch'):
                if customer_name:
                    try:
                        customer_name = str(customer_name).strip()
                        upsert_counterparty(customer_name, "customer")
                        st.cache_data.clear()
                        st.success(f"✓ Πελάτης '{customer_name}' προστέθηκε!")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Σφάλμα: {str(e)}")
                else:
                    st.warning("Εισάγετε όνομα πελάτη")

            st.divider()
            st.write("**Διόρθωση / Διαγραφή Πελάτη:**")
            if customers:
                sel_customer = st.selectbox("Επιλογή Πελάτη", customers, key="cust_sel")
                new_name = st.text_input("Νέο Όνομα", value=str(sel_customer), key="cust_rename")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Αποθήκευση Αλλαγής", width='stretch', key="cust_save", type="primary"):
                        try:
                            old = str(sel_customer).strip()
                            nn = str(new_name).strip()
                            if not nn:
                                st.warning("Το νέο όνομα δεν μπορεί να είναι κενό")
                            else:
                                if old != nn:
                                    db_execute(
                                        "UPDATE journal SET counterparty = :nn WHERE counterparty = :old",
                                        {"nn": nn, "old": old},
                                    )
                                    db_execute(
                                        "DELETE FROM counterparties WHERE name = :old",
                                        {"old": old},
                                    )
                                upsert_counterparty(nn, "customer")
                                st.cache_data.clear()
                                st.success("✓ Ενημερώθηκε!")
                                time.sleep(0.3)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Σφάλμα: {str(e)}")
                with col_b:
                    if st.button("Διαγραφή από λίστα", width='stretch', type="secondary", key="cust_del"):
                        try:
                            nm = str(sel_customer).strip()
                            db_execute("DELETE FROM counterparties WHERE name = :n", {"n": nm})
                            st.cache_data.clear()
                            st.success("✓ Διαγράφηκε από τη λίστα.")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Σφάλμα: {str(e)}")
            else:
                st.info("Δεν υπάρχουν πελάτες για αφαίρεση")
    
    # --- TAB 3: SUPPLIERS ---
    with tab_suppliers:
        st.subheader("🏭 Διαχείριση Προμηθευτών")
        df_suppliers = pd.read_sql_query(
            "SELECT name FROM counterparties WHERE kind = 'supplier' ORDER BY name",
            ENGINE,
        )
        suppliers = df_suppliers["name"].tolist() if not df_suppliers.empty else []
        
        st.write(f"**Σύνολο Προμηθευτών:** {len(suppliers)}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Υπάρχοντες Προμηθευτές:**")
            if suppliers:
                suppliers_df = pd.DataFrame({'Όνομα Προμηθευτή': suppliers})
                st.dataframe(suppliers_df, width='stretch', hide_index=True)
            else:
                st.info("Δεν υπάρχουν εγγεγραμμένοι προμηθευτές ακόμα")
        
        with col2:
            st.write("**Προσθήκη Νέου Προμηθευτή:**")
            supplier_name = st.text_input("Όνομα Προμηθευτή", placeholder="π.χ. ΔΕΖ ΑΕ")
            
            if st.button("Προσθήκη Προμηθευτή", width='stretch'):
                if supplier_name:
                    try:
                        supplier_name = str(supplier_name).strip()
                        upsert_counterparty(supplier_name, "supplier")
                        st.cache_data.clear()
                        st.success(f"✓ Προμηθευτής '{supplier_name}' προστέθηκε!")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Σφάλμα: {str(e)}")
                else:
                    st.warning("Εισάγετε όνομα προμηθευτή")

            st.divider()
            st.write("**Διόρθωση / Διαγραφή Προμηθευτή:**")
            if suppliers:
                sel_supplier = st.selectbox("Επιλογή Προμηθευτή", suppliers, key="sup_sel")
                new_name = st.text_input("Νέο Όνομα", value=str(sel_supplier), key="sup_rename")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Αποθήκευση Αλλαγής", width='stretch', key="sup_save", type="primary"):
                        try:
                            old = str(sel_supplier).strip()
                            nn = str(new_name).strip()
                            if not nn:
                                st.warning("Το νέο όνομα δεν μπορεί να είναι κενό")
                            else:
                                if old != nn:
                                    db_execute(
                                        "UPDATE journal SET counterparty = :nn WHERE counterparty = :old",
                                        {"nn": nn, "old": old},
                                    )
                                    db_execute(
                                        "DELETE FROM counterparties WHERE name = :old",
                                        {"old": old},
                                    )
                                upsert_counterparty(nn, "supplier")
                                st.cache_data.clear()
                                st.success("✓ Ενημερώθηκε!")
                                time.sleep(0.3)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Σφάλμα: {str(e)}")
                with col_b:
                    if st.button("Διαγραφή από λίστα", width='stretch', type="secondary", key="sup_del"):
                        try:
                            nm = str(sel_supplier).strip()
                            db_execute("DELETE FROM counterparties WHERE name = :n", {"n": nm})
                            st.cache_data.clear()
                            st.success("✓ Διαγράφηκε από τη λίστα.")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Σφάλμα: {str(e)}")
            else:
                st.info("Δεν υπάρχουν προμηθευτές για αφαίρεση")
    
    # --- TAB 4: BANK ACCOUNTS ---
    with tab_banks:
        st.subheader("🏦 Διαχείριση Τραπεζικών Λογαριασμών")
        df_accounts = pd.read_sql_query(
            "SELECT name, kind FROM bank_accounts ORDER BY name",
            ENGINE,
        )
        accounts = df_accounts["name"].tolist() if not df_accounts.empty else []
        
        st.write(f"**Σύνολο Λογαριασμών:** {len(accounts)}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Υπάρχοντες Λογαριασμοί:**")
            if accounts:
                show_df = df_accounts.copy()
                show_df["kind"] = show_df["kind"].map({"bank": "Τράπεζα", "cash": "Ταμείο"}).fillna(show_df["kind"])
                show_df.columns = ["Λογαριασμός", "Τύπος"]
                st.dataframe(show_df, width='stretch', hide_index=True)
            else:
                st.info("Δεν υπάρχουν εγγεγραμμένοι λογαριασμοί ακόμα")
        
        with col2:
            st.write("**Άνοιγμα Νέου Λογαριασμού:**")
            
            account_type = st.selectbox("Τύπος Λογαριασμού", ["Τράπεζα", "Ταμείο"])
            account_name = st.text_input("Όνομα Λογαριασμού", placeholder="π.χ. Alpha Bank EUR")
            
            if st.button("Άνοιγμα Λογαριασμού", width='stretch'):
                if account_name:
                    full_account = f"{account_type} - {account_name}"
                    try:
                        full_account = str(full_account).strip()
                        upsert_bank_account(full_account, "cash" if account_type == "Ταμείο" else "bank")
                        st.cache_data.clear()
                        st.success(f"✓ Λογαριασμός '{full_account}' δημιουργήθηκε!")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Σφάλμα: {str(e)}")
                else:
                    st.warning("Εισάγετε όνομα λογαριασμού")

            st.divider()
            st.write("**Διόρθωση / Διαγραφή Λογαριασμού:**")
            if accounts:
                sel_account = st.selectbox("Επιλογή Λογαριασμού", accounts, key="bank_sel")
                cur_kind = (
                    df_accounts.set_index("name").loc[sel_account, "kind"]
                    if (not df_accounts.empty and sel_account in set(df_accounts["name"]))
                    else "bank"
                )
                new_kind_label = st.selectbox(
                    "Τύπος",
                    ["Τράπεζα", "Ταμείο"],
                    index=0 if str(cur_kind) == "bank" else 1,
                    key="bank_kind",
                )
                new_name = st.text_input("Νέο Όνομα", value=str(sel_account), key="bank_rename")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Αποθήκευση Αλλαγής", width='stretch', key="bank_save", type="primary"):
                        try:
                            old = str(sel_account).strip()
                            nn = str(new_name).strip()
                            kd = "cash" if new_kind_label == "Ταμείο" else "bank"
                            if not nn:
                                st.warning("Το νέο όνομα δεν μπορεί να είναι κενό")
                            else:
                                if old != nn:
                                    db_execute(
                                        "UPDATE journal SET bank_account = :nn WHERE bank_account = :old",
                                        {"nn": nn, "old": old},
                                    )
                                    db_execute("DELETE FROM bank_accounts WHERE name = :old", {"old": old})
                                upsert_bank_account(nn, kd)
                                st.cache_data.clear()
                                st.success("✓ Ενημερώθηκε!")
                                time.sleep(0.3)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Σφάλμα: {str(e)}")
                with col_b:
                    if st.button("Διαγραφή από λίστα", width='stretch', type="secondary", key="bank_del"):
                        try:
                            nm = str(sel_account).strip()
                            db_execute("DELETE FROM bank_accounts WHERE name = :n", {"n": nm})
                            st.cache_data.clear()
                            st.success("✓ Διαγράφηκε από τη λίστα.")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Σφάλμα: {str(e)}")
            else:
                st.info("Δεν υπάρχουν λογαριασμοί για αφαίρεση")
    
    # --- TAB 5: SYSTEM ---
    with tab_system:
        st.subheader("⚙️ Ρυθμίσεις Συστήματος")

        st.write("**Πληροφορίες Χρήστη:**")
        st.code(f"Συνδεδεμένος χρήστης: {st.session_state.username}")
        
        st.write("**Πληροφορίες Βάσης Δεδομένων:**")

        try:
            if DB_DIALECT == "postgres":
                d = _safe_db_diagnostics()
                host = d.get("host", "")
                dbn = d.get("db", "")
                sslmode = d.get("sslmode", "")
                st.code(f"Βάση: Postgres (Supabase)\nHost: {host}\nDB: {dbn}\nsslmode: {sslmode}")
            else:
                st.code(f"Βάση: SQLite\nDB file: {DB_FILE}")
                st.warning(
                    "SQLite είναι τοπικό αρχείο. Για 100% μόνιμη αποθήκευση (ειδικά σε Streamlit Cloud) χρησιμοποίησε Postgres/Supabase μέσω `DATABASE_URL`."
                )
        except Exception:
            pass
        
        # Get database statistics
        total_records = int(db_scalar("SELECT COUNT(*) FROM journal", default=0))
        gl_count = int(db_scalar("SELECT COUNT(*) FROM gl_codes", default=0))
        
        stat1, stat2 = st.columns(2)
        stat1.metric("📝 Σύνολο Εγγραφών", f"{total_records}")
        stat2.metric("📚 GL Codes", f"{gl_count}")

        st.divider()

        show_shortcuts = st.toggle("⌨️ Συντομεύσεις Πληκτρολογίου", value=False, key="sys_shortcuts_toggle")
        if show_shortcuts:
            st.markdown("""
            **📝 Νέα Εγγραφή:**
            - `Ctrl + S`: Αποθήκευση

            **🔍 Αναζήτηση:**
            - `Ctrl + F`: Εστίαση στο πεδίο αναζήτησης

            **🧭 Πλοήγηση:**
            - `Alt + 1-7`: Άμεση μετάβαση στο μενού
            """)
        
        st.divider()
        
        st.write("**Δράσεις Διαχείρισης:**")
        
        # Database reset
        st.warning("⚠️ **Επικίνδυνες Λειτουργίες** (χρησιμοποιήστε με προσοχή)")
        
        if st.button("Διαγραφή ΌΛΩΝ των δεδομένων (Reset DB)", width='stretch', type="secondary"):
            if st.button("Επιβεβαίωση: Διαγραφή όλων", width='stretch'):
                try:
                    db_execute("DELETE FROM journal")
                    db_execute("DELETE FROM gl_codes")
                    try:
                        db_execute("DELETE FROM counterparties")
                    except Exception:
                        pass
                    try:
                        db_execute("DELETE FROM bank_accounts")
                    except Exception:
                        pass
                    init_db()
                    st.error("✗ Η βάση καθαρίστηκε πλήρως!")
                    st.info("Η εφαρμογή ξανα-αρχικοποίησε τα βασικά GL codes.")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Σφάλμα: {str(e)}")
        
        st.divider()
        st.write("**Πληροφορίες Συστήματος:**")
        db_location = "Postgres (DATABASE_URL)" if DB_DIALECT == "postgres" else DB_FILE
        st.code(f"""
    Βάση: {db_location}
    Τύπος Βάσης: {DB_DIALECT}
Σύνολο Εγγραφών: {total_records}
GL Codes: {gl_count}
Τελευταία Ενημέρωση: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        """)

