import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, date

# --- 1. CONFIG ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")
DB_FILE = "erp_simple_gl.db"

# --- 2. ΤΟ ΝΕΟ ΑΠΛΟ ΛΟΓΙΣΤΙΚΟ ΣΧΕΔΙΟ ΠΟΥ ΖΗΤΗΣΕΣ ---
SIMPLE_GL = {
    100: "Πωλήσεις (Έσοδα)",
    200: "Αγορές (Έξοδα)",
    300: "Ταμείο (Cash)",
    400: "Τράπεζες (Bank)",
    500: "Μερίσματα (Dividends)",
    600: "Πληρωμές (Payments)",
    700: "Εισπράξεις (Receipts)"
}

# --- 3. CSS (ΜΟΝΟ ΑΣΠΡΟ/ΜΑΥΡΟ - ΚΑΘΑΡΟ) ---
st.markdown("""
<style>
    .stApp { background-color: #ffffff; color: #000000; }
    [data-testid="stSidebar"] { background-color: #f4f4f4; border-right: 1px solid #000; }
    h1, h2, h3, h4, p, label, div, span, li, td, th { color: #000000 !important; font-family: sans-serif; }
    
    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        background-color: #fff !important; color: #000 !important; border: 1px solid #000 !important;
    }
    
    /* Buttons */
    .stButton>button {
        background-color: #000 !important; color: #fff !important; border: 2px solid #000; font-weight: bold; width: 100%;
    }
    .stButton>button:hover { background-color: #333 !important; }
    
    /* Cards */
    div[data-testid="metric-container"] {
        background-color: #fff; border: 2px solid #000; padding: 10px; box-shadow: 4px 4px 0px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- 4. CALCULATOR LOGIC (STATE MANAGEMENT) ---
if 'net_val' not in st.session_state: st.session_state.net_val = 0.0
if 'vat_pc' not in st.session_state: st.session_state.vat_pc = 24
if 'vat_val' not in st.session_state: st.session_state.vat_val = 0.0
if 'gross_val' not in st.session_state: st.session_state.gross_val = 0.0

def update_from_net():
    """Όταν αλλάζει το Καθαρό, υπολογίζει τα υπόλοιπα"""
    n = st.session_state.net_val
    r = st.session_state.vat_pc
    v = n * (r / 100)
    g = n + v
    st.session_state.vat_val = round(v, 2)
    st.session_state.gross_val = round(g, 2)

# --- 5. DATABASE SETUP ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty TEXT, description TEXT, gl_category TEXT,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# --- 6. DATA IMPORT (AUTO EXCEL) ---
conn = get_conn()
try:
    count = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
except: count = 0
conn.close()

if count == 0:
    st.title("⚠️ Αρχική Ρύθμιση")
    st.warning("Η βάση είναι κενή. Ανέβασε το Excel τώρα.")
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
                conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (d_date, str(r.get('DocNo','')), str(r.get('DocType','')), str(r.get('counterparty','')), str(r.get('Description','')), 
                             float(r.get('Amount (Net)',0)), float(r.get('VAT Amount',0)), float(r.get('Amount (Gross)',0)),
                             str(r.get('Payment Method','')), str(r.get('bank_account','')), str(r.get('Status',''))))
            conn.commit()
            conn.close()
            st.success("✅ Εντάξει! Κάνε Refresh.")
        except: st.error("Error loading Excel")
    st.stop()

# --- 7. AUTH ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("🔐 Login")
    u = st.text_input("User"); p = st.text_input("Pass", type="password")
    if st.button("Enter"):
        if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"):
            st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
    st.stop()

# --- 8. MAIN APP ---
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
    
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    cy = datetime.now().year
    df_y = df[df['doc_date'].dt.year == cy]
    
    inc = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
    exp = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
    prof = inc - exp
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Πωλήσεις", f"€{inc:,.0f}")
    c2.metric("Έξοδα", f"€{exp:,.0f}")
    c3.metric("Κέρδος", f"€{prof:,.0f}")
    
    st.divider()
    monthly = df_y.copy()
    monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
    grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
    fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group')
    st.plotly_chart(fig, use_container_width=True)

# --- NEW ENTRY (FIXED CALCULATOR) ---
elif menu == "📝 Νέα Εγγραφή":
    st.title("📝 Νέα Εγγραφή")
    st.info("💡 Ο υπολογισμός γίνεται αυτόματα μόλις αλλάξεις το 'Καθαρό Ποσό' και πατήσεις Enter ή κλικ έξω.")

    # A. ΣΤΟΙΧΕΙΑ
    c1, c2, c3 = st.columns(3)
    d_date = c1.date_input("Ημερομηνία", date.today())
    d_type = c2.selectbox("Τύπος", ["Income", "Expense", "Bill"])
    d_no = c3.text_input("Αρ. Παρ/κου")
    
    c4, c5 = st.columns(2)
    partner = c4.text_input("Συναλλασσόμενος")
    descr = c5.text_input("Αιτιολογία")

    # B. ΛΟΓΙΣΤΙΚΟ ΣΧΕΔΙΟ
    gl_cat = st.selectbox("Κατηγορία (Λογιστικό)", options=sorted(SIMPLE_GL.keys()), format_func=lambda x: f"{x} - {SIMPLE_GL[x]}")

    st.divider()
    st.subheader("💶 Ποσά (Αυτόματος Υπολογισμός)")
    
    # C. CALCULATOR (ΧΩΡΙΣ ΦΟΡΜΑ ΓΙΑ ΝΑ ΔΟΥΛΕΥΕΙ ΤΟ REAL TIME)
    k1, k2, k3, k4 = st.columns(4)
    
    # Εδώ είναι το μυστικό: on_change καλεί τη συνάρτηση update_from_net
    k1.number_input("Καθαρό (€)", step=10.0, key='net_val', on_change=update_from_net)
    k2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key='vat_pc', on_change=update_from_net)
    
    # Τα πεδία αυτά παίρνουν τιμή από το session_state
    vat = k3.number_input("ΦΠΑ (€)", value=st.session_state.vat_val, disabled=False, key='vat_input')
    gross = k4.number_input("Σύνολο (€)", value=st.session_state.gross_val, disabled=False, key='gross_input')
    
    st.divider()
    
    # D. ΠΛΗΡΩΜΗ
    c9, c10 = st.columns(2)
    pay = c9.selectbox("Τρόπος", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
    bank = c10.text_input("Λογαριασμός", "Alpha Bank" if pay=="Τράπεζα" else "Ταμείο" if pay=="Μετρητά" else "")
    
    # E. SAVE BUTTON (ΞΕΧΩΡΙΣΤΟ)
    if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ ΕΓΓΡΑΦΗΣ"):
        status = "Unpaid" if pay == "Επί Πιστώσει" else "Paid"
        
        # Validation
        if abs(gross - (st.session_state.net_val + vat)) > 0.1:
            st.error("❌ Τα ποσά δεν συμφωνούν! Ελέγξτε τα νούμερα.")
        else:
            conn = get_conn()
            conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_category, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (d_date, d_no, d_type, partner, descr, str(gl_cat), st.session_state.net_val, vat, gross, pay, bank, status))
            conn.commit()
            conn.close()
            st.success("✅ Η εγγραφή αποθηκεύτηκε!")
            
            # Reset
            st.session_state.net_val = 0.0
            st.session_state.vat_val = 0.0
            st.session_state.gross_val = 0.0
            st.rerun()

# --- GL MAP DISPLAY ---
elif menu == "🔢 Λογιστικό Σχέδιο":
    st.title("🔢 Λογιστικό Σχέδιο")
    st.write("Οι κατηγορίες που ζήτησες:")
    df_gl = pd.DataFrame(list(SIMPLE_GL.items()), columns=['Κωδικός', 'Περιγραφή'])
    st.table(df_gl)

# --- JOURNAL & DELETE ---
elif menu == "📚 Αρχείο & Διαγραφή":
    st.title("📚 Αρχείο & Επεξεργασία")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    
    # Data cleaning to prevent crashes
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    for c in ['amount_net', 'vat_amount', 'amount_gross']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    st.warning("⚠️ ΟΔΗΓΙΕΣ ΔΙΑΓΡΑΦΗΣ: 1. Επιλέξτε τη γραμμή (κουτάκι αριστερά) -> 2. Πατήστε Delete στο πληκτρολόγιο -> 3. Πατήστε το κουμπί 'Αποθήκευση Αλλαγών' από κάτω.")
    
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "doc_date": st.column_config.DateColumn("Ημ/νία"),
            "amount_net": st.column_config.NumberColumn("Καθαρό"),
            "doc_type": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill"]),
            "gl_category": st.column_config.SelectboxColumn("Κατηγορία", options=sorted([str(k) for k in SIMPLE_GL.keys()]))
        }
    )
    
    if st.button("💾 Αποθήκευση Αλλαγών (Οριστική Διαγραφή)"):
        conn = get_conn()
        conn.execute("DELETE FROM journal")
        
        s_df = edited_df.copy()
        s_df['doc_date'] = pd.to_datetime(s_df['doc_date']).dt.strftime('%Y-%m-%d')
        
        s_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.commit()
        conn.close()
        st.success("✅ Η βάση ενημερώθηκε.")
        st.rerun()

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
        st.error("Βάση διεγράφη.")
