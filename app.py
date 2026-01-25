import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, date

# --- 1. CONFIG & THEME ---
st.set_page_config(page_title="SalesTree ERP Platinum", layout="wide", page_icon="💎")
DB_FILE = "erp_platinum.db"

# --- 2. PREMIUM CSS STYLING ---
st.markdown("""
<style>
    /* Γενικό Layout */
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1e293b; /* Dark Slate */
        border-right: 1px solid #334155;
    }
    [data-testid="stSidebar"] * { color: #f8fafc !important; } /* White text */
    
    /* Metrics / Cards - ΤΟ ΩΡΑΙΟ DESIGN */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border-left: 5px solid #3b82f6; /* Default Blue */
        transition: transform 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    /* Labels & Values */
    div[data-testid="metric-container"] label { color: #64748b !important; font-size: 0.9rem; font-weight: 600; }
    div[data-testid="metric-container"] div { color: #0f172a !important; font-size: 1.8rem; font-weight: 800; }

    /* Buttons */
    .stButton>button {
        background-color: #2563eb !important;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
    }
    .stButton>button:hover { background-color: #1d4ed8 !important; }

    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox div, .stDateInput input {
        border-radius: 6px; border: 1px solid #cbd5e1;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #e2e8f0; border-radius: 6px; color: #475569; font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important; color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE & INIT ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # Πίνακας Κινήσεων
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty TEXT, description TEXT, gl_code TEXT,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT
    )''')
    
    # Πίνακας Λογιστικού Σχεδίου (GL)
    c.execute('''CREATE TABLE IF NOT EXISTS gl_codes (
        code TEXT PRIMARY KEY,
        description TEXT
    )''')
    
    # Default GL Codes
    try:
        if c.execute("SELECT count(*) FROM gl_codes").fetchone()[0] == 0:
            defaults = [
                ("100", "Πωλήσεις (Έσοδα)"), ("200", "Αγορές (Έξοδα)"), 
                ("300", "Ταμείο"), ("400", "Τράπεζες"), 
                ("600", "Λειτουργικά Έξοδα"), ("610", "Ενοίκια")
            ]
            c.executemany("INSERT INTO gl_codes VALUES (?,?)", defaults)
            conn.commit()
    except: pass
    
    conn.commit()
    conn.close()

init_db()

# --- 4. CALCULATOR STATE ---
if 'c_net' not in st.session_state: st.session_state.c_net = 0.0
if 'c_vat_rate' not in st.session_state: st.session_state.c_vat_rate = 24
if 'c_vat_val' not in st.session_state: st.session_state.c_vat_val = 0.0
if 'c_gross' not in st.session_state: st.session_state.c_gross = 0.0

def update_calc():
    """Real-time υπολογισμός"""
    try:
        n = float(st.session_state.c_net)
        r = float(st.session_state.c_vat_rate)
        v = n * (r / 100.0)
        g = n + v
        st.session_state.c_vat_val = round(v, 2)
        st.session_state.c_gross = round(g, 2)
    except: pass

# --- 5. INITIAL DATA CHECK ---
conn = get_conn()
try:
    count = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
except: count = 0
conn.close()

if count == 0:
    st.title("👋 Καλώς ήρθατε στο SalesTree Platinum")
    st.info("Η βάση είναι κενή. Ξεκινήστε ανεβάζοντας το Excel.")
    up = st.file_uploader("Upload Excel", type=['xlsx'])
    
    c1, c2 = st.columns(2)
    if c1.button("🚀 Δημιουργία Κενής Βάσης (Start Fresh)"):
        conn = get_conn()
        conn.execute("INSERT INTO journal (description) VALUES ('init')"); conn.execute("DELETE FROM journal"); conn.commit(); conn.close()
        st.rerun()
        
    if up:
        try:
            xl = pd.ExcelFile(up, engine='openpyxl')
            sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(up, sheet_name=sheet)
            df.columns = df.columns.str.strip()
            rename_map = {
                'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 'Net': 'Amount (Net)', 
                'Gross': 'Amount (Gross)', 'Type': 'DocType', 
                'Counterparty': 'counterparty', 'Bank Account': 'bank_account'
            }
            df.rename(columns=rename_map, inplace=True)
            
            conn = get_conn()
            for _, r in df.iterrows():
                d_date = pd.to_datetime(r.get('DocDate'), errors='coerce').strftime('%Y-%m-%d')
                conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (d_date, str(r.get('DocNo','')), str(r.get('DocType','')), str(r.get('counterparty','')), str(r.get('Description','')), "999", 
                             float(r.get('Amount (Net)',0)), float(r.get('VAT Amount',0)), float(r.get('Amount (Gross)',0)),
                             str(r.get('Payment Method','')), str(r.get('bank_account','')), str(r.get('Status',''))))
            conn.commit(); conn.close()
            st.success("✅ Δεδομένα Φορτώθηκαν!"); st.rerun()
        except Exception as e: st.error(f"Error: {e}")
    st.stop()

# --- 6. AUTH ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.title("🔐 Login")
        u = st.text_input("User"); p = st.text_input("Pass", type="password")
        if st.button("Είσοδος"):
            if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"):
                st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
    st.stop()

# --- 7. SIDEBAR ---
st.sidebar.title("💎 SalesTree")
st.sidebar.write(f"User: **{st.session_state.username}**")
st.sidebar.divider()

menu = st.sidebar.radio("MAIN MENU", [
    "📊 Dashboard",
    "📝 Νέα Εγγραφή",
    "📇 Καρτέλες (Ledgers)",
    "📚 Αρχείο & Διορθώσεις",
    "💵 Ταμείο & Τράπεζες",
    "⚙️ Ρυθμίσεις GL"
])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Γενική Εικόνα (Executive)")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()
    
    # Safe cleaning
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    cy = datetime.now().year
    df_y = df[df['doc_date'].dt.year == cy]
    
    inc = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
    exp = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
    prof = inc - exp
    
    # COLORED CARDS via CSS injection above
    c1, c2, c3 = st.columns(3)
    c1.metric("Πωλήσεις (Έσοδα)", f"€{inc:,.0f}", delta="▲ YTD", delta_color="normal")
    c2.metric("Έξοδα & Αγορές", f"€{exp:,.0f}", delta="▼ YTD", delta_color="inverse")
    c3.metric("Καθαρό Κέρδος", f"€{prof:,.0f}")
    
    st.divider()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📈 Μηνιαία Πορεία")
        monthly = df_y.copy()
        monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
        grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
        # Custom Colors for Chart
        fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group',
                     color_discrete_map={'Income':'#10b981', 'Expense':'#ef4444', 'Bill':'#f97316'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("💰 Κατανομή Εξόδων")
        exp_df = df_y[df_y['doc_type'].isin(['Expense','Bill'])]
        if not exp_df.empty:
            fig2 = px.pie(exp_df, values='amount_net', names='gl_code', hole=0.5)
            st.plotly_chart(fig2, use_container_width=True)

# --- NEW ENTRY ---
elif menu == "📝 Νέα Εγγραφή":
    st.title("📝 Νέα Εγγραφή Συναλλαγής")
    
    conn = get_conn()
    gl_df = pd.read_sql("SELECT code, description FROM gl_codes ORDER BY code", conn)
    conn.close()
    gl_list = gl_df.apply(lambda x: f"{x['code']} - {x['description']}", axis=1).tolist()

    with st.container():
        # Header inputs
        c1, c2, c3 = st.columns(3)
        d_date = c1.date_input("Ημερομηνία", date.today())
        d_type = c2.selectbox("Τύπος", ["Income", "Expense", "Bill"])
        d_no = c3.text_input("Αρ. Παρ/κου")
        
        c4, c5 = st.columns(2)
        partner = c4.text_input("Συναλλασσόμενος")
        gl_choice = c5.selectbox("Λογιστικός Κωδικός", gl_list if gl_list else ["999 - General"])
        descr = st.text_input("Αιτιολογία / Περιγραφή")

        st.divider()
        st.subheader("💶 Οικονομικά Στοιχεία (Calculator)")
        
        k1, k2, k3, k4 = st.columns(4)
        # AUTO-CALC VIA KEY & ON_CHANGE
        k1.number_input("Καθαρή Αξία (€)", step=10.0, key='c_net', on_change=update_calc)
        k2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key='c_vat_rate', on_change=update_calc)
        
        # Read-only results (updated from state)
        vat = k3.number_input("ΦΠΑ (€)", value=st.session_state.c_vat_val, key='disp_v', disabled=True)
        gross = k4.number_input("Σύνολο (€)", value=st.session_state.c_gross, key='disp_g', disabled=True)
        
        st.divider()
        p1, p2 = st.columns(2)
        pay = p1.selectbox("Τρόπος Πληρωμής", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
        bank = p2.text_input("Λογαριασμός", "Alpha" if pay=="Τράπεζα" else "Ταμείο" if pay=="Μετρητά" else "")
        
        if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ", type="primary"):
            status = "Unpaid" if pay == "Επί Πιστώσει" else "Paid"
            gl_val = gl_choice.split(" - ")[0] if gl_choice else "999"
            
            conn = get_conn()
            conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (d_date, d_no, d_type, partner, descr, gl_val, st.session_state.c_net, vat, gross, pay, bank, status))
            conn.commit()
            conn.close()
            st.success("✅ Επιτυχής Καταχώρηση!")
            st.session_state.c_net = 0.0 # Reset
            st.rerun()

# --- LEDGERS ---
elif menu == "📇 Καρτέλες (Ledgers)":
    st.title("📇 Καρτέλες Πελατών/Προμηθευτών")
    conn = get_conn()
    partners = pd.read_sql("SELECT DISTINCT counterparty FROM journal WHERE counterparty IS NOT NULL AND counterparty != ''", conn)['counterparty'].tolist()
    
    sel = st.selectbox("Επιλογή Συναλλασσόμενου", partners)
    if sel:
        df = pd.read_sql(f"SELECT * FROM journal WHERE counterparty='{sel}' ORDER BY doc_date DESC", conn)
        
        # Balance Calculation
        balance = df[df['status']=='Unpaid']['amount_gross'].sum()
        
        c1, c2 = st.columns([1, 3])
        c1.metric(f"Υπόλοιπο {sel}", f"€{balance:,.2f}")
        c2.dataframe(df, use_container_width=True)
    conn.close()

# --- ARCHIVE (FIXED TYPES) ---
elif menu == "📚 Αρχείο & Διορθώσεις":
    st.title("📚 Αρχείο Κινήσεων")
    st.info("💡 **Tip:** Για διαγραφή, τσεκάρετε το κουτί αριστερά της γραμμής -> Delete -> Αποθήκευση.")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    gl_df = pd.read_sql("SELECT code FROM gl_codes", conn)
    gl_codes_list = gl_df['code'].tolist()
    conn.close()
    
    # CRITICAL FIX: Ensure types are correct before Editor
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    df['amount_net'] = pd.to_numeric(df['amount_net'], errors='coerce').fillna(0.0)
    df['amount_gross'] = pd.to_numeric(df['amount_gross'], errors='coerce').fillna(0.0)
    df['gl_code'] = df['gl_code'].astype(str)
    
    edited = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "doc_date": st.column_config.DateColumn("Ημερομηνία"),
            "amount_net": st.column_config.NumberColumn("Καθαρό"),
            "amount_gross": st.column_config.NumberColumn("Μικτό"),
            "doc_type": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill"]),
            "gl_code": st.column_config.SelectboxColumn("GL", options=gl_codes_list),
            "status": st.column_config.SelectboxColumn("Status", options=["Paid", "Unpaid"])
        }
    )
    
    if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ ΑΛΛΑΓΩΝ"):
        conn = get_conn()
        conn.execute("DELETE FROM journal")
        
        # Convert date back to string for SQLite
        s_df = edited.copy()
        s_df['doc_date'] = pd.to_datetime(s_df['doc_date']).dt.strftime('%Y-%m-%d')
        
        s_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.commit()
        conn.close()
        st.success("✅ Ενημερώθηκε!")
        st.rerun()

# --- TREASURY ---
elif menu == "💵 Ταμείο & Τράπεζες":
    st.title("💵 Διαχείριση Διαθεσίμων")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal WHERE status='Paid'", conn)
    conn.close()
    
    df['amount_gross'] = pd.to_numeric(df['amount_gross']).fillna(0)
    df['flow'] = df.apply(lambda x: x['amount_gross'] if x['doc_type']=='Income' else -x['amount_gross'], axis=1)
    df['bank_account'] = df['bank_account'].fillna('Unknown').astype(str)
    
    mask = df['bank_account'].str.contains("Ταμείο|Cash", case=False)
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💶 Ταμείο")
        st.metric("Μετρητά", f"€{df[mask]['flow'].sum():,.2f}")
    with c2:
        st.subheader("🏦 Τράπεζες")
        gr = df[~mask].groupby('bank_account')['flow'].sum().reset_index()
        for i, r in gr.iterrows():
            st.info(f"**{r['bank_account']}**: €{r['flow']:,.2f}")

# --- SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις GL":
    st.title("⚙️ Ρυθμίσεις Λογιστικού Σχεδίου")
    
    conn = get_conn()
    df_gl = pd.read_sql("SELECT * FROM gl_codes ORDER BY code", conn)
    
    # Ensure string type for editing
    df_gl['code'] = df_gl['code'].astype(str)
    
    st.write("Προσθήκη / Επεξεργασία Κωδικών:")
    edited_gl = st.data_editor(df_gl, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Ενημέρωση GL"):
        conn.execute("DELETE FROM gl_codes")
        edited_gl.to_sql('gl_codes', conn, if_exists='append', index=False)
        conn.commit()
        st.success("Saved!")
        st.rerun()
    conn.close()
