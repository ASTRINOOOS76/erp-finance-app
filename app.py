import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, date

# --- 1. RYZMISI SELIDAS & CSS (FORCED LIGHT THEME) ---
st.set_page_config(page_title="SalesTree ERP Final", layout="wide", page_icon="🏢")
DB_FILE = "erp_v4_stable.db"

# ΕΠΙΒΟΛΗ ΛΕΥΚΟΥ ΘΕΜΑΤΟΣ & ΚΑΘΑΡΗΣ ΓΡΑΜΜΑΤΟΣΕΙΡΑΣ
st.markdown("""
<style>
    /* Force Light Mode */
    .stApp {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa !important;
        border-right: 1px solid #dee2e6 !important;
    }
    [data-testid="stSidebar"] * {
        color: #212529 !important;
    }

    /* Inputs styling (Borders & Text) */
    .stTextInput input, .stNumberInput input, .stSelectbox div, .stDateInput input {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #ced4da !important;
        border-radius: 4px !important;
    }
    
    /* Metrics Cards */
    div[data-testid="metric-container"] {
        background-color: #ffffff !important;
        border: 1px solid #dee2e6 !important;
        padding: 15px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
        border-radius: 8px !important;
    }
    div[data-testid="metric-container"] label { color: #6c757d !important; }
    div[data-testid="metric-container"] div { color: #000000 !important; }

    /* Buttons */
    .stButton>button {
        background-color: #0d6efd !important;
        color: #ffffff !important;
        border: none !important;
        font-weight: bold !important;
        padding: 0.5rem 1rem !important;
    }
    .stButton>button:hover {
        background-color: #0b5ed7 !important;
    }
    
    /* Tables */
    [data-testid="stDataFrame"] {
        border: 1px solid #dee2e6 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. LOGIC & CALCULATOR (CALLBACKS) ---
# Αρχικοποίηση μεταβλητών Session State
if 'calc_net' not in st.session_state: st.session_state.calc_net = 0.0
if 'calc_vat_rate' not in st.session_state: st.session_state.calc_vat_rate = 24
if 'calc_vat_val' not in st.session_state: st.session_state.calc_vat_val = 0.0
if 'calc_gross' not in st.session_state: st.session_state.calc_gross = 0.0

def update_calc():
    """Αυτή η συνάρτηση τρέχει ΑΥΤΟΜΑΤΑ όταν αλλάζει το ποσό"""
    try:
        n = float(st.session_state.calc_net)
        r = float(st.session_state.calc_vat_rate)
        v = n * (r / 100.0)
        g = n + v
        st.session_state.calc_vat_val = round(v, 2)
        st.session_state.calc_gross = round(g, 2)
    except:
        pass

# --- 3. DATABASE SETUP ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # 1. Πίνακας Κινήσεων (Journal)
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, 
        doc_no TEXT, 
        doc_type TEXT,
        counterparty TEXT, 
        description TEXT, 
        gl_code TEXT,
        amount_net REAL, 
        vat_amount REAL, 
        amount_gross REAL,
        payment_method TEXT, 
        bank_account TEXT, 
        status TEXT
    )''')
    
    # 2. Πίνακας Λογιστικού Σχεδίου (GL Codes)
    c.execute('''CREATE TABLE IF NOT EXISTS gl_codes (
        code TEXT PRIMARY KEY,
        description TEXT
    )''')
    
    # Default GL Codes (Αν είναι άδειο)
    try:
        if c.execute("SELECT count(*) FROM gl_codes").fetchone()[0] == 0:
            defaults = [
                ("100", "Πωλήσεις (Έσοδα)"), 
                ("200", "Αγορές (Έξοδα)"),
                ("300", "Ταμείο (Μετρητά)"),
                ("400", "Τράπεζες"),
                ("500", "Μερίσματα"),
                ("600", "Μισθοδοσία"),
                ("640", "Γενικά Έξοδα")
            ]
            c.executemany("INSERT INTO gl_codes VALUES (?,?)", defaults)
            conn.commit()
    except: pass
    
    conn.commit()
    conn.close()

init_db()

# --- 4. DATA LOADING HELPER ---
# Φορτώνουμε τα δεδομένα με ασφάλεια (Data Cleaning)
def load_journal():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    
    # Κρίσιμο: Μετατροπή τύπων για να μην σκάει το Streamlit
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    for col in ['amount_net', 'vat_amount', 'amount_gross']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    return df

# --- 5. INITIAL SETUP SCREEN ---
conn = get_conn()
try:
    count = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
except: count = 0
conn.close()

if count == 0:
    st.title("⚠️ Εγκατάσταση SalesTree ERP")
    st.info("Η βάση δεδομένων είναι κενή.")
    
    col1, col2 = st.columns(2)
    
    # Επιλογή 1: Ανέβασμα Excel
    up = col1.file_uploader("Εισαγωγή Excel (Journal)", type=['xlsx'])
    if up:
        try:
            xl = pd.ExcelFile(up, engine='openpyxl')
            sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(up, sheet_name=sheet)
            df.columns = df.columns.str.strip()
            
            # Mapping
            rename_map = {'Date': 'DocDate', 'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType', 'Counterparty': 'counterparty'}
            df.rename(columns=rename_map, inplace=True)
            
            conn = get_conn()
            for _, r in df.iterrows():
                d_date = pd.to_datetime(r.get('DocDate'), errors='coerce').strftime('%Y-%m-%d')
                conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (d_date, str(r.get('DocNo','')), str(r.get('DocType','')), str(r.get('counterparty','')), str(r.get('Description','')), "999", 
                             float(r.get('Amount (Net)',0)), float(r.get('VAT Amount',0)), float(r.get('Amount (Gross)',0)),
                             str(r.get('Payment Method','')), str(r.get('Bank Account','')), str(r.get('Status',''))))
            conn.commit(); conn.close()
            st.success("✅ Ετοιμο! Κάνε Refresh."); st.stop()
        except Exception as e: st.error(f"Error: {e}")

    # Επιλογή 2: Εκκίνηση από το μηδέν
    if col2.button("🚀 Εκκίνηση από το Μηδέν"):
        conn = get_conn()
        conn.execute("INSERT INTO journal (description) VALUES ('init')") # Dummy row
        conn.execute("DELETE FROM journal") # Clean it
        conn.commit(); conn.close()
        st.rerun()
    st.stop()

# --- 6. MAIN APP ---
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.info("Έκδοση: v4.0 Stable")

menu = st.sidebar.radio("ΜΕΝΟΥ ΕΠΙΛΟΓΩΝ", [
    "📊 Dashboard",
    "📝 Νέα Εγγραφή",
    "📇 Καρτέλες (Ledgers)",
    "📚 Αρχείο & Διορθώσεις",
    "⚙️ Ρυθμίσεις GL"
])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Οικονομική Εικόνα")
    df = load_journal()
    
    # Φίλτρο Έτους
    cy = datetime.now().year
    df_y = df[df['doc_date'].dt.year == cy]
    
    # Υπολογισμοί
    inc = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
    exp = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
    profit = inc - exp
    
    # Cards
    c1, c2, c3 = st.columns(3)
    c1.metric("Πωλήσεις", f"€{inc:,.2f}")
    c2.metric("Έξοδα", f"€{exp:,.2f}")
    c3.metric("Κέρδος", f"€{profit:,.2f}")
    
    st.divider()
    
    # Charts
    c4, c5 = st.columns(2)
    with c4:
        st.subheader("Μηνιαία Κίνηση")
        if not df_y.empty:
            df_y['Month'] = df_y['doc_date'].dt.strftime('%Y-%m')
            grp = df_y.groupby(['Month', 'doc_type'])['amount_net'].sum().reset_index()
            fig = px.bar(grp, x='Month', y='amount_net', color='doc_type', barmode='group')
            st.plotly_chart(fig, use_container_width=True)
    
    with c5:
        st.subheader("Κατανομή Εξόδων")
        exp_df = df_y[df_y['doc_type'].isin(['Expense','Bill'])]
        if not exp_df.empty:
            fig2 = px.pie(exp_df, values='amount_net', names='gl_code', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

# --- NEW ENTRY (REAL CALCULATOR) ---
elif menu == "📝 Νέα Εγγραφή":
    st.title("📝 Καταχώρηση Παραστατικού")
    
    # Φόρτωση GL Codes
    conn = get_conn()
    gl_df = pd.read_sql("SELECT code, description FROM gl_codes ORDER BY code", conn)
    conn.close()
    gl_list = gl_df.apply(lambda x: f"{x['code']} - {x['description']}", axis=1).tolist()

    # 1. Στοιχεία
    c1, c2, c3 = st.columns(3)
    d_date = c1.date_input("Ημερομηνία", date.today())
    d_type = c2.selectbox("Τύπος", ["Income", "Expense", "Bill"])
    d_no = c3.text_input("Αρ. Παραστατικού")
    
    c4, c5 = st.columns(2)
    partner = c4.text_input("Συναλλασσόμενος (Πελάτης/Προμηθευτής)")
    gl_choice = c5.selectbox("Λογαριασμός (GL)", gl_list if gl_list else ["999 - General"])
    descr = st.text_input("Αιτιολογία")

    st.markdown("---")
    st.subheader("🧮 Υπολογισμός Αξίας")
    
    # 2. CALCULATOR - Χωρίς st.form για να δουλεύει το on_change
    k1, k2, k3, k4 = st.columns(4)
    
    # INPUTS
    k1.number_input("Καθαρή Αξία (€)", step=10.0, key='calc_net', on_change=update_calc)
    k2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key='calc_vat_rate', on_change=update_calc)
    
    # OUTPUTS (Disabled για να δείχνουν μόνο το αποτέλεσμα)
    vat = k3.number_input("Ποσό ΦΠΑ (€)", value=st.session_state.calc_vat_val, disabled=True, key='disp_vat')
    gross = k4.number_input("Σύνολο (€)", value=st.session_state.calc_gross, disabled=True, key='disp_gross')
    
    st.markdown("---")
    
    # 3. ΠΛΗΡΩΜΗ & SAVE
    p1, p2, p3 = st.columns([2, 2, 1])
    pay = p1.selectbox("Τρόπος Πληρωμής", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
    bank = p2.text_input("Λογαριασμός (π.χ. Alpha Bank, Ταμείο)")
    
    # Save Button
    if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ", type="primary", use_container_width=True):
        status = "Unpaid" if pay == "Επί Πιστώσει" else "Paid"
        gl_val = gl_choice.split(" - ")[0] if gl_choice else "999"
        
        conn = get_conn()
        conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d_date, d_no, d_type, partner, descr, gl_val, st.session_state.calc_net, vat, gross, pay, bank, status))
        conn.commit()
        conn.close()
        
        st.success("✅ Η εγγραφή αποθηκεύτηκε επιτυχώς!")
        # Reset values
        st.session_state.calc_net = 0.0
        st.session_state.calc_vat_val = 0.0
        st.session_state.calc_gross = 0.0
        st.rerun()

# --- LEDGERS ---
elif menu == "📇 Καρτέλες (Ledgers)":
    st.title("📇 Καρτέλες Συναλλασσόμενων")
    conn = get_conn()
    partners = pd.read_sql("SELECT DISTINCT counterparty FROM journal WHERE counterparty <> '' ORDER BY counterparty", conn)['counterparty'].tolist()
    
    sel = st.selectbox("Επιλέξτε Συναλλασσόμενο", partners)
    if sel:
        df = pd.read_sql(f"SELECT * FROM journal WHERE counterparty='{sel}' ORDER BY doc_date DESC", conn)
        
        # Υπολογισμός Υπολοίπου (Simple)
        balance = df[df['status']=='Unpaid']['amount_gross'].sum()
        
        c1, c2 = st.columns([1, 3])
        c1.info(f"**Ανοιχτό Υπόλοιπο:**\n# €{balance:,.2f}")
        c2.dataframe(df[['doc_date', 'doc_type', 'description', 'amount_gross', 'status']], use_container_width=True)
    conn.close()

# --- ARCHIVE & EDIT ---
elif menu == "📚 Αρχείο & Διορθώσεις":
    st.title("📚 Αρχείο Κινήσεων")
    
    # Load and clean data
    df = load_journal()
    
    # Get GL Options for Dropdown inside Editor
    conn = get_conn()
    gl_codes = pd.read_sql("SELECT code FROM gl_codes", conn)['code'].tolist()
    conn.close()
    
    st.markdown("### Οδηγίες Επεξεργασίας:")
    st.info("1. Κάντε διπλό κλικ σε κελί για αλλαγή.\n2. Για **ΔΙΑΓΡΑΦΗ**: Επιλέξτε το κουτί αριστερά της γραμμής, πατήστε `Delete` στο πληκτρολόγιο.\n3. Πατήστε **'Αποθήκευση Αλλαγών'** στο τέλος.")
    
    # THE EDITOR
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "doc_date": st.column_config.DateColumn("Ημερομηνία"),
            "amount_net": st.column_config.NumberColumn("Καθαρό", format="€%.2f"),
            "amount_gross": st.column_config.NumberColumn("Μικτό", format="€%.2f"),
            "gl_code": st.column_config.SelectboxColumn("Κωδικός GL", options=gl_codes),
            "doc_type": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill"]),
            "status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"])
        }
    )
    
    if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ ΑΛΛΑΓΩΝ", type="primary"):
        conn = get_conn()
        conn.execute("DELETE FROM journal") # Διαγράφουμε τα παλιά
        
        # Σώζουμε τα καινούργια (Το edited_df έχει τις αλλαγές ΚΑΙ τις διαγραφές)
        s_df = edited_df.copy()
        s_df['doc_date'] = pd.to_datetime(s_df['doc_date']).dt.strftime('%Y-%m-%d')
        
        s_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.commit()
        conn.close()
        st.success("✅ Η βάση ενημερώθηκε!")
        st.rerun()

# --- SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις GL":
    st.title("⚙️ Ρυθμίσεις Λογιστικού Σχεδίου")
    
    conn = get_conn()
    df_gl = pd.read_sql("SELECT * FROM gl_codes ORDER BY code", conn)
    
    st.write("Μπορείτε να προσθέσετε ή να αλλάξετε κωδικούς εδώ:")
    edited_gl = st.data_editor(df_gl, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Ενημέρωση GL"):
        conn.execute("DELETE FROM gl_codes")
        edited_gl.to_sql('gl_codes', conn, if_exists='append', index=False)
        conn.commit()
        st.success("Το Λογιστικό Σχέδιο αποθηκεύτηκε!")
        st.rerun()
    
    st.divider()
    if st.button("🗑️ Hard Reset (ΠΡΟΣΟΧΗ)"):
        conn.close()
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.warning("Η βάση διαγράφηκε. Κάντε Refresh.")
