import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, date

# --- 1. CONFIG & GL SETUP ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")
DB_FILE = "erp_master_v2.db"

# ΛΕΞΙΚΟ ΛΟΓΑΡΙΑΣΜΩΝ (GL ACCOUNTS)
GL_ACCOUNTS = {
    4000: "Πωλήσεις / Έσοδα Υπηρεσιών",
    5000: "Κόστος Πωληθέντων (Αγορές)",
    6000: "Λειτουργικά Έξοδα (Γενικά)",
    6100: "Αμοιβές Τρίτων & Ενοίκια",
    6200: "Παροχές Τρίτων (ΔΕΗ, Τηλέφωνα)",
    6300: "Φόροι & Τέλη",
    6400: "Διάφορα Έξοδα",
    7000: "Όψεως & Καταθέσεις (Τράπεζες)",
    7010: "Ταμείο Μετρητών",
    8000: "Κεφάλαιο & Μερίσματα",
    9999: "Αταξινόμητα / Εκκρεμή"
}

# --- 2. CSS (ΚΑΘΑΡΟ & ΕΥΑΝΑΓΝΩΣΤΟ) ---
st.markdown("""
<style>
    .stApp { background-color: #ffffff; color: #000000; }
    [data-testid="stSidebar"] { background-color: #f4f4f4; border-right: 1px solid #000; }
    h1, h2, h3, h4, p, label, div, span, li, td, th { color: #000000 !important; font-family: sans-serif; }
    
    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        background-color: #fff !important; color: #000 !important; border: 1px solid #444 !important;
    }
    
    /* Buttons */
    .stButton>button {
        background-color: #000 !important; color: #fff !important; border: 2px solid #000; font-weight: bold;
    }
    .stButton>button:hover { background-color: #333 !important; }
    
    /* Cards */
    div[data-testid="metric-container"] {
        background-color: #fff; border: 2px solid #000; padding: 10px; box-shadow: 4px 4px 0px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- 3. CALCULATOR LOGIC ---
if 'c_net' not in st.session_state: st.session_state.c_net = 0.0
if 'c_vat_rate' not in st.session_state: st.session_state.c_vat_rate = 24
if 'c_vat_val' not in st.session_state: st.session_state.c_vat_val = 0.0
if 'c_gross' not in st.session_state: st.session_state.c_gross = 0.0

def auto_calc():
    """Αυτόματος Υπολογισμός ΦΠΑ"""
    net = st.session_state.c_net
    rate = st.session_state.c_vat_rate
    st.session_state.c_vat_val = round(net * (rate / 100), 2)
    st.session_state.c_gross = round(net + st.session_state.c_vat_val, 2)

# --- 4. DATABASE & MIGRATION ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty TEXT, description TEXT, category TEXT, gl_account INTEGER,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# --- AUTO IMPORT EXCEL IF EMPTY ---
conn = get_conn()
try:
    count = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
except:
    count = 0
conn.close()

if count == 0:
    st.title("⚠️ Η Βάση είναι άδεια")
    st.warning("Για να μην χάσεις τα δεδομένα σου, ανέβασε το Excel τώρα.")
    up = st.file_uploader("Upload Excel", type=['xlsx'])
    if up:
        try:
            xl = pd.ExcelFile(up, engine='openpyxl')
            sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(up, sheet_name=sheet)
            
            df.columns = df.columns.str.strip()
            rename_map = {
                'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 
                'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType',
                'Counterparty': 'counterparty', 'Bank Account': 'bank_account'
            }
            df.rename(columns=rename_map, inplace=True)
            
            conn = get_conn()
            for _, r in df.iterrows():
                d_date = pd.to_datetime(r.get('DocDate'), errors='coerce').strftime('%Y-%m-%d')
                conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, category, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (d_date, str(r.get('DocNo','')), str(r.get('DocType','')), str(r.get('counterparty','')), str(r.get('Description','')), str(r.get('Category','')), 
                             float(r.get('Amount (Net)',0)), float(r.get('VAT Amount',0)), float(r.get('Amount (Gross)',0)),
                             str(r.get('Payment Method','')), str(r.get('bank_account','')), str(r.get('Status',''))))
            conn.commit()
            conn.close()
            st.success("✅ Εντάξει! Κάνε Refresh.")
        except Exception as e:
            st.error(f"Error: {e}")
    st.stop()

# --- 5. AUTH ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("🔐 Login")
    u = st.text_input("User"); p = st.text_input("Pass", type="password")
    if st.button("Enter"):
        if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"):
            st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
    st.stop()

# --- 6. SIDEBAR & MENU ---
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.write(f"User: {st.session_state.username}")
if st.sidebar.button("Logout"): st.session_state.logged_in=False; st.rerun()
st.sidebar.divider()

menu = st.sidebar.radio("ΜΕΝΟΥ", 
    ["📊 Dashboard", "📝 Νέα Εγγραφή", "🔢 Λογιστικό Σχέδιο", "📚 Αρχείο & Διαγραφή", "💵 Ταμείο & Τράπεζες", "⚙️ Ρυθμίσεις"]
)

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Εικόνα Επιχείρησης")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()
    
    # Data Cleaning for Dashboard
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    df['amount_net'] = pd.to_numeric(df['amount_net'], errors='coerce').fillna(0)
    
    cy = datetime.now().year
    df_y = df[df['doc_date'].dt.year == cy]
    
    inc = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
    exp = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
    prof = inc - exp
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Πωλήσεις (Net)", f"€{inc:,.0f}")
    c2.metric("Έξοδα (Net)", f"€{exp:,.0f}")
    c3.metric("Κέρδος (EBITDA)", f"€{prof:,.0f}")
    
    st.divider()
    monthly = df_y.copy()
    monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
    grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
    fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group')
    st.plotly_chart(fig, use_container_width=True)

# --- NEW ENTRY (WITH CALCULATOR & GL) ---
elif menu == "📝 Νέα Εγγραφή":
    st.title("📝 Νέα Εγγραφή (Smart Calculator)")
    
    with st.container():
        c1, c2, c3 = st.columns(3)
        d_date = c1.date_input("Ημερομηνία", date.today())
        d_type = c2.selectbox("Τύπος", ["Income", "Expense", "Bill"])
        d_no = c3.text_input("Αρ. Παρ/κου")
        
        c4, c5 = st.columns(2)
        partner = c4.text_input("Συναλλασσόμενος")
        descr = c5.text_input("Αιτιολογία")
        
        # GL Dropdown
        gl_code = st.selectbox("Λογαριασμός (GL)", options=sorted(GL_ACCOUNTS.keys()), format_func=lambda x: f"{x} - {GL_ACCOUNTS[x]}")

        st.divider()
        st.subheader("💶 Αυτόματος Υπολογισμός")
        k1, k2, k3, k4 = st.columns(4)
        
        # INPUTS με Session State για υπολογισμό
        net = k1.number_input("Καθαρό (€)", step=10.0, key='c_net', on_change=auto_calc)
        rate = k2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key='c_vat_rate', on_change=auto_calc)
        # OUTPUTS
        vat = k3.number_input("ΦΠΑ (€)", value=st.session_state.c_vat_val, key='vat_disp')
        gross = k4.number_input("Σύνολο (€)", value=st.session_state.c_gross, key='gross_disp')
        
        st.divider()
        c9, c10 = st.columns(2)
        pay = c9.selectbox("Τρόπος", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
        bank = c10.text_input("Λογαριασμός", "Alpha Bank" if pay=="Τράπεζα" else "Ταμείο" if pay=="Μετρητά" else "")
        
        if st.button("💾 Αποθήκευση"):
            status = "Unpaid" if pay == "Επί Πιστώσει" else "Paid"
            conn = get_conn()
            conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_account, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (d_date, d_no, d_type, partner, descr, gl_code, net, vat, gross, pay, bank, status))
            conn.commit()
            conn.close()
            st.success("✅ Καταχωρήθηκε!")
            # Reset calculator
            st.session_state.c_net = 0.0
            st.session_state.c_vat_val = 0.0
            st.session_state.c_gross = 0.0
            st.rerun()

# --- GL MAP PAGE ---
elif menu == "🔢 Λογιστικό Σχέδιο":
    st.title("🔢 Λογιστικό Σχέδιο (Chart of Accounts)")
    st.write("Χρησιμοποίησε αυτούς τους κωδικούς για σωστή κατάταξη.")
    
    df_gl = pd.DataFrame(list(GL_ACCOUNTS.items()), columns=['Κωδικός (GL)', 'Περιγραφή'])
    st.table(df_gl)

# --- JOURNAL (EDIT & DELETE) ---
elif menu == "📚 Αρχείο & Διαγραφή":
    st.title("📚 Αρχείο & Επεξεργασία")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    
    # --- FIX CRASH: Data Type Cleaning for Editor ---
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    # Make sure numbers are floats, not strings
    for col in ['amount_net', 'amount_gross', 'vat_amount']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    st.info("ℹ️ Για **ΔΙΑΓΡΑΦΗ**: Επιλέξτε τη γραμμή, πατήστε το πλήκτρο **Delete** στο πληκτρολόγιο και μετά το κουμπί **'💾 Αποθήκευση Αλλαγών'**.")
    
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "doc_date": st.column_config.DateColumn("Ημ/νία"),
            "amount_net": st.column_config.NumberColumn("Καθαρό"),
            "doc_type": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill"]),
            "gl_account": st.column_config.SelectboxColumn("GL", options=sorted(GL_ACCOUNTS.keys()))
        }
    )
    
    if st.button("💾 Αποθήκευση Αλλαγών (Save & Delete)"):
        conn = get_conn()
        conn.execute("DELETE FROM journal")
        
        # Save dates properly
        s_df = edited_df.copy()
        s_df['doc_date'] = pd.to_datetime(s_df['doc_date']).dt.strftime('%Y-%m-%d')
        
        s_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.commit()
        conn.close()
        st.success("✅ Η βάση ενημερώθηκε (τροποποιήσεις & διαγραφές).")
        st.rerun()

# --- TREASURY ---
elif menu == "💵 Ταμείο & Τράπεζες":
    st.title("💵 Διαθέσιμα")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal WHERE status='Paid'", conn)
    conn.close()
    
    # Data Cleaning for Treasury
    df['amount_gross'] = pd.to_numeric(df['amount_gross'], errors='coerce').fillna(0)
    
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
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    if st.button("🗑️ Hard Reset (Διαγραφή Όλων)"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.error("Η βάση διαγράφηκε. Κάνε Refresh.")
