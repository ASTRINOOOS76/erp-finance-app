import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, date

# --- 1. CONFIG & PRO CSS ---
st.set_page_config(page_title="SalesTree ERP Pro", layout="wide", page_icon="🏦")
DB_FILE = "erp_pro.db"

st.markdown("""
<style>
    /* Γενικό Layout - Clean Professional */
    .stApp { background-color: #f8fafc; }
    
    /* Sidebar - Corporate Dark */
    [data-testid="stSidebar"] {
        background-color: #1e293b;
        border-right: 1px solid #334155;
    }
    [data-testid="stSidebar"] * { color: #f1f5f9 !important; }

    /* Headings */
    h1, h2, h3 { color: #0f172a; font-family: 'Segoe UI', sans-serif; font-weight: 700; }
    
    /* KPIs / Metrics */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border-left: 5px solid #0ea5e9; /* Sky Blue */
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="metric-container"] label { color: #64748b !important; font-size: 0.9rem; }
    div[data-testid="metric-container"] div { color: #0f172a !important; font-weight: 800; }

    /* Buttons */
    .stButton>button {
        background-color: #0f172a; color: white; border: none;
        padding: 0.5rem 1rem; border-radius: 6px; font-weight: 600;
        transition: all 0.2s;
    }
    .stButton>button:hover { background-color: #334155; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }

    /* Forms & Inputs */
    .stTextInput>div>div>input { border-radius: 4px; border: 1px solid #cbd5e1; }
    .stSelectbox>div>div>div { border-radius: 4px; border: 1px solid #cbd5e1; }

    /* Success/Error Messages */
    .stAlert { border-radius: 6px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ENGINE (ADVANCED) ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # 1. Transactions (Journal)
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE, doc_no TEXT, doc_type TEXT,
        counterparty_id INTEGER, counterparty_name TEXT,
        description TEXT, category TEXT, gl_account INTEGER,
        amount_net REAL, vat_amount REAL, amount_gross REAL,
        payment_method TEXT, bank_account TEXT, status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 2. Master Data: Partners (Πελάτες/Προμηθευτές)
    c.execute('''CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        type TEXT, -- Customer, Supplier, Both
        vat_no TEXT,
        phone TEXT,
        balance REAL DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()

init_db()

# --- 3. HELPER FUNCTIONS ---
def get_partners(p_type=None):
    conn = get_conn()
    query = "SELECT name FROM partners"
    if p_type:
        query += f" WHERE type = '{p_type}' OR type = 'Both'"
    df = pd.read_sql(query, conn)
    conn.close()
    return df['name'].tolist()

def update_partner_balance(name, amount):
    conn = get_conn()
    c = conn.cursor()
    # Αν είναι έσοδο, αυξάνει το υπόλοιπο (μας χρωστάει). Αν έξοδο, μειώνει (τον ξεχρεώνουμε/πιστώνουμε)
    # Εδώ κάνουμε απλή λογική: Balance = Net Receivables
    pass # Θα το κάνουμε dynamically στα reports
    conn.close()

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
                st.session_state.logged_in=True
                st.session_state.username=u
                st.rerun()
            else: st.error("Access Denied")
    st.stop()

# --- 5. SIDEBAR MENU ---
st.sidebar.title("🚀 SalesTree ERP")
st.sidebar.caption(f"Logged in as: {st.session_state.username}")
st.sidebar.divider()

menu = st.sidebar.radio("MODULES", [
    "📊 Executive Dashboard",
    "📝 Νέα Συναλλαγή (Voucher)",
    "📇 Μητρώο (Master Data)",
    "📚 Γενική Λογιστική (Journal)",
    "🔍 Καρτέλες & Οφειλές",
    "💵 Treasury & Banks",
    "⚙️ Ρυθμίσεις"
])

# --- 6. EXECUTIVE DASHBOARD ---
if menu == "📊 Executive Dashboard":
    st.title("📊 Financial Overview")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()

    if not df.empty:
        df['doc_date'] = pd.to_datetime(df['doc_date'])
        cy = datetime.now().year
        df_y = df[df['doc_date'].dt.year == cy]
        
        # Financial Logic
        income = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
        expenses = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
        ebitda = income - expenses
        margin = (ebitda/income*100) if income>0 else 0
        
        # Outstanding
        receivables = df[(df['doc_type']=='Income') & (df['status']=='Unpaid')]['amount_gross'].sum()
        payables = df[(df['doc_type'].isin(['Expense','Bill'])) & (df['status']=='Unpaid')]['amount_gross'].sum()

        # Top Row - P&L
        st.subheader("📈 Αποτελέσματα Χρήσης (YTD)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Πωλήσεις (Net)", f"€{income:,.0f}", delta="Έσοδα")
        c2.metric("Λειτουργικά Έξοδα", f"€{expenses:,.0f}", delta="-Έξοδα", delta_color="inverse")
        c3.metric("EBITDA", f"€{ebitda:,.0f}", delta=f"{margin:.1f}%")
        c4.metric("ΦΠΑ Προς Απόδοση", f"€{(df_y[df_y['doc_type']=='Income']['vat_amount'].sum() - df_y[df_y['doc_type']!='Income']['vat_amount'].sum()):,.0f}")

        st.divider()

        # Bottom Row - Liquidity
        st.subheader("💧 Ρευστότητα & Οφειλές")
        c5, c6, c7 = st.columns(3)
        c5.metric("Απαιτήσεις από Πελάτες", f"€{receivables:,.0f}", "Αναμένεται είσπραξη")
        c6.metric("Υποχρεώσεις σε Προμηθευτές", f"€{payables:,.0f}", "Πρέπει να πληρωθούν", delta_color="inverse")
        
        cash = df[df['status']=='Paid'].apply(lambda x: x['amount_gross'] if x['doc_type']=='Income' else -x['amount_gross'], axis=1).sum()
        c7.metric("Ταμειακά Διαθέσιμα", f"€{cash:,.0f}", "Cash on Hand")

        # Charts
        c8, c9 = st.columns(2)
        with c8:
            monthly = df_y.copy()
            monthly['mo'] = monthly['doc_date'].dt.strftime('%Y-%m')
            grp = monthly.groupby(['mo','doc_type'])['amount_net'].sum().reset_index()
            fig = px.bar(grp, x='mo', y='amount_net', color='doc_type', barmode='group', title='Μηνιαία Εξέλιξη', color_discrete_map={'Income':'#0ea5e9', 'Expense':'#ef4444'})
            st.plotly_chart(fig, use_container_width=True)

# --- 7. VOUCHER ENTRY (PROFESSIONAL FORM) ---
elif menu == "📝 Νέα Συναλλαγή (Voucher)":
    st.title("📝 Καταχώρηση Παραστατικού")
    
    with st.container():
        st.markdown("### 1. Στοιχεία Παραστατικού")
        
        with st.form("voucher_form", clear_on_submit=True):
            col1, col2, col3, col4 = st.columns(4)
            
            d_date = col1.date_input("Ημερομηνία", date.today())
            d_type = col2.selectbox("Τύπος Κίνησης", ["Income", "Expense", "Bill", "Equity Distribution"])
            d_no = col3.text_input("Αρ. Παραστατικού (π.χ. INV-001)")
            
            # Δυναμική φόρτωση από Master Data
            partner_type = "Customer" if d_type == "Income" else "Supplier"
            partners_list = get_partners(partner_type if d_type != "Equity Distribution" else None)
            
            if not partners_list:
                st.warning(f"⚠️ Δεν βρέθηκαν {partner_type}s στο Μητρώο. Πήγαινε στο μενού 'Μητρώο' να τους ανοίξεις!")
                partner = col4.text_input("Συναλλασσόμενος (Χειροκίνητα)")
            else:
                partner = col4.selectbox("Συναλλασσόμενος", partners_list)

            st.markdown("### 2. Οικονομικά Στοιχεία")
            c1, c2, c3 = st.columns(3)
            net = c1.number_input("Καθαρή Αξία (€)", min_value=0.0, step=10.0)
            vat = c2.number_input("ΦΠΑ (€)", min_value=0.0, step=1.0)
            gross = c3.number_input("Σύνολο (€)", min_value=0.0, step=10.0)
            
            st.markdown("### 3. Ταξινόμηση & Πληρωμή")
            c4, c5, c6 = st.columns(3)
            category = c4.text_input("Κατηγορία / Κέντρο Κόστους", placeholder="π.χ. Ενοίκια, Πωλήσεις Χονδρικής")
            pay_method = c5.selectbox("Τρόπος Πληρωμής", ["Επί Πιστώσει", "Μετρητά", "Έμβασμα", "Κάρτα"])
            
            # Smart Bank Logic
            status = "Unpaid" if pay_method == "Επί Πιστώσει" else "Paid"
            bank_acc = ""
            if pay_method == "Μετρητά": bank_acc = "Ταμείο Μετρητών"
            elif pay_method in ["Έμβασμα", "Κάρτα"]: bank_acc = "Όψεως (Main)"
            
            descr = st.text_input("Αιτιολογία / Σχόλια")

            # VALIDATION & SUBMIT
            submitted = st.form_submit_button("💾 Καταχώρηση Εγγραφής")
            
            if submitted:
                # Validation Logic
                if abs(gross - (net + vat)) > 0.1:
                    st.error(f"❌ Λάθος Ποσά! Καθαρό ({net}) + ΦΠΑ ({vat}) ≠ Σύνολο ({gross})")
                elif not partner:
                    st.error("❌ Λείπει ο Συναλλασσόμενος")
                else:
                    # Save Logic
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute('''INSERT INTO journal (
                        doc_date, doc_no, doc_type, counterparty_name, description, category,
                        amount_net, vat_amount, amount_gross, payment_method, bank_account, status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', 
                    (d_date, d_no, d_type, partner, descr, category, net, vat, gross, pay_method, bank_acc, status))
                    conn.commit()
                    conn.close()
                    st.success("✅ Το παραστατικό καταχωρήθηκε επιτυχώς!")

# --- 8. MASTER DATA (CRM LIGHT) ---
elif menu == "📇 Μητρώο (Master Data)":
    st.title("📇 Μητρώο Συναλλασσόμενων")
    
    tab1, tab2 = st.tabs(["📋 Λίστα & Επεξεργασία", "➕ Νέος Συναλλασσόμενος"])
    
    conn = get_conn()
    
    with tab1:
        df_p = pd.read_sql("SELECT * FROM partners", conn)
        edited_p = st.data_editor(df_p, num_rows="dynamic", use_container_width=True)
        # Εδώ θα μπορούσαμε να προσθέσουμε Update logic, για το demo είναι read/view mainly
    
    with tab2:
        with st.form("new_partner"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Επωνυμία")
            vat_no = c2.text_input("ΑΦΜ")
            p_type = st.selectbox("Τύπος", ["Customer", "Supplier", "Both"])
            phone = st.text_input("Τηλέφωνο")
            
            if st.form_submit_button("Δημιουργία Καρτέλας"):
                try:
                    c = conn.cursor()
                    c.execute("INSERT INTO partners (name, type, vat_no, phone) VALUES (?,?,?,?)", (name, p_type, vat_no, phone))
                    conn.commit()
                    st.success(f"Ο {name} δημιουργήθηκε!")
                except Exception as e:
                    st.error(f"Σφάλμα (π.χ. υπάρχει ήδη): {e}")
    conn.close()

# --- 9. JOURNAL (GRID) ---
elif menu == "📚 Γενική Λογιστική (Journal)":
    st.title("📚 Ημερολόγιο Εγγραφών")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    
    # Advanced Filters
    with st.expander("🔍 Φίλτρα Αναζήτησης", expanded=True):
        c1, c2, c3 = st.columns(3)
        search = c1.text_input("Αναζήτηση (Όνομα/Αιτιολογία)")
        f_type = c2.multiselect("Τύπος", df['doc_type'].unique())
        f_status = c3.multiselect("Κατάσταση", ["Paid", "Unpaid"])
    
    if search:
        df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
    if f_type:
        df = df[df['doc_type'].isin(f_type)]
    if f_status:
        df = df[df['status'].isin(f_status)]
        
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Export
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Εξαγωγή σε Excel", buf, "Journal_Export.xlsx")

# --- 10. CUSTOMER/SUPPLIER CARDS (LEDGERS) ---
elif menu == "🔍 Καρτέλες & Οφειλές":
    st.title("🔍 Καρτέλες Συναλλασσόμενων")
    
    conn = get_conn()
    partners = pd.read_sql("SELECT name FROM partners", conn)['name'].tolist()
    
    # Αν δεν υπάρχουν στο Master Data, πάρε από το Journal
    if not partners:
        partners = pd.read_sql("SELECT DISTINCT counterparty_name FROM journal", conn)['counterparty_name'].tolist()
    
    sel_partner = st.selectbox("Επιλογή Καρτέλας (Πελάτη/Προμηθευτή)", partners)
    
    if sel_partner:
        df = pd.read_sql(f"SELECT * FROM journal WHERE counterparty_name = '{sel_partner}' ORDER BY doc_date", conn)
        
        if not df.empty:
            # Υπολογισμός Υπολοίπου (Running Balance)
            # Αν είναι Πελάτης (Income): Χρέωση (+), Πληρωμή (-)
            # Αν είναι Προμηθευτής (Bill): Πίστωση (+), Πληρωμή (-)
            # Εδώ κάνουμε μια γενική προσέγγιση: Income/Bill = Αυξάνει χρέος, Payment = Μειώνει
            
            balance = 0.0
            total_debts = 0.0
            
            for index, row in df.iterrows():
                if row['status'] == 'Unpaid':
                    balance += row['amount_gross']
            
            c1, c2 = st.columns(2)
            c1.metric(f"Τρέχον Υπόλοιπο {sel_partner}", f"€{balance:,.2f}", "Ανοιχτό Ποσό")
            
            st.subheader("Αναλυτική Κίνηση")
            st.dataframe(df[['doc_date', 'doc_type', 'description', 'amount_gross', 'status']], use_container_width=True)
        else:
            st.info("Δεν υπάρχουν κινήσεις για αυτόν τον συναλλασσόμενο.")
    conn.close()

# --- 11. TREASURY ---
elif menu == "💵 Treasury & Banks":
    st.title("💵 Διαχείριση Διαθεσίμων")
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM journal WHERE status='Paid'", conn)
    conn.close()
    
    # Logic: Income adds to bank, Expense subtracts
    df['flow'] = df.apply(lambda x: x['amount_gross'] if x['doc_type']=='Income' else -x['amount_gross'], axis=1)
    
    # Group by Bank
    banks = df.groupby('bank_account')['flow'].sum().reset_index()
    
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.subheader("🏦 Υπόλοιπα Λογαριασμών")
        for i, row in banks.iterrows():
            name = row['bank_account'] if row['bank_account'] else "Unassigned"
            val = row['flow']
            st.info(f"**{name}**: €{val:,.2f}")
            
    with c2:
        st.subheader("📉 Ροή Χρήματος (Cashflow)")
        df['mo'] = pd.to_datetime(df['doc_date']).dt.strftime('%Y-%m')
        cf = df.groupby('mo')['flow'].sum().reset_index()
        fig = px.line(cf, x='mo', y='flow', markers=True, title="Καθαρή Ροή ανά Μήνα")
        st.plotly_chart(fig, use_container_width=True)

# --- 12. SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις Συστήματος")
    st.write("System Admin Tools")
    
    if st.button("🗑️ Hard Reset Database (ΠΡΟΣΟΧΗ)"):
        os.remove(DB_FILE)
        st.error("Η βάση διαγράφηκε. Κάνε refresh.")
