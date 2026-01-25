import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, date

# --- 1. CONFIG ---
st.set_page_config(page_title="SalesTree ERP Enterprise", layout="wide", page_icon="🏢")
DB_FILE = "erp_enterprise.db"

# --- 2. PROFESSIONAL CSS (HIGH VISIBILITY) ---
st.markdown("""
<style>
    /* Γενικό Layout - Λευκό & Καθαρό */
    .stApp { background-color: #ffffff; color: #000000; }
    
    /* Sidebar - Σοβαρό Γκρι */
    section[data-testid="stSidebar"] {
        background-color: #f1f5f9;
        border-right: 1px solid #cbd5e1;
    }
    section[data-testid="stSidebar"] * {
        color: #0f172a !important; /* Σκούρο μπλε/μαύρο */
        font-weight: 600;
    }

    /* Metrics - Κάρτες με έντονο περίγραμμα */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        border-left: 5px solid #2563eb; /* Royal Blue */
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-radius: 8px;
    }
    div[data-testid="metric-container"] label { color: #64748b !important; } /* Label Gray */
    div[data-testid="metric-container"] div { color: #0f172a !important; font-weight: 800; } /* Value Black */

    /* Inputs - Ξεκάθαρα πλαίσια */
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #94a3b8 !important;
        border-radius: 5px;
    }

    /* Buttons - Έντονα */
    .stButton>button {
        background-color: #0f172a !important; /* Midnight Blue */
        color: #ffffff !important;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #334155 !important;
    }

    /* Tables */
    [data-testid="stDataFrame"] { border: 1px solid #e2e8f0; }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC & STATE ---
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

# --- 4. DATABASE & MIGRATION ---
def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # 1. Journal Table
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty_name TEXT, description TEXT, category TEXT, gl_account INTEGER,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT
    )''')
    
    # 2. Partners Table
    c.execute('''CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, type TEXT, vat_no TEXT, phone TEXT
    )''')
    conn.commit()
    
    # --- AUTO IMPORT EXCEL IF DB IS EMPTY ---
    c.execute("SELECT count(*) FROM journal")
    if c.fetchone()[0] == 0:
        excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
        if excel_files:
            try:
                path = excel_files[0]
                xl = pd.ExcelFile(path, engine='openpyxl')
                sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
                df = pd.read_excel(path, sheet_name=sheet)
                
                # Cleanup Columns
                df.columns = df.columns.str.strip()
                rename_map = {
                    'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 
                    'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType',
                    'Counterparty': 'counterparty_name', 'Bank Account': 'bank_account'
                }
                df.rename(columns=rename_map, inplace=True)
                
                # Fill missing
                if 'VAT Amount' not in df.columns: df['VAT Amount'] = 0
                
                # Insert
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
                    
                    # Auto Create Partner
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
        st.title("🔐 Enterprise Login")
        u = st.text_input("User"); p = st.text_input("Pass", type="password")
        if st.button("Enter"):
            if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"):
                st.session_state.logged_in=True; st.session_state.username=u; st.rerun()
    st.stop()

# --- 6. SIDEBAR MENU ---
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.markdown(f"👤 **{st.session_state.username}**")
st.sidebar.divider()

menu = st.sidebar.radio("MAIN MENU", [
    "📊 Executive Dashboard",
    "📝 Νέα Εγγραφή (Calculator)",
    "📊 Οικονομικές Αναφορές (ΦΠΑ & P&L)", # <--- Η ΜΕΓΑΛΗ ΑΝΑΒΑΘΜΙΣΗ
    "📇 Καρτέλες & Μητρώο",                # <--- Η ΜΕΓΑΛΗ ΑΝΑΒΑΘΜΙΣΗ
    "📚 Journal (Αρχείο)",
    "💵 Ταμείο & Τράπεζες",
    "⚙️ Ρυθμίσεις"
])

# --- 7. EXECUTIVE DASHBOARD ---
if menu == "📊 Executive Dashboard":
    st.title("📊 Financial Overview")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()

    if not df.empty:
        df['doc_date'] = pd.to_datetime(df['doc_date'])
        cy = datetime.now().year
        df_y = df[df['doc_date'].dt.year == cy]
        
        # Financials
        inc = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
        exp = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
        vat_net = df_y[df_y['doc_type']=='Income']['vat_amount'].sum() - df_y[df_y['doc_type']!='Income']['vat_amount'].sum()
        ebitda = inc - exp
        
        # Top Cards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Πωλήσεις (Net)", f"€{inc:,.0f}", delta="Έσοδα")
        c2.metric("Λειτουργικά Έξοδα", f"€{exp:,.0f}", delta="-Έξοδα", delta_color="inverse")
        c3.metric("Κέρδος (EBITDA)", f"€{ebitda:,.0f}")
        c4.metric("ΦΠΑ Πληρωτέο", f"€{vat_net:,.0f}", delta="Προς Εφορία" if vat_net>0 else "Επιστροφή", delta_color="inverse")

        st.divider()

        # Outstanding
        rec = df[(df['doc_type']=='Income')&(df['status']=='Unpaid')]['amount_gross'].sum()
        pay = df[(df['doc_type']!='Income')&(df['status']=='Unpaid')]['amount_gross'].sum()
        
        c5, c6 = st.columns(2)
        c5.info(f"💰 **Απαιτήσεις από Πελάτες:** €{rec:,.2f}")
        c6.error(f"💸 **Υποχρεώσεις σε Προμηθευτές:** €{pay:,.2f}")

        # Charts
        st.subheader("🗓️ Μηνιαία Πορεία")
        monthly = df_y.copy()
        monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
        grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
        fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group',
                     color_discrete_map={'Income':'#2563eb', 'Expense':'#ef4444', 'Bill':'#ef4444'})
        st.plotly_chart(fig, use_container_width=True)

# --- 8. SMART VOUCHER ENTRY ---
elif menu == "📝 Νέα Εγγραφή (Calculator)":
    st.title("📝 Νέα Εγγραφή")
    
    conn = get_conn()
    partners = [r[0] for r in conn.execute("SELECT name FROM partners ORDER BY name").fetchall()]
    conn.close()
    
    with st.container():
        st.markdown("### 1. Στοιχεία Συναλλαγής")
        c1, c2, c3 = st.columns(3)
        d_date = c1.date_input("Ημερομηνία", date.today())
        d_type = c2.selectbox("Τύπος", ["Income", "Expense", "Bill"])
        d_no = c3.text_input("Αρ. Παρ/κου")
        
        c4, c5 = st.columns(2)
        if partners: partner = c4.selectbox("Συναλλασσόμενος", partners)
        else: partner = c4.text_input("Συναλλασσόμενος (Νέος)")
        descr = c5.text_input("Αιτιολογία")
        
        st.markdown("### 2. Αυτόματος Υπολογισμός ΦΠΑ")
        kc1, kc2, kc3, kc4 = st.columns(4)
        net = kc1.number_input("Καθαρή Αξία (€)", step=10.0, key="calc_net", on_change=recalculate_totals)
        rate = kc2.selectbox("ΦΠΑ %", [24, 13, 6, 0], key="calc_vat_rate", on_change=recalculate_totals)
        vat = kc3.number_input("Ποσό ΦΠΑ (€)", value=st.session_state.calc_vat_val, key="calc_vat_val_input")
        gross = kc4.number_input("Σύνολο (€)", value=st.session_state.calc_gross, key="calc_gross_input")
        
        st.markdown("### 3. Πληρωμή")
        c9, c10 = st.columns(2)
        pay_method = c9.selectbox("Τρόπος", ["Επί Πιστώσει", "Μετρητά", "Τράπεζα"])
        bank = c10.text_input("Λογαριασμός", "Alpha Bank" if pay_method=="Τράπεζα" else "Ταμείο" if pay_method=="Μετρητά" else "")
        
        if st.button("💾 Αποθήκευση Εγγραφής", type="primary"):
            if abs(gross - (net + vat)) > 0.1:
                st.error("❌ Ασυμφωνία Ποσών!")
            else:
                status = "Unpaid" if pay_method == "Επί Πιστώσει" else "Paid"
                conn = get_conn()
                conn.execute("INSERT INTO journal (doc_date, doc_no, doc_type, counterparty_name, description, amount_net, vat_amount, amount_gross, payment_method, bank_account, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (d_date, d_no, d_type, partner, descr, net, vat, gross, pay_method, bank, status))
                conn.execute("INSERT OR IGNORE INTO partners (name, type) VALUES (?, 'Unknown')", (partner,))
                conn.commit()
                conn.close()
                st.success("✅ Καταχωρήθηκε!")
                st.session_state.calc_net = 0.0
                st.session_state.calc_vat_val = 0.0
                st.session_state.calc_gross = 0.0
                st.rerun()

# --- 9. NEW REPORTING MODULE (VAT & P&L) ---
elif menu == "📊 Οικονομικές Αναφορές (ΦΠΑ & P&L)":
    st.title("📊 Οικονομικές Αναφορές")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()
    
    tab_vat, tab_pl = st.tabs(["🏛️ Αναφορά ΦΠΑ", "📈 Αποτελέσματα Χρήσης"])
    
    # --- VAT REPORT ---
    with tab_vat:
        st.subheader("Περιοδική Δήλωση ΦΠΑ (Εκτίμηση)")
        
        # Calculate
        vat_collected = df[df['doc_type'] == 'Income']['vat_amount'].sum()
        vat_paid = df[df['doc_type'].isin(['Expense', 'Bill'])]['vat_amount'].sum()
        vat_balance = vat_collected - vat_paid
        
        # Display Cards
        c1, c2, c3 = st.columns(3)
        c1.metric("ΦΠΑ Εκροών (Εισπράξεις)", f"€{vat_collected:,.2f}", "+")
        c2.metric("ΦΠΑ Εισροών (Δαπάνες)", f"€{vat_paid:,.2f}", "-")
        c3.metric("Τελικό Προς Απόδοση", f"€{vat_balance:,.2f}", 
                  delta="Πληρωμή" if vat_balance > 0 else "Επιστροφή", delta_color="inverse")
        
        st.divider()
        st.write("🔎 **Αναλυτικό Βιβλίο ΦΠΑ**")
        vat_df = df[df['vat_amount'] > 0][['doc_date', 'doc_no', 'counterparty_name', 'doc_type', 'amount_net', 'vat_amount']]
        st.dataframe(vat_df, use_container_width=True)

    # --- P&L REPORT ---
    with tab_pl:
        st.subheader("Κατάσταση Αποτελεσμάτων (Profit & Loss)")
        
        # Pivot Table
        pl_data = df[df['doc_type'].isin(['Income', 'Expense', 'Bill'])]
        if not pl_data.empty:
            pl = pl_data.groupby(['category', 'doc_type'])['amount_net'].sum().unstack(fill_value=0)
            if 'Income' not in pl.columns: pl['Income'] = 0
            
            # Add Total Column
            pl['Total'] = pl['Income'] - pl.get('Expense', 0) - pl.get('Bill', 0)
            
            st.dataframe(pl.style.format("€{:,.2f}"), use_container_width=True)
        else:
            st.info("Δεν υπάρχουν δεδομένα για P&L.")

# --- 10. LEDGERS (ΚΑΡΤΕΛΕΣ) ---
elif menu == "📇 Καρτέλες & Μητρώο":
    st.title("📇 Διαχείριση Συναλλασσόμενων")
    
    tab_card, tab_master = st.tabs(["🔍 Καρτέλες (Ledgers)", "📝 Επεξεργασία Μητρώου"])
    
    conn = get_conn()
    
    with tab_card:
        st.subheader("Καρτέλα Πελάτη / Προμηθευτή")
        partners = pd.read_sql("SELECT name FROM partners ORDER BY name", conn)['name'].tolist()
        
        sel_partner = st.selectbox("Επιλογή Συναλλασσόμενου", partners)
        if sel_partner:
            # Get Transactions
            ledger = pd.read_sql(f"SELECT * FROM journal WHERE counterparty_name='{sel_partner}' ORDER BY doc_date", conn)
            
            if not ledger.empty:
                # Calc Balance
                balance = 0
                for _, row in ledger.iterrows():
                    amt = row['amount_gross']
                    if row['doc_type'] == 'Income': # Customer
                         if row['status'] == 'Unpaid': balance += amt
                    else: # Supplier
                         if row['status'] == 'Unpaid': balance += amt # Simplified logic
                
                c1, c2 = st.columns([1,3])
                c1.metric("Υπόλοιπο", f"€{balance:,.2f}")
                c2.dataframe(ledger[['doc_date', 'doc_type', 'description', 'amount_gross', 'status']], use_container_width=True)
            else:
                st.info("Δεν βρέθηκαν κινήσεις.")

    with tab_master:
        df_p = pd.read_sql("SELECT * FROM partners", conn)
        edited = st.data_editor(df_p, num_rows="dynamic", use_container_width=True)
        if st.button("💾 Save Partners"):
            conn.execute("DELETE FROM partners")
            edited.to_sql('partners', conn, if_exists='append', index=False)
            st.success("Μητρώο Ενημερώθηκε!")
    conn.close()

# --- 11. JOURNAL & TREASURY (STANDARD) ---
elif menu == "📚 Journal (Αρχείο)":
    st.title("📚 Αρχείο Κινήσεων")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
    if st.button("💾 Ενημέρωση Βάσης"):
        conn = get_conn()
        conn.execute("DELETE FROM journal")
        edited_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.commit()
        conn.close()
        st.success("Updated!")

elif menu == "💵 Ταμείο & Τράπεζες":
    st.title("💵 Διαθέσιμα")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal WHERE status='Paid'", conn)
    conn.close()
    
    df['signed_amount'] = df.apply(lambda x: x['amount_gross'] if x['doc_type']=='Income' else -x['amount_gross'], axis=1)
    df['bank_account'] = df['bank_account'].fillna('Unknown').astype(str)
    
    mask_cash = df['bank_account'].str.contains("Ταμείο|Cash", case=False)
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💶 Ταμείο")
        st.metric("Μετρητά", f"€{df[mask_cash]['signed_amount'].sum():,.2f}")
    with c2:
        st.subheader("🏦 Τράπεζες")
        gr = df[~mask_cash].groupby('bank_account')['signed_amount'].sum().reset_index()
        for i, r in gr.iterrows():
            st.info(f"**{r['bank_account']}**: €{r['signed_amount']:,.2f}")

# --- 12. SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    if st.button("🗑️ Hard Reset"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.error("Deleted. Refresh page.")
