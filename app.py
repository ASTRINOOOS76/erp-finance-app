import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, date

# --- 1. CONFIG ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")
DB_FILE = "erp_clean.db"

# --- 2. CSS - ΚΑΘΑΡΟ (ΧΩΡΙΣ ΧΡΩΜΑΤΙΣΤΕΣ ΠΑΡΕΜΒΑΣΕΙΣ) ---
# Αφαιρέσαμε όλα τα background colors για να μην χαλάει το θέμα σου
st.markdown("""
<style>
    /* Κάνουμε τα inputs να ξεχωρίζουν λίγο */
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div {
        border: 1px solid #ccc;
    }
    /* Κάνουμε τα κουμπιά πιο έντονα */
    .stButton>button {
        border: 2px solid #ccc;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE & LOGIC ---
if 'calc_net' not in st.session_state: st.session_state.calc_net = 0.0
if 'calc_vat_rate' not in st.session_state: st.session_state.calc_vat_rate = 24
if 'calc_vat_val' not in st.session_state: st.session_state.calc_vat_val = 0.0
if 'calc_gross' not in st.session_state: st.session_state.calc_gross = 0.0

def recalculate_totals():
    net = st.session_state.calc_net
    rate = st.session_state.calc_vat_rate
    vat_amt = net * (rate / 100)
    gross = net + vat_amt
    st.session_state.calc_vat_val = round(vat_amt, 2)
    st.session_state.calc_gross = round(gross, 2)

def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty_name TEXT, description TEXT, category TEXT, gl_account INTEGER,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, type TEXT, vat_no TEXT, phone TEXT
    )''')
    conn.commit()
    conn.close()

# Τρέχουμε τη δημιουργία πινάκων
init_db()

# --- 4. DATA CHECK & UPLOAD (Η ΛΥΣΗ ΓΙΑ ΤΙΣ 0 ΕΓΓΡΑΦΕΣ) ---
conn = get_conn()
row_count = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
conn.close()

# ΑΝ Η ΒΑΣΗ ΕΙΝΑΙ ΑΔΕΙΑ -> ΔΕΙΧΝΟΥΜΕ ΟΘΟΝΗ ΦΟΡΤΩΣΗΣ
if row_count == 0:
    st.title("⚠️ Η Βάση Δεδομένων είναι Άδεια")
    st.warning("Δεν βρέθηκαν εγγραφές. Παρακαλώ ανεβάστε το αρχείο Excel (Journal) για να ξεκινήσουμε.")
    
    uploaded_file = st.file_uploader("Επιλέξτε το αρχείο Excel", type=['xlsx'])
    
    if uploaded_file:
        try:
            with st.spinner("Γίνεται εισαγωγή δεδομένων..."):
                xl = pd.ExcelFile(uploaded_file, engine='openpyxl')
                sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
                df = pd.read_excel(uploaded_file, sheet_name=sheet)
                
                # Καθαρισμός Ονομάτων Στηλών
                df.columns = df.columns.str.strip()
                rename_map = {
                    'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 
                    'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType',
                    'Counterparty': 'counterparty_name', 'Bank Account': 'bank_account'
                }
                df.rename(columns=rename_map, inplace=True)
                
                conn = get_conn()
                c = conn.cursor()
                
                count_ins = 0
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
                    
                    # Αυτόματη δημιουργία Πελάτη
                    p_name = str(row.get('counterparty_name','')).strip()
                    if p_name and p_name != 'nan':
                        pt = "Customer" if row.get('DocType') == 'Income' else "Supplier"
                        c.execute("INSERT OR IGNORE INTO partners (name, type) VALUES (?,?)", (p_name, pt))
                    count_ins += 1
                
                conn.commit()
                conn.close()
            st.success(f"✅ Επιτυχία! Περάστηκαν {count_ins} εγγραφές.")
            if st.button("🚀 Είσοδος στην Εφαρμογή"):
                st.rerun()
                
        except Exception as e:
            st.error(f"Σφάλμα στο αρχείο: {e}")
            st.stop()
    else:
        st.stop() # Σταματάμε εδώ αν δεν έχει ανέβει αρχείο

# --- 5. LOGIN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("🔐 SalesTree ERP Login")
    col1, col2 = st.columns([1,2])
    with col1:
        u = st.text_input("User")
        p = st.text_input("Pass", type="password")
        if st.button("Enter"):
            if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"):
                st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
    st.stop()

# --- 6. MAIN APP ---
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.write(f"👤 **{st.session_state.username}**")
st.sidebar.divider()
menu = st.sidebar.radio("ΜΕΝΟΥ", ["📊 Dashboard", "📝 Νέα Εγγραφή", "📇 Μητρώο", "📚 Journal", "💵 Ταμείο & Τράπεζες", "⚙️ Ρυθμίσεις"])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Dashboard")
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
        monthly = df_y.copy()
        monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
        grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
        fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group')
        st.plotly_chart(fig, use_container_width=True)

# --- VOUCHER ENTRY ---
elif menu == "📝 Νέα Εγγραφή":
    st.title("📝 Νέα Εγγραφή (Calculator)")
    
    conn = get_conn()
    partners = [r[0] for r in conn.execute("SELECT name FROM partners ORDER BY name").fetchall()]
    conn.close()
    
    with st.container():
        c1, c2, c3 = st.columns(3)
        d_date = c1.date_input("Ημερομηνία", date.today())
        d_type = c2.selectbox("Τύπος", ["Income", "Expense", "Bill"])
        d_no = c3.text_input("Αρ. Παρ/κου")
        
        c4, c5 = st.columns(2)
        if partners: partner = c4.selectbox("Συναλλασσόμενος", partners)
        else: partner = c4.text_input("Συναλλασσόμενος (Νέος)")
        descr = c5.text_input("Αιτιολογία")
        
        st.divider()
        st.subheader("💶 Υπολογισμός Ποσών")
        
        # CALCULATOR
        kc1, kc2, kc3, kc4 = st.columns(4)
        net = kc1.number_input("Καθαρή Αξία (€)", step=10.0, key="calc_net", on_change=recalculate_totals)
        rate = kc2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key="calc_vat_rate", on_change=recalculate_totals)
        vat = kc3.number_input("Ποσό ΦΠΑ (€)", value=st.session_state.calc_vat_val, key="calc_vat_val_input")
        gross = kc4.number_input("Σύνολο (€)", value=st.session_state.calc_gross, key="calc_gross_input")
        
        st.divider()
        c9, c10 = st.columns(2)
        pay_method = c9.selectbox("Τρόπος", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
        bank = c10.text_input("Τράπεζα", "Alpha Bank" if pay_method=="Τράπεζα" else "Ταμείο" if pay_method=="Μετρητά" else "")
        
        if st.button("💾 Αποθήκευση", type="primary"):
            if abs(gross - (net + vat)) > 0.1:
                st.error("❌ Τα ποσά δεν συμφωνούν!")
            else:
                status = "Unpaid" if pay_method == "Επί Πιστώσει" else "Paid"
                conn = get_conn()
                conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty_name, description, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (d_date, d_no, d_type, partner, descr, net, vat, gross, pay_method, bank, status))
                conn.execute("INSERT OR IGNORE INTO partners (name, type) VALUES (?, 'Unknown')", (partner,))
                conn.commit()
                conn.close()
                st.success("✅ Αποθηκεύτηκε!")
                st.session_state.calc_net = 0.0
                st.session_state.calc_vat_val = 0.0
                st.session_state.calc_gross = 0.0
                st.rerun()

# --- MASTER DATA ---
elif menu == "📇 Μητρώο":
    st.title("📇 Μητρώο Συναλλασσόμενων")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM partners", conn)
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("Αποθήκευση Αλλαγών"):
        conn.execute("DELETE FROM partners")
        edited.to_sql('partners', conn, if_exists='append', index=False)
        st.success("Saved!")
    conn.close()

# --- JOURNAL ---
elif menu == "📚 Journal":
    st.title("📚 Αρχείο & Διορθώσεις")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    
    st.info("💡 Μπορείς να διορθώσεις απευθείας στον πίνακα.")
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
    
    if st.button("💾 Ενημέρωση Βάσης"):
        conn = get_conn()
        conn.execute("DELETE FROM journal")
        edited_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.commit()
        conn.close()
        st.success("✅ Ενημερώθηκε!")

# --- TREASURY ---
elif menu == "💵 Ταμείο & Τράπεζες":
    st.title("💵 Διαθέσιμα")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal WHERE status='Paid'", conn)
    conn.close()
    
    df['signed_amount'] = df.apply(lambda x: x['amount_gross'] if x['doc_type']=='Income' else -x['amount_gross'], axis=1)
    df['bank_account'] = df['bank_account'].fillna('Unknown').astype(str)
    
    mask_cash = df['bank_account'].str.contains("Ταμείο|Cash", case=False)
    df_cash = df[mask_cash]
    df_bank = df[~mask_cash]
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💶 Ταμείο (Μετρητά)")
        st.metric("Σύνολο", f"€{df_cash['signed_amount'].sum():,.2f}")
    with c2:
        st.subheader("🏦 Τράπεζες")
        gr = df_bank.groupby('bank_account')['signed_amount'].sum().reset_index()
        for i, r in gr.iterrows():
            st.info(f"**{r['bank_account']}**: €{r['signed_amount']:,.2f}")

# --- SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    if st.button("🗑️ Hard Reset (Διαγραφή Όλων)"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.warning("Η βάση διαγράφηκε. Κάνε Refresh τη σελίδα.")
