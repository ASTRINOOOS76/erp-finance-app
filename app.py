import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, date

# --- 1. CONFIG ---
st.set_page_config(page_title="SalesTree ERP Custom", layout="wide", page_icon="🏢")
DB_FILE = "erp_custom.db"

# --- 2. CSS (CLEAN WHITE/BLACK) ---
st.markdown("""
<style>
    .stApp { background-color: #ffffff; color: #000000; }
    [data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #ddd; }
    [data-testid="stSidebar"] * { color: #000 !important; font-weight: 600; }
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        background-color: #fff !important; color: #000 !important; border: 1px solid #ccc !important;
    }
    .stButton>button {
        background-color: #000 !important; color: #fff !important; font-weight: bold; border: none;
    }
    .stButton>button:hover { background-color: #444 !important; }
    div[data-testid="metric-container"] {
        background-color: #fff; border: 1px solid #000; padding: 10px; box-shadow: 2px 2px 0px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE ENGINE ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # 1. Πίνακας Κινήσεων (Journal)
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty TEXT, description TEXT, gl_code TEXT,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT
    )''')
    
    # 2. Πίνακας Λογιστικού Σχεδίου (GL Codes) - ΠΑΡΑΜΕΤΡΟΠΟΙΗΣΙΜΟ
    c.execute('''CREATE TABLE IF NOT EXISTS gl_codes (
        code TEXT PRIMARY KEY,
        description TEXT
    )''')
    
    conn.commit()
    
    # Γέμισμα με αρχικά δεδομένα αν είναι άδειο (για να μην ξεκινάς από το μηδέν)
    count = c.execute("SELECT count(*) FROM gl_codes").fetchone()[0]
    if count == 0:
        defaults = [
            ("100", "Πωλήσεις Εμπορευμάτων"),
            ("101", "Πωλήσεις Υπηρεσιών"),
            ("200", "Αγορές Εμπορευμάτων"),
            ("600", "Γενικά Έξοδα"),
            ("610", "Ενοίκια"),
            ("620", "ΔΕΗ / Τηλεπικοινωνίες")
        ]
        c.executemany("INSERT INTO gl_codes (code, description) VALUES (?,?)", defaults)
        conn.commit()
        
    conn.close()

init_db()

# --- 4. CALCULATOR STATE ---
if 'calc_net' not in st.session_state: st.session_state.calc_net = 0.0
if 'calc_vat' not in st.session_state: st.session_state.calc_vat = 24
if 'calc_vat_val' not in st.session_state: st.session_state.calc_vat_val = 0.0
if 'calc_gross' not in st.session_state: st.session_state.calc_gross = 0.0

def update_calc():
    """Real-time υπολογισμός"""
    try:
        n = float(st.session_state.calc_net)
        r = float(st.session_state.calc_vat)
        v = n * (r / 100.0)
        g = n + v
        st.session_state.calc_vat_val = round(v, 2)
        st.session_state.calc_gross = round(g, 2)
    except:
        pass

# --- 5. DATA LOAD & RECOVERY ---
conn = get_conn()
try:
    count_j = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
except: count_j = 0
conn.close()

if count_j == 0:
    st.title("⚠️ Εκκίνηση Συστήματος")
    st.info("Η βάση είναι κενή. Μπορείς να ανεβάσεις Excel ή να ξεκινήσεις από το μηδέν.")
    
    up = st.file_uploader("Εισαγωγή Excel (Προαιρετικό)", type=['xlsx'])
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
                conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (d_date, str(r.get('DocNo','')), str(r.get('DocType','')), str(r.get('counterparty','')), str(r.get('Description','')), "Unassigned", 
                             float(r.get('Amount (Net)',0)), float(r.get('VAT Amount',0)), float(r.get('Amount (Gross)',0)),
                             str(r.get('Payment Method','')), str(r.get('bank_account','')), str(r.get('Status',''))))
            conn.commit()
            conn.close()
            st.success("✅ Δεδομένα Φορτώθηκαν! Κάνε Refresh.")
        except Exception as e: st.error(f"Error: {e}")
    
    if st.button("🚀 Ξεκινάω από το μηδέν (χωρίς Excel)"):
        # Απλά εισάγουμε μια dummy εγγραφή για να ξεκολλήσει το count
        conn = get_conn()
        conn.execute("INSERT INTO journal (doc_date, description) VALUES (?,?)", (date.today(), 'System Init'))
        conn.execute("DELETE FROM journal WHERE description='System Init'") # Τη σβήνουμε αμέσως
        conn.commit()
        conn.close()
        st.rerun()
    
    st.stop()

# --- 6. AUTH ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("🔐 Login")
    u = st.text_input("User"); p = st.text_input("Pass", type="password")
    if st.button("Login"):
        if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"):
            st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
    st.stop()

# --- 7. MAIN MENU ---
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.write(f"Χρήστης: **{st.session_state.username}**")
st.sidebar.divider()

menu = st.sidebar.radio("ΜΕΝΟΥ", [
    "📊 Dashboard",
    "📝 Νέα Εγγραφή",
    "📇 Καρτέλες (Ledgers)",
    "📚 Αρχείο & Διορθώσεις",
    "⚙️ Ρυθμίσεις & GL"
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
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Πωλήσεις (Net)", f"€{inc:,.0f}")
    k2.metric("Έξοδα (Net)", f"€{exp:,.0f}")
    k3.metric("Κέρδος", f"€{inc-exp:,.0f}")
    
    st.divider()
    monthly = df_y.copy()
    monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
    grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
    fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group')
    st.plotly_chart(fig, use_container_width=True)

# --- NEW ENTRY (WITH DB GL) ---
elif menu == "📝 Νέα Εγγραφή":
    st.title("📝 Νέα Εγγραφή")
    
    # 1. Fetch GL Codes from DB
    conn = get_conn()
    gl_df = pd.read_sql("SELECT code, description FROM gl_codes ORDER BY code", conn)
    gl_options = gl_df.apply(lambda x: f"{x['code']} - {x['description']}", axis=1).tolist()
    conn.close()
    
    if not gl_options:
        st.error("⚠️ Το Λογιστικό Σχέδιο είναι άδειο! Πήγαινε στις Ρυθμίσεις να προσθέσεις κωδικούς.")
        gl_options = ["999 - Unassigned"]

    c1, c2, c3 = st.columns(3)
    d_date = c1.date_input("Ημερομηνία", date.today())
    d_type = c2.selectbox("Τύπος", ["Income", "Expense", "Bill"])
    d_no = c3.text_input("Αρ. Παρ/κου")
    
    c4, c5 = st.columns(2)
    partner = c4.text_input("Συναλλασσόμενος")
    descr = c5.text_input("Αιτιολογία")
    
    # Εδώ είναι το δυναμικό GL
    gl_choice = st.selectbox("Λογιστικός Κωδικός", options=gl_options)

    st.divider()
    st.subheader("💶 Υπολογισμός (Πατήστε Enter μετά το ποσό)")
    
    k1, k2, k3, k4 = st.columns(4)
    net = k1.number_input("Καθαρό (€)", step=10.0, key='calc_net', on_change=update_calc)
    rate = k2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key='calc_vat', on_change=update_calc)
    vat = k3.number_input("ΦΠΑ (€)", value=st.session_state.calc_vat_val, key='disp_v')
    gross = k4.number_input("Σύνολο (€)", value=st.session_state.calc_gross, key='disp_g')
    
    st.divider()
    p1, p2 = st.columns(2)
    pay = p1.selectbox("Πληρωμή", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
    bank = p2.text_input("Λογαριασμός", "Alpha" if pay=="Τράπεζα" else "Ταμείο" if pay=="Μετρητά" else "")
    
    if st.button("💾 Αποθήκευση", type="primary"):
        status = "Unpaid" if pay == "Επί Πιστώσει" else "Paid"
        conn = get_conn()
        conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty, description, gl_code, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d_date, d_no, d_type, partner, descr, gl_choice.split(' - ')[0], st.session_state.calc_net, vat, gross, pay, bank, status))
        conn.commit()
        conn.close()
        st.success("✅ Καταχωρήθηκε!")
        st.session_state.calc_net = 0.0
        st.session_state.calc_vat_val = 0.0
        st.session_state.calc_gross = 0.0
        st.rerun()

# --- LEDGERS ---
elif menu == "📇 Καρτέλες (Ledgers)":
    st.title("📇 Καρτέλες Συναλλασσόμενων")
    conn = get_conn()
    partners = pd.read_sql("SELECT DISTINCT counterparty FROM journal WHERE counterparty IS NOT NULL AND counterparty != '' ORDER BY counterparty", conn)['counterparty'].tolist()
    
    sel = st.selectbox("Επιλογή", partners)
    if sel:
        df = pd.read_sql(f"SELECT * FROM journal WHERE counterparty='{sel}' ORDER BY doc_date", conn)
        balance = df[df['status']=='Unpaid']['amount_gross'].sum()
        st.metric("Ανοιχτό Υπόλοιπο", f"€{balance:,.2f}")
        st.dataframe(df[['doc_date', 'doc_type', 'description', 'amount_gross', 'status', 'gl_code']], use_container_width=True)
    conn.close()

# --- JOURNAL EDIT ---
elif menu == "📚 Αρχείο & Διορθώσεις":
    st.title("📚 Αρχείο & Επεξεργασία")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    
    # Get GL codes for the dropdown editor
    gl_df = pd.read_sql("SELECT code FROM gl_codes", conn)
    gl_list = gl_df['code'].tolist()
    conn.close()
    
    st.info("Διαγραφή: Επιλέξτε αριστερά -> Delete -> Αποθήκευση")
    
    edited = st.data_editor(
        df, num_rows="dynamic", use_container_width=True, hide_index=True,
        column_config={
            "doc_date": st.column_config.DateColumn("Ημ/νία"),
            "amount_net": st.column_config.NumberColumn("Καθαρό"),
            "amount_gross": st.column_config.NumberColumn("Μικτό"),
            "gl_code": st.column_config.SelectboxColumn("GL", options=gl_list)
        }
    )
    
    if st.button("💾 Αποθήκευση Αλλαγών"):
        conn = get_conn()
        conn.execute("DELETE FROM journal")
        
        s_df = edited.copy()
        s_df['doc_date'] = pd.to_datetime(s_df['doc_date']).dt.strftime('%Y-%m-%d')
        s_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.commit()
        conn.close()
        st.success("Updated!")
        st.rerun()

# --- SETTINGS / GL MANAGER ---
elif menu == "⚙️ Ρυθμίσεις & GL":
    st.title("⚙️ Ρυθμίσεις")
    
    tab1, tab2 = st.tabs(["🔢 Λογιστικό Σχέδιο", "🗑️ Reset"])
    
    with tab1:
        st.subheader("Διαχείριση Κωδικών Λογιστικής")
        st.info("Εδώ προσθέτεις ή αλλάζεις τους κωδικούς (π.χ. 100, 200, 64.00).")
        
        conn = get_conn()
        df_gl = pd.read_sql("SELECT * FROM gl_codes ORDER BY code", conn)
        
        edited_gl = st.data_editor(df_gl, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 Ενημέρωση Λογιστικού Σχεδίου"):
            conn.execute("DELETE FROM gl_codes")
            edited_gl.to_sql('gl_codes', conn, if_exists='append', index=False)
            conn.commit()
            st.success("Το Λογιστικό Σχέδιο ενημερώθηκε!")
            st.rerun()
        conn.close()

    with tab2:
        st.error("Προσοχή: Αυτό διαγράφει ΤΑ ΠΑΝΤΑ.")
        if st.button("Διαγραφή Όλων"):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            st.warning("Έγιναν όλα reset. Κάνε Refresh.")
