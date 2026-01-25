import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, date

# --- 1. CONFIG ---
st.set_page_config(page_title="SalesTree ERP Final", layout="wide", page_icon="🏢")
DB_FILE = "erp_tax_fixed.db"

# --- 2. CSS (FIX: ΜΑΥΡΑ ΓΡΑΜΜΑΤΑ ΠΑΝΤΟΥ) ---
st.markdown("""
<style>
    /* 1. ΦΟΝΤΟ ΕΦΑΡΜΟΓΗΣ - ΛΕΥΚΟ */
    .stApp {
        background-color: #ffffff !important;
    }

    /* 2. ΚΕΙΜΕΝΟ - ΑΝΑΓΚΑΣΤΙΚΑ ΜΑΥΡΟ (GIA NA MHN EINAI ASPRO SE ASPRO) */
    h1, h2, h3, h4, h5, h6, p, span, div, label, li {
        color: #000000 !important;
    }

    /* 3. SIDEBAR */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa !important;
        border-right: 1px solid #ccc !important;
    }

    /* 4. METRICS (ΤΑ ΚΟΥΤΑΚΙΑ ME TA NOYMERA) */
    div[data-testid="metric-container"] {
        background-color: #f0f2f6 !important; /* Ελαφρύ Γκρι για να ξεχωρίζει */
        border: 1px solid #000000 !important; /* Μαύρο περίγραμμα */
        padding: 10px !important;
        border-radius: 5px !important;
        box-shadow: 2px 2px 0px rgba(0,0,0,0.2) !important;
    }
    
    /* Τα γράμματα μέσα στα Metrics - ΚΑΤΑΜΑΥΡΑ */
    div[data-testid="metric-container"] label {
        color: #000000 !important;
        font-weight: bold !important;
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #000000 !important;
    }

    /* 5. INPUTS & BUTTONS */
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #000000 !important;
    }
    .stButton>button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE SETUP ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

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
    try:
        if c.execute("SELECT count(*) FROM gl_codes").fetchone()[0] == 0:
            defaults = [("100", "Πωλήσεις"), ("200", "Αγορές"), ("300", "Ταμείο"), ("400", "Τράπεζες"), ("600", "Γενικά Έξοδα")]
            c.executemany("INSERT INTO gl_codes VALUES (?,?)", defaults)
            conn.commit()
    except: pass
    conn.commit(); conn.close()

init_db()

# --- 4. CALCULATOR LOGIC ---
if 'c_net' not in st.session_state: st.session_state.c_net = 0.0
if 'c_vat_rate' not in st.session_state: st.session_state.c_vat_rate = 24
if 'c_vat_val' not in st.session_state: st.session_state.c_vat_val = 0.0
if 'c_gross' not in st.session_state: st.session_state.c_gross = 0.0

def update_calc():
    try:
        n = float(st.session_state.c_net)
        r = float(st.session_state.c_vat_rate)
        v = n * (r / 100.0)
        g = n + v
        st.session_state.c_vat_val = round(v, 2)
        st.session_state.c_gross = round(g, 2)
    except: pass

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
                d_date = pd.to_datetime(r.get('DocDate'), errors='coerce').strftime('%Y-%m-%d')
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
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.write(f"User: **{st.session_state.username}**")
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
    monthly = df_y.copy()
    monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
    grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
    fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group')
    st.plotly_chart(fig, use_container_width=True)

# --- NEW ENTRY ---
elif menu == "📝 Νέα Εγγραφή":
    st.title("📝 Νέα Εγγραφή")
    conn = get_conn()
    gl_df = pd.read_sql("SELECT code, description FROM gl_codes ORDER BY code", conn)
    conn.close()
    gl_list = gl_df.apply(lambda x: f"{x['code']} - {x['description']}", axis=1).tolist()

    with st.container():
        c1, c2, c3 = st.columns(3)
        d_date = c1.date_input("Ημερομηνία", date.today())
        d_type = c2.selectbox("Τύπος", ["Income", "Expense", "Bill"])
        d_no = c3.text_input("Αρ. Παρ/κου")
        
        c4, c5 = st.columns(2)
        partner = c4.text_input("Συναλλασσόμενος")
        gl_choice = c5.selectbox("Λογαριασμός (GL)", gl_list if gl_list else ["999"])
        descr = st.text_input("Αιτιολογία")

        st.divider()
        st.subheader("💶 Υπολογισμός (Enter στο ποσό για update)")
        
        k1, k2, k3, k4 = st.columns(4)
        k1.number_input("Καθαρό (€)", step=10.0, key='c_net', on_change=update_calc)
        k2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key='c_vat_rate', on_change=update_calc)
        vat = k3.number_input("ΦΠΑ (€)", value=st.session_state.c_vat_val, disabled=True, key='v_disp')
        gross = k4.number_input("Σύνολο (€)", value=st.session_state.c_gross, disabled=True, key='g_disp')
        
        st.divider()
        p1, p2 = st.columns(2)
        pay = p1.selectbox("Πληρωμή", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
        bank = p2.text_input("Λογαριασμός", "Alpha" if pay=="Τράπεζα" else "Ταμείο" if pay=="Μετρητά" else "")
        
        if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ", type="primary"):
            status = "Unpaid" if pay == "Επί Πιστώσει" else "Paid"
            gl_val = gl_choice.split(" - ")[0] if gl_choice else "999"
            conn = get_conn()
            conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (d_date, d_no, d_type, partner, descr, gl_val, st.session_state.c_net, vat, gross, pay, bank, status))
            conn.commit(); conn.close()
            st.success("✅ Καταχωρήθηκε!")
            st.session_state.c_net = 0.0; st.rerun()

# --- VAT & TAX REPORT (NEW MODULE) ---
elif menu == "📊 ΦΠΑ & Φόροι (Report)":
    st.title("📊 Αναφορές ΦΠΑ & Φόρου Εισοδήματος")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()
    
    # 1. Φίλτρα Χρόνου
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    
    col_yr, col_mo = st.columns(2)
    sel_year = col_yr.number_input("Επιλογή Έτους", min_value=2000, max_value=2100, value=datetime.now().year)
    sel_month = col_mo.selectbox("Επιλογή Μήνα", range(1, 13), index=datetime.now().month - 1)
    
    # Filter Data
    mask = (df['doc_date'].dt.year == sel_year) & (df['doc_date'].dt.month == sel_month)
    df_filtered = df[mask]
    
    if df_filtered.empty:
        st.warning(f"Δεν βρέθηκαν κινήσεις για {sel_month}/{sel_year}.")
    else:
        # --- A. ΥΠΟΛΟΓΙΣΜΟΣ ΦΠΑ ---
        st.header("1. Περιοδική ΦΠΑ")
        
        vat_collected = df_filtered[df_filtered['doc_type'] == 'Income']['vat_amount'].sum()
        vat_paid = df_filtered[df_filtered['doc_type'].isin(['Expense', 'Bill'])]['vat_amount'].sum()
        vat_balance = vat_collected - vat_paid
        
        c1, c2, c3 = st.columns(3)
        c1.metric("ΦΠΑ Πωλήσεων (Εκροές)", f"€{vat_collected:,.2f}")
        c2.metric("ΦΠΑ Αγορών (Εισροές)", f"€{vat_paid:,.2f}")
        c3.metric("Αποτέλεσμα ΦΠΑ", f"€{vat_balance:,.2f}", delta="Πληρωμή" if vat_balance > 0 else "Επιστροφή", delta_color="inverse")
        
        # --- B. ΦΟΡΟΣ ΕΙΣΟΔΗΜΑΤΟΣ (CUSTOM RATE) ---
        st.markdown("---")
        st.header("2. Υπολογισμός Φόρου Εισοδήματος")
        
        # Calculate Net Profit
        net_inc = df_filtered[df_filtered['doc_type'] == 'Income']['amount_net'].sum()
        net_exp = df_filtered[df_filtered['doc_type'].isin(['Expense', 'Bill'])]['amount_net'].sum()
        net_profit = net_inc - net_exp
        
        # Input for Tax Rate
        st.info("👇 **Ρύθμιση Συντελεστή:** Άλλαξε το ποσοστό εδώ για να δεις τον φόρο.")
        tax_rate = st.number_input("Συντελεστής Φόρου (%)", value=24.0, step=1.0, format="%.1f")
        
        tax_amount = net_profit * (tax_rate / 100.0)
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Καθαρά Έσοδα", f"€{net_inc:,.2f}")
        k2.metric("Καθαρά Έξοδα", f"€{net_exp:,.2f}")
        k3.metric(f"Φόρος ({tax_rate}%)", f"€{tax_amount:,.2f}", delta="-Φόρος", delta_color="inverse")
        
        st.success(f"💰 **Καθαρό Κέρδος μετά από Φόρους:** €{(net_profit - tax_amount):,.2f}")

# --- LEDGERS ---
elif menu == "📇 Καρτέλες (Ledgers)":
    st.title("📇 Καρτέλες")
    conn = get_conn()
    partners = pd.read_sql("SELECT DISTINCT counterparty FROM journal WHERE counterparty IS NOT NULL AND counterparty != ''", conn)['counterparty'].tolist()
    sel = st.selectbox("Επιλογή", partners)
    if sel:
        df = pd.read_sql(f"SELECT * FROM journal WHERE counterparty='{sel}' ORDER BY doc_date DESC", conn)
        bal = df[df['status']=='Unpaid']['amount_gross'].sum()
        st.metric("Ανοιχτό Υπόλοιπο", f"€{bal:,.2f}")
        st.dataframe(df, use_container_width=True)
    conn.close()

# --- ARCHIVE ---
elif menu == "📚 Αρχείο & Διορθώσεις":
    st.title("📚 Αρχείο")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    
    # Cleaning
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    for c in ['amount_net', 'vat_amount', 'amount_gross']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    
    edited = st.data_editor(
        df, num_rows="dynamic", use_container_width=True, hide_index=True,
        column_config={"doc_date": st.column_config.DateColumn("Ημ/νία")}
    )
    
    if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ"):
        conn.execute("DELETE FROM journal")
        s_df = edited.copy()
        s_df['doc_date'] = pd.to_datetime(s_df['doc_date']).dt.strftime('%Y-%m-%d')
        s_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.commit(); conn.close()
        st.success("Updated!"); st.rerun()

# --- TREASURY ---
elif menu == "💵 Ταμείο & Τράπεζες":
    st.title("💵 Διαθέσιμα")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal WHERE status='Paid'", conn)
    conn.close()
    
    df['flow'] = df.apply(lambda x: x['amount_gross'] if x['doc_type']=='Income' else -x['amount_gross'], axis=1)
    df['bank_account'] = df['bank_account'].fillna('Unknown').astype(str)
    mask = df['bank_account'].str.contains("Ταμείο|Cash", case=False)
    
    c1, c2 = st.columns(2)
    c1.metric("💶 Ταμείο", f"€{df[mask]['flow'].sum():,.2f}")
    
    with c2:
        st.subheader("🏦 Τράπεζες")
        gr = df[~mask].groupby('bank_account')['flow'].sum().reset_index()
        for i, r in gr.iterrows(): st.info(f"**{r['bank_account']}**: €{r['flow']:,.2f}")

# --- SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις GL":
    st.title("⚙️ Ρυθμίσεις GL")
    conn = get_conn()
    df_gl = pd.read_sql("SELECT * FROM gl_codes ORDER BY code", conn)
    df_gl['code'] = df_gl['code'].astype(str)
    
    edited_gl = st.data_editor(df_gl, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Update GL"):
        conn.execute("DELETE FROM gl_codes")
        edited_gl.to_sql('gl_codes', conn, if_exists='append', index=False)
        conn.commit(); st.success("Saved!"); st.rerun()
    
    st.divider()
    if st.button("🗑️ Reset DB"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.error("Deleted.")
    conn.close()
