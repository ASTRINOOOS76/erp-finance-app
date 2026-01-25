import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, date

# --- 1. ΡΥΘΜΙΣΕΙΣ & DB CONFIG ---
st.set_page_config(page_title="SalesTree Pro ERP", layout="wide", page_icon="🚀")
DB_FILE = "erp.db"

# --- CSS PRO THEME ---
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    div[data-testid="metric-container"] {
        background-color: #ffffff; border-left: 5px solid #4CAF50;
        padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton>button { width: 100%; border-radius: 5px; }
    h1, h2, h3 { color: #2c3e50; font-family: 'Segoe UI', sans-serif; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ENGINE (SQLITE) ---
def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Master Data
    c.execute('''CREATE TABLE IF NOT EXISTS counterparties (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, type TEXT)''')

    # Transactions
    c.execute('''CREATE TABLE IF NOT EXISTS journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_no TEXT, doc_date DATE, doc_type TEXT,
                    counterparty TEXT, description TEXT, category TEXT,
                    amount_net REAL, vat_amount REAL, amount_gross REAL,
                    payment_method TEXT, bank_account TEXT, status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()

# --- 3. MIGRATION (SMART VERSION) ---
def migrate_from_excel():
    if os.path.exists(DB_FILE):
        conn = get_connection()
        try:
            count = conn.execute("SELECT count(*) FROM journal").fetchone()[0]
            conn.close()
            if count > 0: return # Έχουμε δεδομένα
        except:
            pass

    # Ψάχνουμε το Excel
    excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
    if not excel_files: 
        st.warning("⚠️ Δεν βρέθηκε αρχείο .xlsx για μετάπτωση.")
        return

    file_to_load = excel_files[0]
    st.toast(f"⏳ Προσπάθεια ανάγνωσης: {file_to_load}...", icon="🔄")
    
    try:
        # Χρήση ExcelFile για να δούμε τα tabs πρώτα
        xl = pd.ExcelFile(file_to_load, engine='openpyxl')
        sheet_names = xl.sheet_names
        
        # Λογική Επιλογής Tab
        if "Journal" in sheet_names:
            target_sheet = "Journal"
        else:
            target_sheet = sheet_names[0] # Παίρνουμε το πρώτο διαθέσιμο
            st.warning(f"⚠️ Δεν βρέθηκε καρτέλα 'Journal'. Χρησιμοποιείται η καρτέλα: '{target_sheet}'")

        df = pd.read_excel(file_to_load, sheet_name=target_sheet)
        
        # Καθαρισμός Στηλών (αντιστοίχιση ονομάτων Excel -> DB)
        # Φτιάχνουμε τα columns αν λείπουν
        expected_cols = ['DocNo', 'DocDate', 'DocType', 'Counterparty', 'Description', 'Category', 
                         'Amount (Net)', 'VAT Amount', 'Amount (Gross)', 'Payment Method', 'Bank Account', 'Status']
        
        for col in expected_cols:
            if col not in df.columns:
                df[col] = "" # Γεμίζουμε με κενά αν λείπει στήλη

        conn = get_connection()
        c = conn.cursor()
        
        # Εισαγωγή στη Βάση
        rows_inserted = 0
        for _, row in df.iterrows():
            # Μετατροπή ημερομηνίας
            try:
                d_date = pd.to_datetime(row['DocDate']).strftime('%Y-%m-%d')
            except:
                d_date = date.today().strftime('%Y-%m-%d')

            c.execute('''INSERT INTO journal (
                doc_no, doc_date, doc_type, counterparty, description, category,
                amount_net, vat_amount, amount_gross, payment_method, bank_account, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', 
            (str(row['DocNo']), d_date, str(row['DocType']), str(row['Counterparty']), 
             str(row['Description']), str(row['Category']), 
             float(pd.to_numeric(row['Amount (Net)'], errors='coerce') or 0), 
             float(pd.to_numeric(row['VAT Amount'], errors='coerce') or 0), 
             float(pd.to_numeric(row['Amount (Gross)'], errors='coerce') or 0),
             str(row['Payment Method']), str(row['Bank Account']), str(row['Status'])))
            
            rows_inserted += 1
            
            # Auto-Master Data
            if row['Counterparty']:
                c.execute("INSERT OR IGNORE INTO counterparties (name, type) VALUES (?, ?)", (str(row['Counterparty']), 'Unknown'))
            if row['Category']:
                c.execute("INSERT OR IGNORE INTO categories (name, type) VALUES (?, ?)", (str(row['Category']), 'General'))
                
        conn.commit()
        conn.close()
        st.success(f"✅ Επιτυχία! Μεταφέρθηκαν {rows_inserted} εγγραφές στη βάση δεδομένων.")
        
    except Exception as e:
        st.error(f"❌ Η μετάπτωση απέτυχε. Λεπτομέρειες: {e}")

# Αρχικοποίηση
init_db()
migrate_from_excel()

# --- 4. DATA ACCESS LAYER ---
def load_journal():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM journal ORDER BY doc_date DESC", conn)
    conn.close()
    return df

def add_transaction(data):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO journal (
                doc_no, doc_date, doc_type, counterparty, description, category,
                amount_net, vat_amount, amount_gross, payment_method, bank_account, status
              ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
              (data['doc_no'], data['doc_date'], data['doc_type'], data['counterparty'], 
               data['description'], data['category'], data['net'], data['vat'], data['gross'],
               data['pay_method'], data['bank'], data['status']))
    conn.commit()
    conn.close()

def get_master_list(table):
    conn = get_connection()
    try:
        res = [r[0] for r in conn.execute(f"SELECT name FROM {table} ORDER BY name").fetchall()]
    except:
        res = []
    conn.close()
    return res

# --- 5. UI COMPONENTS ---
def sidebar_menu():
    st.sidebar.title("🚀 SalesTree Pro")
    return st.sidebar.radio("Module", ["Dashboard", "Νέα Συναλλαγή", "Journal / Data", "Master Data"])

# --- MAIN APP ---
menu = sidebar_menu()

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Dashboard (SQL Powered)")
    df = load_journal()
    
    if not df.empty:
        df['doc_date'] = pd.to_datetime(df['doc_date'])
        current_year = datetime.now().year
        df_curr = df[df['doc_date'].dt.year == current_year]
        
        inc = df_curr[df_curr['doc_type'] == 'Income']['amount_net'].sum()
        exp = df_curr[df_curr['doc_type'].isin(['Expense', 'Bill'])]['amount_net'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Έσοδα Έτους", f"€{inc:,.2f}")
        c2.metric("Έξοδα Έτους", f"€{exp:,.2f}")
        c3.metric("Κέρδος (EBITDA)", f"€{inc - exp:,.2f}")
        
        st.divider()
        c1, c2 = st.columns([2,1])
        with c1:
            df_curr['month'] = df_curr['doc_date'].dt.strftime('%Y-%m')
            grp = df_curr.groupby(['month', 'doc_type'])['amount_net'].sum().reset_index()
            st.plotly_chart(px.bar(grp, x='month', y='amount_net', color='doc_type', barmode='group'), use_container_width=True)
    else:
        st.info("Η βάση είναι κενή. Ξεκινήστε τις καταχωρήσεις ή ελέγξτε το Excel.")

# --- NEW TRANSACTION ---
elif menu == "Νέα Συναλλαγή":
    st.title("➕ Νέα Εγγραφή")
    
    with st.form("new_txn_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        doc_date = c1.date_input("Ημερομηνία", value=date.today())
        doc_no = c2.text_input("Αρ. Παραστατικού")
        doc_type = c3.selectbox("Τύπος", ["Income", "Expense", "Bill", "Equity Distribution"])
        
        c4, c5 = st.columns(2)
        parties = get_master_list("counterparties")
        cats = get_master_list("categories")
        
        counterparty = c4.selectbox("Συναλλασσόμενος", parties) if parties else c4.text_input("Συναλλασσόμενος (Νέος)")
        category = c5.selectbox("Κατηγορία", cats) if cats else c5.text
