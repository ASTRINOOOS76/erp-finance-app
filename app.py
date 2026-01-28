import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import time
from datetime import datetime, date

# --- 1. CONFIG ---
st.set_page_config(page_title="SalesTree ERP Final", layout="wide", page_icon="🏢")
# Always resolve DB path relative to this file so Streamlit's working directory
# (which can vary depending on how the app is launched) doesn't create/read a different DB.
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erp_tax_fixed_v2.db")

# --- 2. CSS (ΧΡΩΜΑΤΑ ΚΑΙ ΤΥΠΟΓΡΑΦΙΑ) ---
st.markdown("""
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
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(45, 90, 140, 0.2) !important;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #1a365d 0%, #0f1f3c 100%) !important;
        box-shadow: 0 4px 12px rgba(45, 90, 140, 0.3) !important;
        transform: translateY(-2px) !important;
    }
    
    .stInfo {
        background-color: #e8f4f8 !important;
        border-left: 4px solid #2d5a8c !important;
        color: #1a365d !important;
        border-radius: 6px !important;
    }
    
    .stWarning {
        background-color: #fff5e6 !important;
        border-left: 4px solid #d97706 !important;
        color: #7c2d12 !important;
        border-radius: 6px !important;
    }
    
    .stSuccess {
        background-color: #e8f5e9 !important;
        border-left: 4px solid #10b981 !important;
        color: #065f46 !important;
        border-radius: 6px !important;
    }
    
    [role="tablist"] button {
        color: #34568b !important;
        font-weight: 600 !important;
        border-bottom: 2px solid #cbd5e0 !important;
    }
    
    [role="tablist"] button[aria-selected="true"] {
        color: #2d5a8c !important;
        border-bottom: 2px solid #2d5a8c !important;
    }
    
    /* ===== TABLE STYLING ===== */
    .dataframe {
        width: 100% !important;
        border-collapse: collapse !important;
        background-color: #ffffff !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }
    
    .dataframe thead {
        background: linear-gradient(90deg, #1a365d 0%, #2d5a8c 100%) !important;
    }
    
    .dataframe thead th {
        color: #ffffff !important;
        font-weight: 700 !important;
        padding: 16px 12px !important;
        text-align: left !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.5px !important;
        border-bottom: none !important;
        text-transform: uppercase !important;
    }
    
    .dataframe tbody tr {
        border-bottom: 1px solid #e2e8f0 !important;
        transition: background-color 0.2s ease !important;
    }
    
    .dataframe tbody tr:hover {
        background-color: #f0f4f8 !important;
    }
    
    .dataframe tbody tr:last-child {
        border-bottom: none !important;
    }
    
    .dataframe tbody td {
        color: #0f172a !important;
        padding: 14px 12px !important;
        font-size: 0.9rem !important;
        vertical-align: middle !important;
    }
    
    .dataframe tbody td:first-child {
        font-weight: 500 !important;
    }
    
    /* Numeric columns alignment */
    .dataframe tbody td[data-dtype="int64"],
    .dataframe tbody td[data-dtype="float64"] {
        text-align: right !important;
        font-weight: 500 !important;
    }
    
    /* Striped rows for better readability */
    .dataframe tbody tr:nth-child(even) {
        background-color: #f8f9fa !important;
    }
    
    /* ===== CUSTOM DATAFRAME CLASS ===== */
    .stDataFrame {
        border-radius: 8px !important;
    }

    /* ===== PROFESSIONAL UI OVERRIDES (cleaner + more enterprise) ===== */
    :root {
        --st-brand: #00d084;   /* SalesTree green */
        --st-navy: #0b2b4c;    /* deep navy */
        --st-bg: #F7FAFC;      /* soft background */
        --st-border: #e3e9f0;
        --st-text: #1A202C;
        --st-muted: #587089;
        --st-hover: #e0fcff;
    }

    .stApp {
        background: var(--st-bg) !important;
    }

    .main .block-container {
        padding-top: 1.25rem !important;
        padding-bottom: 2rem !important;
    }

    h1 {
        color: var(--st-navy) !important;
        font-size: 2.05rem !important;
        letter-spacing: -0.5px !important;
        margin-bottom: 1.0rem !important;
    }

    h2 {
        color: var(--st-navy) !important;
        font-size: 1.55rem !important;
        margin-top: 1.25rem !important;
        margin-bottom: 0.75rem !important;
    }

    h3, h4 {
        color: var(--st-navy) !important;
    }

    div[data-testid="metric-container"] {
        background: #ffffff !important;
        border: 1px solid var(--st-border) !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06) !important;
    }

    div[data-testid="metric-container"] label {
        text-transform: none !important;
        letter-spacing: 0 !important;
        font-size: 0.9rem !important;
    }

    /* Sidebar container */
    [data-testid="stSidebar"] {
        background: #ffffff !important;
        border-right: 1px solid var(--st-border) !important;
        box-shadow: 2px 0 18px rgba(16, 24, 40, 0.06) !important;
    }

    /* Sidebar spacing */
    [data-testid="stSidebar"] .block-container {
        padding-top: 1.25rem !important;
    }

    /* Sidebar menu (safe styling) */
    [data-testid="stSidebar"] [role="radiogroup"] {
        display: flex !important;
        flex-direction: column !important;
        gap: 0.35rem !important;
    }

    /* Streamlit uses BaseWeb for radios; this is more stable than :has() */
    [data-testid="stSidebar"] label[data-baseweb="radio"] {
        width: 100% !important;
        margin: 0 !important;
        padding: 0.55rem 0.7rem !important;
        border-radius: 12px !important;
        border: 1px solid transparent !important;
        background: transparent !important;
        transition: background-color 0.12s ease, border-color 0.12s ease !important;
    }

    /* Ensure sidebar menu text is always visible */
    [data-testid="stSidebar"] label[data-baseweb="radio"] p {
        color: var(--st-text) !important;
        margin: 0 !important;
    }

    [data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
        background: var(--st-hover) !important;
        border-color: rgba(0, 208, 132, 0.35) !important;
    }

    /* Highlight selected option (works without :has) */
    [data-testid="stSidebar"] label[data-baseweb="radio"] input:checked + div {
        background: rgba(0, 208, 132, 0.12) !important;
        border-radius: 10px !important;
        padding: 0.1rem 0.35rem !important;
    }

    [data-testid="stSidebar"] label[data-baseweb="radio"] input:checked + div p {
        color: var(--st-navy) !important;
        font-weight: 700 !important;
    }

    /* Make buttons less "playful" */
    .stButton>button {
        background: var(--st-brand) !important;
        color: #072A40 !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.10) !important;
    }

    .stButton>button:hover {
        background: #00b874 !important;
        transform: none !important;
        box-shadow: 0 2px 6px rgba(16, 24, 40, 0.16) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE SETUP ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

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
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty TEXT, description TEXT, gl_code TEXT,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS gl_codes (
        code TEXT PRIMARY KEY, description TEXT
    )''')
    
    # Create indices for common queries
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_doc_date ON journal(doc_date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_counterparty ON journal(counterparty)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_doc_type ON journal(doc_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_bank_account ON journal(bank_account)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_status ON journal(status)")
    except:
        pass

    # Normalize legacy mixed-type values (SQLite can store any type in any column)
    try:
        c.execute("UPDATE journal SET doc_type = '' WHERE doc_type IS NULL")
        mixed_doc_type = c.execute(
            "SELECT count(*) FROM journal WHERE doc_type IS NOT NULL AND typeof(doc_type) != 'text'"
        ).fetchone()[0]
        if mixed_doc_type and mixed_doc_type > 0:
            c.execute(
                "UPDATE journal SET doc_type = CAST(doc_type AS TEXT) WHERE doc_type IS NOT NULL AND typeof(doc_type) != 'text'"
            )
    except:
        pass
    
    try:
        if c.execute("SELECT count(*) FROM gl_codes").fetchone()[0] == 0:
            defaults = [("100", "Πωλήσεις"), ("200", "Αγορές"), ("300", "Ταμείο"), ("400", "Τράπεζες"), ("600", "Γενικά Έξοδα")]
            c.executemany("INSERT INTO gl_codes VALUES (?,?)", defaults)
            conn.commit()
    except: pass
    conn.commit(); conn.close()

init_db()

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

# --- 4.5 INPUT VALIDATION ---
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
conn = get_conn()
try: count = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
except: count = 0
conn.close()

if count == 0:
    st.title("⚠️ Εγκατάσταση")
    st.info("Η βάση είναι κενή.")
    c1, c2 = st.columns(2)
    up = c1.file_uploader("Upload Excel", type=['xlsx'])
    if up:
        try:
            xl = pd.ExcelFile(up, engine='openpyxl')
            sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(up, sheet_name=sheet)
            df.columns = df.columns.str.strip()
            rename_map = {'Date':'DocDate', 'Net':'Amount (Net)', 'Gross':'Amount (Gross)', 'Type':'DocType', 'Counterparty':'counterparty', 'Bank Account':'bank_account'}
            df.rename(columns=rename_map, inplace=True)
            conn = get_conn()
            for _, r in df.iterrows():
                parsed_date = pd.to_datetime(r.get('DocDate'), errors='coerce')
                d_date = parsed_date.strftime('%Y-%m-%d') if pd.notna(parsed_date) else date.today().strftime('%Y-%m-%d')
                conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (d_date, str(r.get('DocNo','')), str(r.get('DocType','')), str(r.get('counterparty','')), str(r.get('Description','')), "999", float(r.get('Amount (Net)',0)), float(r.get('VAT Amount',0)), float(r.get('Amount (Gross)',0)), str(r.get('Payment Method','')), str(r.get('bank_account','')), str(r.get('Status',''))))
            conn.commit(); conn.close(); st.success("✅ OK! Refresh."); st.stop()
        except: st.error("Error loading Excel")
    
    if c2.button("🚀 Start Fresh (Blank DB)"):
        conn = get_conn(); conn.execute("INSERT INTO journal (description) VALUES ('init')"); conn.execute("DELETE FROM journal"); conn.commit(); conn.close(); st.rerun()
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
st.sidebar.caption(f"Συνδεδεμένος χρήστης: {st.session_state.username}")
st.sidebar.divider()

menu = st.sidebar.radio("ΜΕΝΟΥ", [
    "📊 Dashboard",
    "📝 Νέα Εγγραφή",
    "📊 ΦΠΑ & Φόροι (Report)",
    "📇 Καρτέλες (Ledgers)",
    "📚 Αρχείο & Διορθώσεις",
    "💵 Ταμείο & Τράπεζες",
    "⚙️ Ρυθμίσεις GL"
])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Γενική Εικόνα")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()
    
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
    fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group')
    
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
    
    st.plotly_chart(fig, use_container_width=True)
    
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
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)

# --- NEW ENTRY ---
elif menu == "📝 Νέα Εγγραφή":
    st.title("📝 Νέα Εγγραφή - Συναλλαγές Λογιστηρίου")
    
    conn = get_conn()
    gl_df = pd.read_sql("SELECT code, description FROM gl_codes ORDER BY code", conn)
    conn.close()
    gl_list = gl_df.apply(lambda x: f"{x['code']} - {x['description']}", axis=1).tolist()
    
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
        
        # Transaction-specific fields
        if trans_type == "💰 Εισπράξεις (Πωλήσεις)":
            st.subheader("📊 Στοιχεία Εισπράξης")
            partner = st.text_input("Πελάτης", "")
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
            bank = p2.text_input("Λογαριασμός", "Alpha" if pay=="Τράπεζα" else "Ταμείο" if pay=="Μετρητά" else "")
            d_type = "Income"
        
        elif trans_type == "💸 Πληρωμές (Έξοδα)":
            st.subheader("📊 Στοιχεία Πληρωμής")
            partner = st.text_input("Προμηθευτής / Δαπάνη", "")
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
            bank = p2.text_input("Λογαριασμός", "Alpha" if pay=="Τράπεζα" else "Ταμείο" if pay=="Μετρητά" else "")
            d_type = "Expense"
        
        elif trans_type == "📄 Τιμολόγια Αγορών":
            st.subheader("📊 Στοιχεία Τιμολογίου Αγοράς")
            partner = st.text_input("Προμηθευτής", "")
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
            bank = p2.text_input("Λογαριασμός", "")
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
        
        else:  # Άλλη Συναλλαγή
            st.subheader("📊 Στοιχεία Συναλλαγής")
            partner = st.text_input("Συναλλασσόμενος", "")
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
            bank = st.text_input("Λογαριασμός", "")
            vat = st.session_state.calc_vat_val
            gross = st.session_state.calc_gross
            d_type = pay
        
        st.divider()
        if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ", type="primary", use_container_width=True):
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
                    
                    status = "Unpaid" if pay in ["Επί Πιστώσει"] else "Paid"
                    gl_val = gl_choice.split(" - ")[0] if gl_choice else "999"
                    doc_date_iso = d_date.strftime('%Y-%m-%d') if hasattr(d_date, 'strftime') else str(d_date)
                    
                    conn = get_conn()
                    conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                (doc_date_iso, d_no, d_type, partner, descr, gl_val, net_amount, vat_amount, gross_amount, pay, bank, status))
                    conn.commit()
                    conn.close()
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
elif menu == "📊 ΦΠΑ & Φόροι (Report)":
    st.title("📊 Αναλυτική Έκθεση ΦΠΑ & Φόρων")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()
    
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
        st.dataframe(vat_summary, use_container_width=True)
    
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
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Download as CSV
        csv = df_display.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Λήψη Έκθεσης (CSV)",
            data=csv,
            file_name=f"fpa_foroi_{period_label}.csv",
            mime="text/csv"
        )

# --- LEDGERS ---
elif menu == "📇 Καρτέλες (Ledgers)":
    st.title("📇 Καρτέλες Συναλλασσομένων")
    
    conn = get_conn()
    partners = pd.read_sql("SELECT DISTINCT counterparty FROM journal WHERE counterparty IS NOT NULL AND counterparty != ''", conn)['counterparty'].tolist()
    partners.sort()
    conn.close()
    
    if not partners:
        st.warning("⚠️ Δεν υπάρχουν καταχωρημένοι συναλλασσόμενοι")
        st.stop()
    
    # Επιλογή συναλλασσόμενου
    st.subheader("🔍 Φίλτρα")
    sel = st.selectbox("Επιλογή Συναλλασσόμενου", partners, help="Επιλέξτε τον συναλλασσόμενο για να δείτε τις συναλλαγές του")
    
    if sel:
        conn = get_conn()
        df = pd.read_sql("SELECT * FROM journal WHERE counterparty=? ORDER BY doc_date DESC", conn, params=(sel,))
        conn.close()
        
        # Convert date and clean data
        df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
        df = clean_dataframe(df)
        
        # Date filters
        col1, col2, col3 = st.columns(3)
        with col1:
            min_date = df['doc_date'].min()
            start_date = st.date_input("Από", value=min_date, help="Ημερομηνία έναρξης")
        
        with col2:
            max_date = df['doc_date'].max()
            end_date = st.date_input("Ως", value=max_date, help="Ημερομηνία λήξης")
        
        with col3:
            doc_type_filter = st.multiselect("Τύπος Συναλλαγής", 
                                            ["Income", "Expense", "Bill", "Transfer"], 
                                            default=["Income", "Expense", "Bill"],
                                            help="Επιλέξτε τύπους συναλλαγών προς εμφάνιση")
        
        # Apply date filter
        mask = (df['doc_date'].dt.date >= start_date) & (df['doc_date'].dt.date <= end_date)
        if doc_type_filter:
            mask = mask & (df['doc_type'].isin(doc_type_filter))
        
        df_filtered = df[mask].copy()
        
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
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
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
            
            st.dataframe(summary_display, use_container_width=True)
            
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
elif menu == "📚 Αρχείο & Διορθώσεις":
    st.title("📚 Αρχείο & Διορθώσεις")
    
    conn = get_conn()
    df = pd.read_sql("SELECT rowid as id, * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("📭 Δεν υπάρχουν καταχωρήσεις στο αρχείο")
        st.stop()
    
    # Cleaning and conversion
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    df = clean_dataframe(df)
    df['id'] = df['id'].astype(int)  # ΣΗΜΑΝΤΙΚΟ: Μετατροπή id σε int
    
    st.subheader("📋 Όλες οι Εγγραφές")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        sort_by = st.selectbox("Ταξινόμηση", 
                              ["Πιο Πρόσφατες", "Πιο Παλιές", "Μεγαλύτερα Ποσά"],
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
    if search_term:
        mask = mask & (
            (df['counterparty'].str.contains(search_term, case=False, na=False)) |
            (df['description'].str.contains(search_term, case=False, na=False))
        )
    
    df_filtered = df[mask].copy()
    
    # Apply sorting
    if sort_by == "Πιο Πρόσφατες":
        df_filtered = df_filtered.sort_values('doc_date', ascending=False)
    elif sort_by == "Πιο Παλιές":
        df_filtered = df_filtered.sort_values('doc_date', ascending=True)
    else:
        df_filtered = df_filtered.sort_values('amount_gross', ascending=False)
    
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
                        if st.button("✏️ Επεξεργασία", key=f"list_edit_{rid}", use_container_width=True):
                            st.session_state[f"edit_mode_{rid}"] = True
                            st.rerun()
                    with col_del:
                        if st.button("🗑️ Διαγραφή", key=f"list_del_{rid}", use_container_width=True):
                            conn = get_conn()
                            conn.execute("DELETE FROM journal WHERE rowid=?", (rid,))
                            conn.commit()
                            conn.close()
                            st.success("Διαγράφηκε!")
                            time.sleep(0.3)
                            st.rerun()
                    with col_id:
                        st.caption(f"#{rid}")
        
        else:
            # ΛΕΠΤΟΜΕΡΕΙΕΣ
            for row in df_filtered.itertuples(index=False):
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
                    
                    new_vat = round(new_net * (new_vat_rate / 100), 2)
                    new_gross = round(new_net + new_vat, 2)
                    st.info(f"ΦΠΑ: €{new_vat:,.2f} | Σύνολο: €{new_gross:,.2f}")
                    
                    st.divider()
                    
                    col_upd, col_del = st.columns(2)
                    with col_upd:
                        if st.button("Ενημέρωση", key=f"det_upd_{rid}", use_container_width=True, type="primary"):
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
                                    conn = get_conn()
                                    conn.execute("""UPDATE journal SET doc_date=?, doc_no=?, doc_type=?, counterparty=?, 
                                                  description=?, amount_net=?, vat_amount=?, amount_gross=?, 
                                                  payment_method=?, status=? WHERE rowid=?""",
                                               (new_date, new_docno, new_type, new_partner, new_descr,
                                                new_net, new_vat, new_gross, new_pay, new_stat, rid))
                                    conn.commit()
                                    conn.close()
                                    st.success("✓ Ενημερώθηκε!")
                                    time.sleep(0.3)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Σφάλμα κατά την ενημέρωση: {str(e)}")
                    with col_del:
                        if st.button("Διαγραφή", key=f"det_del_{rid}", use_container_width=True, type="secondary"):
                            try:
                                conn = get_conn()
                                conn.execute("DELETE FROM journal WHERE rowid=?", (rid,))
                                conn.commit()
                                conn.close()
                                st.error("✗ Διαγράφηκε!")
                                time.sleep(0.3)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Σφάλμα κατά τη διαγραφή: {str(e)}")

# --- TREASURY ---
elif menu == "💵 Ταμείο & Τράπεζες":
    st.title("💵 Διαχείριση Διαθεσίμων")
    
    conn = get_conn()
    df_all = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()
    
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
        st.dataframe(acc_df_display, use_container_width=True, hide_index=True)
    
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
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
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
        
        st.plotly_chart(fig, use_container_width=True)
        
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
elif menu == "⚙️ Ρυθμίσεις GL":
    st.title("⚙️ Διαχείριση Ρυθμίσεων")
    
    conn = get_conn()
    
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
        df_gl = pd.read_sql("SELECT * FROM gl_codes ORDER BY code", conn)
        df_gl['code'] = df_gl['code'].astype(str)
        
        # Show current GL codes
        st.write(f"**Σύνολο GL Codes:** {len(df_gl)}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Υπάρχουσες Ρυθμίσεις:**")
            edited_gl = st.data_editor(df_gl, num_rows="dynamic", use_container_width=True, key="gl_editor")
            
            if st.button("💾 Αποθήκευση GL Codes", use_container_width=True, type="primary"):
                try:
                    conn.execute("DELETE FROM gl_codes")
                    for _, row in edited_gl.iterrows():
                        conn.execute("INSERT INTO gl_codes VALUES (?,?)", (row['code'], row['description']))
                    conn.commit()
                    st.success("✓ GL Codes αποθηκεύτηκαν!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Σφάλμα: {str(e)}")
        
        with col2:
            st.write("**Προσθήκη Νέου:**")
            new_code = st.text_input("Κωδικός", placeholder="π.χ. 500")
            new_desc = st.text_input("Περιγραφή", placeholder="π.χ. Πωλήσεις Υπηρεσιών")
            
            if st.button("➕ Προσθήκη GL", use_container_width=True):
                if new_code and new_desc:
                    try:
                        conn.execute("INSERT INTO gl_codes VALUES (?,?)", (new_code, new_desc))
                        conn.commit()
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
        
        # Get unique customers from journal
        df_journal = pd.read_sql("SELECT DISTINCT counterparty FROM journal WHERE doc_type IN ('Income', 'Cash Deposit') AND counterparty != ''", conn)
        customers = sorted(df_journal['counterparty'].unique().tolist()) if not df_journal.empty else []
        
        st.write(f"**Σύνολο Πελατών:** {len(customers)}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Υπάρχοντες Πελάτες:**")
            if customers:
                customers_df = pd.DataFrame({'Όνομα Πελάτη': customers})
                st.dataframe(customers_df, use_container_width=True, hide_index=True)
            else:
                st.info("Δεν υπάρχουν εγγεγραμμένοι πελάτες ακόμα")
        
        with col2:
            st.write("**Προσθήκη Νέου Πελάτη:**")
            customer_name = st.text_input("Όνομα Πελάτη", placeholder="π.χ. ΑΒΓ ΑΕ")
            
            if st.button("➕ Προσθήκη Πελάτη", use_container_width=True):
                if customer_name:
                    try:
                        # Add a test entry to register the customer
                        conn.execute(
                            "INSERT INTO journal (doc_date, counterparty, description, amount_net, amount_gross, status) VALUES (?, ?, ?, ?, ?, ?)",
                            (datetime.now().strftime('%Y-%m-%d'), customer_name, "(αρχικοποίηση)", 0.0, 0.0, "Paid")
                        )
                        conn.commit()
                        st.success(f"✓ Πελάτης '{customer_name}' προστέθηκε!")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Σφάλμα: {str(e)}")
                else:
                    st.warning("Εισάγετε όνομα πελάτη")
    
    # --- TAB 3: SUPPLIERS ---
    with tab_suppliers:
        st.subheader("🏭 Διαχείριση Προμηθευτών")
        
        # Get unique suppliers from journal
        df_journal = pd.read_sql("SELECT DISTINCT counterparty FROM journal WHERE doc_type IN ('Expense', 'Bill') AND counterparty != ''", conn)
        suppliers = sorted(df_journal['counterparty'].unique().tolist()) if not df_journal.empty else []
        
        st.write(f"**Σύνολο Προμηθευτών:** {len(suppliers)}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Υπάρχοντες Προμηθευτές:**")
            if suppliers:
                suppliers_df = pd.DataFrame({'Όνομα Προμηθευτή': suppliers})
                st.dataframe(suppliers_df, use_container_width=True, hide_index=True)
            else:
                st.info("Δεν υπάρχουν εγγεγραμμένοι προμηθευτές ακόμα")
        
        with col2:
            st.write("**Προσθήκη Νέου Προμηθευτή:**")
            supplier_name = st.text_input("Όνομα Προμηθευτή", placeholder="π.χ. ΔΕΖ ΑΕ")
            
            if st.button("➕ Προσθήκη Προμηθευτή", use_container_width=True):
                if supplier_name:
                    try:
                        # Add a test entry to register the supplier
                        conn.execute(
                            "INSERT INTO journal (doc_date, counterparty, description, amount_net, amount_gross, status) VALUES (?, ?, ?, ?, ?, ?)",
                            (datetime.now().strftime('%Y-%m-%d'), supplier_name, "(αρχικοποίηση)", 0.0, 0.0, "Paid")
                        )
                        conn.commit()
                        st.success(f"✓ Προμηθευτής '{supplier_name}' προστέθηκε!")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Σφάλμα: {str(e)}")
                else:
                    st.warning("Εισάγετε όνομα προμηθευτή")
    
    # --- TAB 4: BANK ACCOUNTS ---
    with tab_banks:
        st.subheader("🏦 Διαχείριση Τραπεζικών Λογαριασμών")
        
        # Get unique bank accounts
        df_journal = pd.read_sql("SELECT DISTINCT bank_account FROM journal WHERE bank_account != '' AND bank_account IS NOT NULL", conn)
        accounts = sorted(df_journal['bank_account'].unique().tolist()) if not df_journal.empty else []
        
        st.write(f"**Σύνολο Λογαριασμών:** {len(accounts)}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Υπάρχοντες Λογαριασμοί:**")
            if accounts:
                accounts_df = pd.DataFrame({'Λογαριασμός': accounts})
                st.dataframe(accounts_df, use_container_width=True, hide_index=True)
            else:
                st.info("Δεν υπάρχουν εγγεγραμμένοι λογαριασμοί ακόμα")
        
        with col2:
            st.write("**Άνοιγμα Νέου Λογαριασμού:**")
            
            account_type = st.selectbox("Τύπος Λογαριασμού", ["Τράπεζα", "Ταμείο"])
            account_name = st.text_input("Όνομα Λογαριασμού", placeholder="π.χ. Alpha Bank EUR")
            
            if st.button("➕ Άνοιγμα Λογαριασμού", use_container_width=True):
                if account_name:
                    full_account = f"{account_type} - {account_name}"
                    try:
                        # Add initial entry
                        conn.execute(
                            "INSERT INTO journal (doc_date, bank_account, description, amount_net, amount_gross, status) VALUES (?, ?, ?, ?, ?, ?)",
                            (datetime.now().strftime('%Y-%m-%d'), full_account, "(άνοιγμα λογαριασμού)", 0.0, 0.0, "Paid")
                        )
                        conn.commit()
                        st.success(f"✓ Λογαριασμός '{full_account}' δημιουργήθηκε!")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Σφάλμα: {str(e)}")
                else:
                    st.warning("Εισάγετε όνομα λογαριασμού")
    
    # --- TAB 5: SYSTEM ---
    with tab_system:
        st.subheader("⚙️ Ρυθμίσεις Συστήματος")
        
        st.write("**Πληροφορίες Βάσης Δεδομένων:**")
        
        # Get database statistics
        df_all = pd.read_sql("SELECT COUNT(*) as count FROM journal", conn)
        total_records = df_all['count'].iloc[0]
        
        df_gl_count = pd.read_sql("SELECT COUNT(*) as count FROM gl_codes", conn)
        gl_count = df_gl_count['count'].iloc[0]
        
        stat1, stat2 = st.columns(2)
        stat1.metric("📝 Σύνολο Εγγραφών", f"{total_records}")
        stat2.metric("📚 GL Codes", f"{gl_count}")
        
        st.divider()
        
        st.write("**Δράσεις Διαχείρισης:**")
        
        # Database reset
        st.warning("⚠️ **Επικίνδυνες Λειτουργίες** (χρησιμοποιήστε με προσοχή)")
        
        if st.button("🗑️ Διαγραφή ΌΛΩΝ των δεδομένων (Reset DB)", use_container_width=True, type="secondary"):
            if st.button("✓ Επιβεβαίωση: Διαγραφή όλων", use_container_width=True):
                try:
                    if os.path.exists(DB_FILE):
                        os.remove(DB_FILE)
                    st.error("✗ Βάση δεδομένων διαγράφηκε πλήρως!")
                    st.info("Η εφαρμογή θα ξαναδημιουργήσει τη βάση κατά το επόμενο restart.")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Σφάλμα: {str(e)}")
        
        st.divider()
        st.write("**Πληροφορίες Συστήματος:**")
        st.code(f"""
Αρχείο Βάσης: {DB_FILE}
Τύπος Βάσης: SQLite3
Σύνολο Εγγραφών: {total_records}
GL Codes: {gl_count}
Τελευταία Ενημέρωση: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        """)
    
    conn.close()
