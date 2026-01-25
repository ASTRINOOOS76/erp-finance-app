import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, date

# --- 1. PYΘΜΙΣΕΙΣ (PROFESSIONAL MODE) ---
st.set_page_config(page_title="SalesTree ERP Pro", layout="wide", page_icon="🏢")
DB_FILE = "erp_pro_final.db"

# Λογιστικό Σχέδιο (Όπως το ζήτησες)
GL_MAP = {
    "100": "Πωλήσεις (Έσοδα)",
    "200": "Αγορές & Έξοδα",
    "300": "Ταμείο (Μετρητά)",
    "400": "Τράπεζες",
    "500": "Μερίσματα",
    "600": "Πληρωμές Προμηθευτών",
    "700": "Εισπράξεις Πελατών"
}

# --- 2. CSS (ΑΥΣΤΗΡΟ ΕΠΑΓΓΕΛΜΑΤΙΚΟ ΣΤΥΛ) ---
st.markdown("""
<style>
    /* Γενικό */
    .stApp { background-color: #ffffff; color: #000000; font-family: 'Segoe UI', sans-serif; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #f0f2f5; border-right: 1px solid #d1d5db; }
    [data-testid="stSidebar"] * { color: #1f2937 !important; font-weight: 600; }
    
    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox div, .stDateInput input {
        background-color: #fff !important; color: #000 !important; 
        border: 1px solid #9ca3af !important; border-radius: 4px;
    }
    
    /* Buttons */
    .stButton>button {
        background-color: #111827 !important; color: #fff !important; 
        border: none; font-weight: bold; padding: 0.5rem 1rem;
    }
    .stButton>button:hover { background-color: #374151 !important; }
    
    /* Metrics/Cards */
    div[data-testid="metric-container"] {
        background-color: #fff; border: 1px solid #e5e7eb; 
        border-left: 5px solid #2563eb; padding: 15px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    
    /* Tables */
    [data-testid="stDataFrame"] { border: 1px solid #e5e7eb; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE ENGINE ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Κύριος Πίνακας Κινήσεων
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty TEXT, description TEXT, gl_code TEXT,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# --- 4. STATE MANAGEMENT (ΓΙΑ ΤΟΝ ΥΠΟΛΟΓΙΣΤΗ) ---
if 'calc_net' not in st.session_state: st.session_state.calc_net = 0.0
if 'calc_vat' not in st.session_state: st.session_state.calc_vat = 24
if 'calc_vat_val' not in st.session_state: st.session_state.calc_vat_val = 0.0
if 'calc_gross' not in st.session_state: st.session_state.calc_gross = 0.0

def update_totals():
    """Real-time υπολογισμός"""
    n = st.session_state.calc_net
    r = st.session_state.calc_vat
    v = n * (r / 100)
    g = n + v
    st.session_state.calc_vat_val = round(v, 2)
    st.session_state.calc_gross = round(g, 2)

# --- 5. INITIAL DATA LOAD (EXCEL) ---
conn = get_conn()
try:
    count = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
except: count = 0
conn.close()

if count == 0:
    st.title("⚠️ Εκκίνηση Συστήματος")
    st.info("Η βάση είναι κενή. Ανέβασε το αρχείο Excel για να ξεκινήσουμε.")
    up = st.file_uploader("Upload Journal.xlsx", type=['xlsx'])
    if up:
        try:
            xl = pd.ExcelFile(up, engine='openpyxl')
            sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(up, sheet_name=sheet)
            df.columns = df.columns.str.strip()
            
            # Mapping
            rename_map = {
                'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 
                'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType',
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
            conn.commit()
            conn.close()
            st.success("✅ Δεδομένα Φορτώθηκαν! Κάνε Refresh.")
        except Exception as e: st.error(f"Error: {e}")
    st.stop()

# --- 6. AUTHENTICATION ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("🔐 Login")
    c1, c2 = st.columns([1,2])
    with c1:
        u = st.text_input("User"); p = st.text_input("Pass", type="password")
        if st.button("Login"):
            if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"):
                st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
    st.stop()

# --- 7. MAIN APPLICATION ---
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.markdown(f"Χρήστης: **{st.session_state.username}**")
st.sidebar.divider()

menu = st.sidebar.radio("ΜΕΝΟΥ ΕΡΓΑΣΙΩΝ", [
    "📊 Dashboard & KPIs",
    "📝 Νέα Εγγραφή (Calculator)",
    "📇 Καρτέλες Πελατών (CRM)",
    "📚 Αρχείο & Διορθώσεις",
    "💵 Ταμείο & Τράπεζες",
    "⚙️ Ρυθμίσεις"
])

# --- DASHBOARD ---
if menu == "📊 Dashboard & KPIs":
    st.title("📊 Γενική Εικόνα")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()
    
    df['doc_date'] = pd.to_datetime(df['doc_date'], errors='coerce')
    cy = datetime.now().year
    df_y = df[df['doc_date'].dt.year == cy]
    
    inc = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
    exp = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
    vat_diff = df_y[df_y['doc_type']=='Income']['vat_amount'].sum() - df_y[df_y['doc_type']!='Income']['vat_amount'].sum()
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Πωλήσεις (Net)", f"€{inc:,.0f}")
    k2.metric("Έξοδα (Net)", f"€{exp:,.0f}")
    k3.metric("Κέρδος", f"€{inc-exp:,.0f}")
    k4.metric("ΦΠΑ Απόδοσης", f"€{vat_diff:,.0f}", delta="Πληρωμή" if vat_diff>0 else "Επιστροφή", delta_color="inverse")
    
    st.divider()
    st.subheader("📉 Μηνιαία Εξέλιξη")
    monthly = df_y.copy()
    monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
    grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
    fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group')
    st.plotly_chart(fig, use_container_width=True)

# --- ENTRY WITH CALCULATOR ---
elif menu == "📝 Νέα Εγγραφή (Calculator)":
    st.title("📝 Νέα Εγγραφή")
    
    # 1. ΒΑΣΙΚΑ ΣΤΟΙΧΕΙΑ
    c1, c2, c3 = st.columns(3)
    d_date = c1.date_input("Ημερομηνία", date.today())
    d_type = c2.selectbox("Τύπος Παραστατικού", ["Income", "Expense", "Bill"])
    d_no = c3.text_input("Αρ. Παραστατικού")
    
    c4, c5, c6 = st.columns(3)
    partner = c4.text_input("Συναλλασσόμενος")
    descr = c5.text_input("Αιτιολογία")
    # GL Dropdown
    gl_choice = c6.selectbox("Κωδικός Λογιστικής", options=list(GL_MAP.keys()), format_func=lambda x: f"{x} - {GL_MAP[x]}")

    st.divider()
    st.subheader("🧮 Οικονομικά Στοιχεία (Auto Calc)")
    
    # 2. CALCULATOR
    k1, k2, k3, k4 = st.columns(4)
    # Εδώ είναι το "μαγικό" on_change που κάνει τον υπολογισμό
    net = k1.number_input("Καθαρή Αξία (€)", step=10.0, key='calc_net', on_change=update_totals)
    rate = k2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key='calc_vat', on_change=update_totals)
    # Τα αποτελέσματα
    vat = k3.number_input("ΦΠΑ (€)", value=st.session_state.calc_vat_val, key='disp_vat')
    gross = k4.number_input("Σύνολο (€)", value=st.session_state.calc_gross, key='disp_gross')
    
    st.divider()
    
    # 3. ΠΛΗΡΩΜΗ
    p1, p2 = st.columns(2)
    pay_method = p1.selectbox("Τρόπος Πληρωμής", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
    bank = p2.text_input("Λογαριασμός", "Alpha Bank" if pay_method=="Τράπεζα" else "Ταμείο" if pay_method=="Μετρητά" else "")
    
    # 4. SAVE
    if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ ΕΓΓΡΑΦΗΣ", type="primary"):
        # Έλεγχος
        if abs(gross - (st.session_state.calc_net + vat)) > 0.1:
            st.error("❌ Λάθος στα ποσά! Καθαρό + ΦΠΑ δεν κάνουν το Σύνολο.")
        else:
            status = "Unpaid" if pay_method == "Επί Πιστώσει" else "Paid"
            conn = get_conn()
            conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (d_date, d_no, d_type, partner, descr, gl_choice, st.session_state.calc_net, vat, gross, pay_method, bank, status))
            conn.commit()
            conn.close()
            st.success("✅ Η εγγραφή αποθηκεύτηκε!")
            # Reset
            st.session_state.calc_net = 0.0
            st.session_state.calc_vat_val = 0.0
            st.session_state.calc_gross = 0.0
            st.rerun()

# --- CRM / LEDGERS ---
elif menu == "📇 Καρτέλες Πελατών (CRM)":
    st.title("📇 Καρτέλες Συναλλασσόμενων")
    
    conn = get_conn()
    partners = pd.read_sql("SELECT DISTINCT counterparty FROM journal ORDER BY counterparty", conn)['counterparty'].tolist()
    
    sel_partner = st.selectbox("Επιλογή Πελάτη/Προμηθευτή", partners)
    
    if sel_partner:
        df_p = pd.read_sql(f"SELECT * FROM journal WHERE counterparty = '{sel_partner}' ORDER BY doc_date DESC", conn)
        
        # Υπολογισμός Υπολοίπου (Χονδρικός)
        # Θεωρούμε Income = Χρέωση, Payment = Πίστωση (απλοποιημένα)
        balance = df_p[df_p['status']=='Unpaid']['amount_gross'].sum()
        
        c1, c2 = st.columns([1, 3])
        c1.metric("Τρέχον Υπόλοιπο (Unpaid)", f"€{balance:,.2f}")
        
        c2.subheader("Κινήσεις")
        c2.dataframe(df_p[['doc_date', 'doc_type', 'description', 'amount_gross', 'status']], use_container_width=True)
    conn.close()

# --- EDIT & DELETE (THE EXCEL WAY) ---
elif menu == "📚 Αρχείο & Διορθώσεις":
    st.title("📚 Αρχείο & Επεξεργασία")
    st.info("💡 **Οδηγίες:** Για διαγραφή, επιλέξτε το κουτάκι αριστερά της γραμμής, πατήστε 'Delete' στο πληκτρολόγιο και μετά το κουμπί 'Αποθήκευση'.")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    
    # Τύποι Δεδομένων (Fix Crash)
    df['doc_date'] = pd.to_datetime(df['doc_date']).dt.date
    for col in ['amount_net', 'vat_amount', 'amount_gross']:
        df[col] = pd.to_numeric(df[col]).fillna(0.0)
    
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True,
        column_config={
            "doc_date": st.column_config.DateColumn("Ημερομηνία"),
            "amount_net": st.column_config.NumberColumn("Καθαρό"),
            "amount_gross": st.column_config.NumberColumn("Μικτό"),
            "doc_type": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill"]),
            "gl_code": st.column_config.SelectboxColumn("Κωδικός", options=list(GL_MAP.keys())),
            "status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"])
        }
    )
    
    if st.button("💾 ΑΠΟΘΗΚΕΥΣΗ ΑΛΛΑΓΩΝ & ΔΙΑΓΡΑΦΩΝ", type="primary"):
        conn = get_conn()
        conn.execute("DELETE FROM journal")
        
        # Save Back
        save_df = edited_df.copy()
        save_df['doc_date'] = pd.to_datetime(save_df['doc_date']).dt.strftime('%Y-%m-%d')
        
        save_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.commit()
        conn.close()
        st.success("✅ Η βάση ενημερώθηκε επιτυχώς!")
        st.rerun()

# --- TREASURY ---
elif menu == "💵 Ταμείο & Τράπεζες":
    st.title("💵 Διαθέσιμα")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal WHERE status='Paid'", conn)
    conn.close()
    
    # Καθαρισμός για Treasury
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
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    if st.button("⚠️ Hard Reset (Διαγραφή Όλων)"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.error("Η βάση διαγράφηκε. Κάνε Refresh τη σελίδα.")
