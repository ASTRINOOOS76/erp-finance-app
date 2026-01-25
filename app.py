import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import io
from datetime import datetime, date

# --- ΒΑΣΙΚΕΣ ΡΥΘΜΙΣΕΙΣ (ΧΩΡΙΣ ΠΕΡΙΕΡΓΑ ΧΡΩΜΑΤΑ) ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")
DB_FILE = "erp_stable.db"

# --- ΣΥΝΔΕΣΗ ΜΕ ΒΑΣΗ ---
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Απλός πίνακας Journal που δουλεύει πάντα
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_date DATE,
        doc_no TEXT,
        doc_type TEXT,
        counterparty TEXT,
        description TEXT,
        category TEXT,
        amount_net REAL,
        vat_amount REAL,
        amount_gross REAL,
        payment_method TEXT,
        bank_account TEXT,
        status TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# --- ΕΛΕΓΧΟΣ ΔΕΔΟΜΕΝΩΝ (ΤΟ ΣΗΜΑΝΤΙΚΟΤΕΡΟ) ---
conn = get_conn()
try:
    row_count = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
except:
    row_count = 0
conn.close()

# ΑΝ ΔΕΝ ΥΠΑΡΧΟΥΝ ΔΕΔΟΜΕΝΑ -> ΖΗΤΑΜΕ EXCEL (ΓΙΑ ΝΑ ΜΗΝ ΧΑΝΕΣΑΙ)
if row_count == 0:
    st.title("⚠️ Επαναφορά Δεδομένων")
    st.warning("Η βάση είναι κενή. Ανέβασε το Excel (Journal) τώρα για να το σώσω μόνιμα.")
    
    uploaded_file = st.file_uploader("Επιλογή Αρχείου Excel", type=['xlsx'])
    
    if uploaded_file:
        try:
            xl = pd.ExcelFile(uploaded_file, engine='openpyxl')
            # Βρίσκουμε το σωστό tab
            sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(uploaded_file, sheet_name=sheet)
            
            # Καθαρισμός Ονομάτων (Trim spaces)
            df.columns = df.columns.str.strip()
            
            # Μετονομασία για σιγουριά
            rename_map = {
                'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 
                'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType',
                'Counterparty': 'counterparty', 'Bank Account': 'bank_account'
            }
            df.rename(columns=rename_map, inplace=True)
            
            conn = get_conn()
            # Εισαγωγή γραμμή-γραμμή για ασφάλεια
            count = 0
            for _, row in df.iterrows():
                # Ημερομηνία
                d_date = pd.to_datetime(row.get('DocDate'), errors='coerce').strftime('%Y-%m-%d')
                
                conn.execute('''INSERT INTO journal (
                    doc_date, doc_no, doc_type, counterparty, description, category,
                    amount_net, vat_amount, amount_gross, payment_method, bank_account, status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', 
                (d_date, str(row.get('DocNo','')), str(row.get('DocType','')), str(row.get('counterparty','')), 
                 str(row.get('Description','')), str(row.get('Category','')), 
                 float(row.get('Amount (Net)',0)), float(row.get('VAT Amount',0)), float(row.get('Amount (Gross)',0)),
                 str(row.get('Payment Method','')), str(row.get('bank_account','')), str(row.get('Status',''))))
                count += 1
            
            conn.commit()
            conn.close()
            st.success(f"✅ Περάστηκαν {count} εγγραφές! Πατήστε το κουμπί από κάτω.")
            if st.button("🚀 Είσοδος στην Εφαρμογή"):
                st.rerun()
                
        except Exception as e:
            st.error(f"Σφάλμα στο αρχείο: {e}")
            st.stop()
    else:
        st.stop()

# --- LOGIN (ΑΠΛΟ) ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("🔐 Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if (u=="admin" and p=="admin123") or (u=="user" and p=="1234"):
            st.session_state.logged_in = True
            st.session_state.username = u
            st.rerun()
    st.stop()

# --- ΚΥΡΙΩΣ ΕΦΑΡΜΟΓΗ ---
st.sidebar.title("SalesTree ERP")
st.sidebar.write(f"👤 {st.session_state.username}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

menu = st.sidebar.radio("Μενού", ["📊 Dashboard", "📝 Εγγραφές", "🏦 Ταμείο", "⏳ Οφειλές", "⚙️ Ρυθμίσεις"])

# Φόρτωση δεδομένων για χρήση παντού
conn = get_conn()
df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
conn.close()
df['doc_date'] = pd.to_datetime(df['doc_date'])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Εικόνα Επιχείρησης")
    
    # Τρέχον Έτος
    cy = datetime.now().year
    df_y = df[df['doc_date'].dt.year == cy]
    
    inc = df_y[df_y['doc_type']=='Income']['amount_net'].sum()
    exp = df_y[df_y['doc_type'].isin(['Expense','Bill'])]['amount_net'].sum()
    profit = inc - exp
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Πωλήσεις (Net)", f"€{inc:,.0f}")
    c2.metric("Έξοδα", f"€{exp:,.0f}")
    c3.metric("Κέρδος", f"€{profit:,.0f}")
    
    st.divider()
    
    # Γράφημα
    monthly = df_y.copy()
    monthly['Month'] = monthly['doc_date'].dt.strftime('%Y-%m')
    grp = monthly.groupby(['Month', 'doc_type'])['amount_net'].sum().reset_index()
    
    fig = px.bar(grp, x='Month', y='amount_net', color='doc_type', barmode='group')
    st.plotly_chart(fig, use_container_width=True)

# --- ΕΓΓΡΑΦΕΣ ---
elif menu == "📝 Εγγραφές":
    st.title("📝 Διαχείριση Εγγραφών")
    
    # Φίλτρα
    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Αναζήτηση")
    
    df_show = df.copy()
    if search:
        df_show = df_show[df_show.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        
    # Editor
    edited_df = st.data_editor(
        df_show, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True,
        column_config={
            "doc_date": st.column_config.DateColumn("Ημερομηνία"),
            "amount_net": st.column_config.NumberColumn("Καθαρό"),
            "amount_gross": st.column_config.NumberColumn("Μικτό"),
            "doc_type": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill", "Equity Distribution"]),
            "status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"]),
            "bank_account": st.column_config.SelectboxColumn("Λογαριασμός", options=["Alpha Bank", "Eurobank", "Piraeus", "National Bank", "Revolut", "Ταμείο Μετρητών"])
        }
    )
    
    if st.button("💾 Αποθήκευση Αλλαγών"):
        # Απλή και σίγουρη αποθήκευση: Σβήνουμε και ξαναγράφουμε για να μην γίνονται διπλότυπα
        conn = get_conn()
        conn.execute("DELETE FROM journal")
        
        # Μετατροπή ημερομηνίας σε string για SQLite
        save_df = edited_df.copy()
        save_df['doc_date'] = save_df['doc_date'].dt.strftime('%Y-%m-%d')
        
        save_df.to_sql('journal', conn, if_exists='append', index=False)
        conn.close()
        st.success("✅ Τα δεδομένα αποθηκεύτηκαν!")
        st.rerun()

# --- ΤΑΜΕΙΟ ---
elif menu == "🏦 Ταμείο":
    st.title("🏦 Ταμείο & Τράπεζες")
    
    df_paid = df[df['status'] == 'Paid'].copy()
    df_paid['flow'] = df_paid.apply(lambda x: x['amount_gross'] if x['doc_type']=='Income' else -x['amount_gross'], axis=1)
    
    # Διαχωρισμός
    df_paid['bank_account'] = df_paid['bank_account'].fillna("Άγνωστο").astype(str)
    mask_cash = df_paid['bank_account'].str.contains("Ταμείο|Cash", case=False)
    
    df_cash = df_paid[mask_cash]
    df_bank = df_paid[~mask_cash]
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("💶 Ταμείο (Μετρητά)")
        total_cash = df_cash['flow'].sum()
        st.metric("Σύνολο Μετρητών", f"€{total_cash:,.2f}")
        
    with c2:
        st.subheader("🏦 Τραπεζικοί Λογαριασμοί")
        if not df_bank.empty:
            gr = df_bank.groupby('bank_account')['flow'].sum().reset_index()
            for i, r in gr.iterrows():
                st.info(f"**{r['bank_account']}**: €{r['flow']:,.2f}")
        else:
            st.info("Δεν βρέθηκαν κινήσεις τραπέζης.")

# --- ΟΦΕΙΛΕΣ ---
elif menu == "⏳ Οφειλές":
    st.title("⏳ Οφειλές (Aging)")
    
    unpaid_in = df[(df['doc_type'] == 'Income') & (df['status'] == 'Unpaid')]
    unpaid_out = df[(df['doc_type'].isin(['Expense', 'Bill'])) & (df['status'] == 'Unpaid')]
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Μας Χρωστάνε (Πελάτες)")
        st.dataframe(unpaid_in[['doc_date', 'counterparty', 'amount_gross']], use_container_width=True)
        st.metric("Σύνολο", f"€{unpaid_in['amount_gross'].sum():,.2f}")
        
    with c2:
        st.subheader("Χρωστάμε (Προμηθευτές)")
        st.dataframe(unpaid_out[['doc_date', 'counterparty', 'amount_gross']], use_container_width=True)
        st.metric("Σύνολο", f"€{unpaid_out['amount_gross'].sum():,.2f}")

# --- SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    
    if st.button("🗑️ Hard Reset (Διαγραφή Βάσης)"):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
            st.error("Η βάση διαγράφηκε. Κάνε Refresh για να ανεβάσεις ξανά το Excel.")
