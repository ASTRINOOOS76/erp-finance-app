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

# --- 2. CSS - ΚΑΘΑΡΟ DESIGN ---
st.markdown("""
<style>
    .stApp { background-color: #ffffff; }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #f0f2f6;
        border-right: 2px solid #ccc;
    }
    [data-testid="stSidebar"] * { color: #000000 !important; font-weight: 600; }

    /* Inputs & Text */
    h1, h2, h3, p, label, div, span { color: #000000 !important; font-family: Arial, sans-serif; }
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        background-color: #ffffff; color: #000000; border: 1px solid #444;
    }

    /* Metrics */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 2px solid #000000;
        padding: 10px;
        box-shadow: 3px 3px 0px rgba(0,0,0,0.2);
    }

    /* Buttons */
    .stButton>button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 1px solid #000000;
        font-weight: bold;
    }
    .stButton>button:hover { background-color: #333333 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC & CALCULATIONS ---
# Αρχικοποίηση μεταβλητών για τους υπολογισμούς
if 'calc_net' not in st.session_state: st.session_state.calc_net = 0.0
if 'calc_vat_rate' not in st.session_state: st.session_state.calc_vat_rate = 24
if 'calc_vat_val' not in st.session_state: st.session_state.calc_vat_val = 0.0
if 'calc_gross' not in st.session_state: st.session_state.calc_gross = 0.0

def recalculate_totals():
    """Αυτόματος υπολογισμός ΦΠΑ και Συνόλου"""
    net = st.session_state.calc_net
    rate = st.session_state.calc_vat_rate
    
    vat_amt = net * (rate / 100)
    gross = net + vat_amt
    
    st.session_state.calc_vat_val = round(vat_amt, 2)
    st.session_state.calc_gross = round(gross, 2)

# --- 4. DATABASE ENGINE ---
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
    
    # Check if empty -> Load Excel
    c.execute("SELECT count(*) FROM journal")
    if c.fetchone()[0] == 0:
        excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
        if excel_files:
            try:
                path = excel_files[0]
                xl = pd.ExcelFile(path, engine='openpyxl')
                sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
                df = pd.read_excel(path, sheet_name=sheet)
                
                df.columns = df.columns.str.strip()
                rename_map = {
                    'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 
                    'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType',
                    'Counterparty': 'counterparty_name', 'Bank Account': 'bank_account'
                }
                df.rename(columns=rename_map, inplace=True)
                
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
                    
                    p_name = str(row.get('counterparty_name','')).strip()
                    if p_name and p_name != 'nan':
                        pt = "Customer" if row.get('DocType') == 'Income' else "Supplier"
                        c.execute("INSERT OR IGNORE INTO partners (name, type) VALUES (?,?)", (p_name, pt))
                conn.commit()
            except: pass
    conn.close()

init_db()

# --- 5. AUTH ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.title("🔐 Login")
        u = st.text_input("User"); p = st.text_input("Pass", type="password")
        if st.button("Enter"):
            if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"):
                st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
    st.stop()

# --- 6. SIDEBAR ---
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.write(f"User: **{st.session_state.username}**")
st.sidebar.divider()
menu = st.sidebar.radio("ΜΕΝΟΥ", ["📊 Dashboard", "📝 Νέα Εγγραφή", "📇 Μητρώο", "📚 Journal", "💵 Ταμείο & Τράπεζες", "⚙️ Ρυθμίσεις"])

# --- 7. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Γενική Εικόνα")
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

# --- 8. VOUCHER ENTRY (AUTO CALC) ---
elif menu == "📝 Νέα Εγγραφή":
    st.title("📝 Νέα Εγγραφή (Με Αυτόματο Υπολογισμό)")
    
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
        st.subheader("💶 Οικονομικά (Αυτόματος Υπολογισμός)")
        
        # --- CALCULATOR SECTION ---
        kc1, kc2, kc3, kc4 = st.columns(4)
        
        # Input Net -> Triggers Recalculation
        net = kc1.number_input("Καθαρή Αξία (€)", step=10.0, key="calc_net", on_change=recalculate_totals)
        
        # Input Rate -> Triggers Recalculation
        rate = kc2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key="calc_vat_rate", on_change=recalculate_totals)
        
        # Outputs (Displays values from Session State)
        vat = kc3.number_input("Ποσό ΦΠΑ (€)", value=st.session_state.calc_vat_val, key="calc_vat_val_input")
        gross = kc4.number_input("Σύνολο (€)", value=st.session_state.calc_gross, key="calc_gross_input")
        
        st.caption("ℹ️ Γράψε το Καθαρό και διάλεξε ΦΠΑ%. Τα υπόλοιπα θα συμπληρωθούν αυτόματα!")
        st.divider()

        c9, c10 = st.columns(2)
        pay_method = c9.selectbox("Τρόπος", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
        bank = c10.text_input("Τράπεζα", "Alpha Bank" if pay_method=="Τράπεζα" else "Ταμείο" if pay_method=="Μετρητά" else "")
        
        if st.button("💾 Αποθήκευση Εγγραφής", type="primary"):
            # Final Validation
            if abs(gross - (net + vat)) > 0.1:
                st.error(f"❌ Προσοχή! Τα ποσά δεν συμφωνούν: {net} + {vat} != {gross}")
            else:
                status = "Unpaid" if pay_method == "Επί Πιστώσει" else "Paid"
                conn = get_conn()
                conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty_name, description, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (d_date, d_no, d_type, partner, descr, net, vat, gross, pay_method, bank, status))
                conn.execute("INSERT OR IGNORE INTO partners (name, type) VALUES (?, 'Unknown')", (partner,))
                conn.commit()
                conn.close()
                st.success("✅ Η εγγραφή αποθηκεύτηκε!")
                
                # Reset values
                st.session_state.calc_net = 0.0
                st.session_state.calc_vat_val = 0.0
                st.session_state.calc_gross = 0.0
                st.rerun()

# --- 9. MASTER DATA ---
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

# --- 10. JOURNAL & EDITING ---
elif menu == "📚 Journal":
    st.title("📚 Αρχείο & Διορθώσεις")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    
    st.info("💡 Μπορείς να διορθώσεις απευθείας στον πίνακα. Το σύστημα θα ελέγξει τα ποσά πριν την αποθήκευση.")
    
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
    
    if st.button("💾 Ενημέρωση Βάσης"):
        # Έλεγχος πριν την αποθήκευση
        errors = []
        for idx, row in edited_df.iterrows():
            n, v, g = row['amount_net'], row['vat_amount'], row['amount_gross']
            if abs(g - (n + v)) > 0.5: # Ανοχή 50 λεπτά
                errors.append(f"Γραμμή {idx+1}: Net({n}) + VAT({v}) != Gross({g})")
        
        if errors:
            st.error("⚠️ Βρέθηκαν λάθη στα ποσά! Διορθώστε τα πριν την αποθήκευση:")
            for e in errors: st.write(e)
        else:
            conn = get_conn()
            conn.execute("DELETE FROM journal") # Full overwrite logic for simplicity
            edited_df.to_sql('journal', conn, if_exists='append', index=False)
            conn.commit()
            conn.close()
            st.success("✅ Η βάση ενημερώθηκε επιτυχώς!")

# --- 11. TREASURY ---
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

# --- 12. SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    if st.button("🗑️ Hard Reset"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.error("Deleted. Refresh page.")
