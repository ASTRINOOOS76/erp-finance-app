import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, date

# --- 1. CONFIG ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")
DB_FILE = "erp_final.db"

# --- 2. CSS - ΤΟ ΑΠΟΛΥΤΟ ΚΑΘΑΡΟ (ΑΣΠΡΟ/ΜΑΥΡΟ) ---
st.markdown("""
<style>
    /* Φόντο κάτασπρο */
    .stApp {
        background-color: #ffffff;
    }
    
    /* Sidebar Ανοιχτό Γκρι με ΜΑΥΡΑ γράμματα */
    [data-testid="stSidebar"] {
        background-color: #f0f2f6;
        border-right: 2px solid #ccc;
    }
    [data-testid="stSidebar"] * {
        color: #000000 !important;
        font-weight: 600;
    }

    /* Κείμενα εφαρμογής - ΜΑΥΡΑ */
    h1, h2, h3, h4, p, label, div, span, li {
        color: #000000 !important;
        font-family: Arial, sans-serif;
    }

    /* Κουτάκια (Metrics) - Με περίγραμμα για να ξεχωρίζουν */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 2px solid #000000;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 3px 3px 0px rgba(0,0,0,0.2);
    }

    /* Πίνακες - Καθαροί */
    [data-testid="stDataFrame"] {
        border: 1px solid #000000;
    }

    /* Κουμπιά - Μαύρα με άσπρα γράμματα */
    .stButton>button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 1px solid #000000;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #333333 !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 5px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #e0e0e0;
        color: #000000 !important;
        border: 1px solid #000000;
        font-weight: bold;
    }
    .stTabs [aria-selected="true"] {
        background-color: #000000 !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE ENGINE & MIGRATION ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # 1. Πίνακας Κινήσεων
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty_name TEXT, description TEXT, category TEXT, gl_account INTEGER,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT
    )''')
    
    # 2. Πίνακας Πελατών/Προμηθευτών (Master Data)
    c.execute('''CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, type TEXT, vat_no TEXT, phone TEXT
    )''')
    
    conn.commit()
    
    # --- MIGRATION LOGIC (ΕΔΩ ΕΙΝΑΙ Η ΔΙΟΡΘΩΣΗ ΓΙΑ ΤΑ ΜΗΔΕΝΙΚΑ ΔΕΔΟΜΕΝΑ) ---
    # Ελέγχουμε αν είναι άδεια η βάση
    c.execute("SELECT count(*) FROM journal")
    count = c.fetchone()[0]
    
    if count == 0:
        # Ψάχνουμε Excel
        excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
        if excel_files:
            try:
                file_path = excel_files[0]
                # st.toast(f"⏳ Φόρτωση δεδομένων από: {file_path}...", icon="🔄")
                
                xl = pd.ExcelFile(file_path, engine='openpyxl')
                sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
                df = pd.read_excel(file_path, sheet_name=sheet)
                
                # Καθαρισμός Στηλών
                df.columns = df.columns.str.strip()
                rename_map = {
                    'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 
                    'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType',
                    'Counterparty': 'counterparty_name', 'Bank Account': 'bank_account'
                }
                df.rename(columns=rename_map, inplace=True)
                
                # Default values
                cols_check = ['amount_net', 'amount_gross', 'vat_amount', 'gl_account']
                for col in cols_check:
                    if col not in df.columns and col.title() in df.columns: # Check capitalization
                         df.rename(columns={col.title(): col}, inplace=True)
                
                # Εισαγωγή Journal
                for _, row in df.iterrows():
                    d_date = pd.to_datetime(row.get('DocDate'), errors='coerce').strftime('%Y-%m-%d')
                    
                    c.execute('''INSERT INTO journal (
                        doc_date, doc_no, doc_type, counterparty_name, description, category,
                        amount_net, vat_amount, amount_gross, payment_method, bank_account, status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', 
                    (d_date, str(row.get('DocNo','')), str(row.get('DocType','')), str(row.get('counterparty_name','')), 
                     str(row.get('Description','')), str(row.get('Category','')), 
                     float(row.get('Amount (Net)',0)), float(row.get('VAT Amount',0)), float(row.get('Amount (Gross)',0)),
                     str(row.get('Payment Method','')), str(row.get('bank_account','')), str(row.get('Status',''))))
                    
                    # Αυτόματη δημιουργία Πελάτη στο Μητρώο
                    partner = str(row.get('counterparty_name','')).strip()
                    if partner and partner != 'nan':
                        p_type = "Customer" if row.get('DocType') == 'Income' else "Supplier"
                        c.execute("INSERT OR IGNORE INTO partners (name, type) VALUES (?,?)", (partner, p_type))
                
                conn.commit()
                # st.toast("✅ Επιτυχής φόρτωση δεδομένων!", icon="info")
            except Exception as e:
                st.error(f"Migration Error: {e}")
                
    conn.close()

init_db()

# --- 4. AUTH ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.title("🔐 Login")
        u = st.text_input("User")
        p = st.text_input("Pass", type="password")
        if st.button("Enter"):
            if u=="admin" and p=="admin123":
                st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
            elif u=="user" and p=="1234":
                st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
            else: st.error("Lathos kodikos")
    st.stop()

# --- 5. SIDEBAR ---
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.write(f"User: **{st.session_state.username}**")
st.sidebar.divider()

menu = st.sidebar.radio("ΜΕΝΟΥ", [
    "📊 Dashboard",
    "📝 Νέα Εγγραφή (Voucher)",
    "📇 Μητρώο (Πελάτες)",
    "📚 Journal (Αρχείο)",
    "💵 Ταμείο & Τράπεζες",
    "⚙️ Ρυθμίσεις"
])

# --- 6. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Γενική Εικόνα (Dashboard)")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()

    if not df.empty:
        df['doc_date'] = pd.to_datetime(df['doc_date'])
        cy = datetime.now().year
        df_y = df[df['doc_date'].dt.year == cy]
        
        inc = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
        exp = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
        ebitda = inc - exp
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Πωλήσεις (Net)", f"€{inc:,.0f}")
        c2.metric("Έξοδα", f"€{exp:,.0f}")
        c3.metric("Κέρδος", f"€{ebitda:,.0f}")

        st.divider()
        
        c4, c5 = st.columns(2)
        with c4:
            st.subheader("Μηνιαία Κίνηση")
            monthly = df_y.copy()
            monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
            grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
            # Απλό γράφημα με έντονα χρώματα
            fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group', 
                         color_discrete_map={'Income':'blue', 'Expense':'red', 'Bill':'red'})
            st.plotly_chart(fig, use_container_width=True)

# --- 7. VOUCHER ENTRY ---
elif menu == "📝 Νέα Εγγραφή (Voucher)":
    st.title("📝 Νέα Εγγραφή")
    
    conn = get_conn()
    partners = [r[0] for r in conn.execute("SELECT name FROM partners ORDER BY name").fetchall()]
    conn.close()
    
    with st.form("voucher", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        d_date = c1.date_input("Ημερομηνία", date.today())
        d_type = c2.selectbox("Τύπος", ["Income", "Expense", "Bill"])
        d_no = c3.text_input("Αρ. Παρ/κου")
        
        c4, c5 = st.columns(2)
        # Αν η λίστα είναι κενή, δώσε text input
        if partners:
            partner = c4.selectbox("Συναλλασσόμενος", partners)
        else:
            partner = c4.text_input("Συναλλασσόμενος (Νέος)")
            
        descr = c5.text_input("Αιτιολογία")
        
        c6, c7, c8 = st.columns(3)
        net = c6.number_input("Καθαρό", step=10.0)
        vat = c7.number_input("ΦΠΑ", step=1.0)
        gross = c8.number_input("Σύνολο", step=10.0)
        
        c9, c10 = st.columns(2)
        pay_method = c9.selectbox("Τρόπος", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
        bank = c10.text_input("Τράπεζα (αν ισχύει)", "Alpha Bank" if pay_method=="Τράπεζα" else "Ταμείο" if pay_method=="Μετρητά" else "")
        
        if st.form_submit_button("💾 Αποθήκευση"):
            status = "Unpaid" if pay_method == "Επί Πιστώσει" else "Paid"
            conn = get_conn()
            conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty_name, description, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (d_date, d_no, d_type, partner, descr, net, vat, gross, pay_method, bank, status))
            # Auto-add partner if new
            conn.execute("INSERT OR IGNORE INTO partners (name, type) VALUES (?, 'Unknown')", (partner,))
            conn.commit()
            conn.close()
            st.success("Αποθηκεύτηκε!")

# --- 8. MASTER DATA ---
elif menu == "📇 Μητρώο (Πελάτες)":
    st.title("📇 Μητρώο Συναλλασσόμενων")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM partners", conn)
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("Save Changes"):
        # Simple Logic: Overwrite table (for demo simplicity)
        conn.execute("DELETE FROM partners")
        edited.to_sql('partners', conn, if_exists='append', index=False)
        st.success("Saved!")
    conn.close()

# --- 9. JOURNAL ---
elif menu == "📚 Journal (Αρχείο)":
    st.title("📚 Αρχείο Κινήσεων")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    
    search = st.text_input("🔍 Αναζήτηση")
    if search:
        df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        
    st.dataframe(df, use_container_width=True)

# --- 10. TREASURY ---
elif menu == "💵 Ταμείο & Τράπεζες":
    st.title("💵 Διαθέσιμα")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal WHERE status='Paid'", conn)
    conn.close()
    
    # Logic
    df['signed_amount'] = df.apply(lambda x: x['amount_gross'] if x['doc_type']=='Income' else -x['amount_gross'], axis=1)
    
    # Split
    df['bank_account'] = df['bank_account'].fillna('Unknown').astype(str)
    mask_cash = df['bank_account'].str.contains("Ταμείο|Cash", case=False)
    
    df_cash = df[mask_cash]
    df_bank = df[~mask_cash]
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("💶 Ταμείο (Μετρητά)")
        if not df_cash.empty:
            cash_total = df_cash['signed_amount'].sum()
            st.metric("Σύνολο Μετρητών", f"€{cash_total:,.2f}")
        else:
            st.info("Κανένα στοιχείο")
            
    with c2:
        st.subheader("🏦 Τραπεζικοί Λογαριασμοί")
        if not df_bank.empty:
            gr = df_bank.groupby('bank_account')['signed_amount'].sum().reset_index()
            for i, r in gr.iterrows():
                st.info(f"**{r['bank_account']}**: €{r['signed_amount']:,.2f}")
        else:
            st.info("Κανένα στοιχείο")

# --- 11. SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    if st.button("🗑️ Hard Reset (Διαγραφή Βάσης)"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.error("Βάση διεγράφη. Κάνε Refresh.")
