import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, date

# --- 1. ΡΥΘΜΙΣΕΙΣ ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")
DB_FILE = "erp.db"

# --- CSS (Όπως σου άρεσε) ---
st.markdown("""
<style>
    .stApp { background-color: #f4f6f9; }
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #ddd;
        padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #007bff; color: white; }
    .stButton>button:hover { background-color: #0056b3; color: white; }
</style>
""", unsafe_allow_html=True)

# --- 2. ΔΙΑΧΕΙΡΙΣΗ ΒΑΣΗΣ (DATABASE) ---
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_and_migrate():
    """Ελέγχει αν υπάρχει βάση. Αν όχι, διαβάζει το Excel και τη φτιάχνει."""
    if os.path.exists(DB_FILE):
        return # Όλα καλά, η βάση υπάρχει

    # Αν δεν υπάρχει βάση, ψάχνουμε το Excel
    excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
    
    if not excel_files:
        st.warning("⚠️ Δεν βρέθηκε βάση (erp.db) ούτε Excel για αρχική φόρτωση.")
        return

    # Διάβασμα Excel και αποθήκευση σε SQLite
    try:
        file_path = excel_files[0]
        st.toast(f"⏳ Μετατροπή του {file_path} σε Βάση Δεδομένων...", icon="🔄")
        
        # Προσπάθεια εύρεσης του σωστού Tab
        xl = pd.ExcelFile(file_path, engine='openpyxl')
        sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
        
        df = pd.read_excel(file_path, sheet_name=sheet)
        
        # Καθαρισμός ημερομηνιών για να είναι συμβατές με DB
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce').dt.strftime('%Y-%m-%d')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Αποθήκευση
        conn = get_connection()
        df.to_sql('journal', conn, if_exists='replace', index=False)
        conn.close()
        st.success("✅ Η μετάπτωση ολοκληρώθηκε! Πλέον δουλεύουμε με Βάση Δεδομένων.")
        st.rerun() # Επανεκκίνηση για να φορτώσει τα νέα δεδομένα
        
    except Exception as e:
        st.error(f"Σφάλμα κατά τη μετάπτωση: {e}")

# Τρέχουμε τον έλεγχο κατά την εκκίνηση
init_and_migrate()

# --- 3. ΦΟΡΤΩΣΗ & ΑΠΟΘΗΚΕΥΣΗ ---
def load_data():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM journal", conn)
        
        # Μετατροπές τύπων για να παίζει σωστά το Grid
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
        numeric_cols = ['Amount (Net)', 'Amount (Gross)', 'VAT Amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        conn.close()
        return df
    except:
        conn.close()
        return pd.DataFrame() # Κενό αν γίνει λάθος

def save_data(df_to_save):
    try:
        conn = get_connection()
        # Μετατροπή ημερομηνιών σε string πάλι για την SQLite
        save_copy = df_to_save.copy()
        save_copy['DocDate'] = save_copy['DocDate'].dt.strftime('%Y-%m-%d')
        save_copy['Payment Date'] = save_copy['Payment Date'].dt.strftime('%Y-%m-%d')
        
        save_copy.to_sql('journal', conn, if_exists='replace', index=False)
        conn.close()
        st.toast("✅ Τα δεδομένα αποθηκεύτηκαν μόνιμα!", icon="💾")
    except Exception as e:
        st.error(f"Αδυναμία αποθήκευσης: {e}")

# --- 4. UI ΕΦΑΡΜΟΓΗΣ ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50)
st.sidebar.title("SalesTree ERP")

# Φόρτωση Δεδομένων
df = load_data()

if df.empty:
    st.info("Δεν υπάρχουν δεδομένα. Ανέβασε το Excel σου στο φάκελο για να ξεκινήσουμε.")
    st.stop()

# Global Filters
years = sorted(df['DocDate'].dt.year.dropna().unique().astype(int), reverse=True)
if not years: years = [2025] # Fallback
selected_year = st.sidebar.selectbox("Έτος", years)

df_year = df[df['DocDate'].dt.year == selected_year]

# Menu
menu = st.sidebar.radio("Μενού", ["📊 Dashboard", "📝 Εγγραφές & Επεξεργασία", "🏦 Treasury", "⏳ Οφειλές"])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title(f"📊 Εικόνα {selected_year}")
    
    inc = df_year[df_year['DocType'] == 'Income']['Amount (Net)'].sum()
    exp = df_year[df_year['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    profit = inc - exp
    
    # Cashflow (Paid only)
    paid_in = df_year[(df_year['Status']=='Paid') & (df_year['DocType']=='Income')]['Amount (Gross)'].sum()
    paid_out = df_year[(df_year['Status']=='Paid') & (df_year['DocType']!='Income')]['Amount (Gross)'].sum()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Πωλήσεις", f"€{inc:,.0f}")
    c2.metric("Έξοδα", f"€{exp:,.0f}")
    c3.metric("Κέρδος", f"€{profit:,.0f}")
    c4.metric("Ταμείο (Cash)", f"€{(paid_in-paid_out):,.0f}")
    
    st.divider()
    
    c1, c2 = st.columns([2,1])
    with c1:
        mon = df_year.copy()
        mon['Month'] = mon['DocDate'].dt.strftime('%Y-%m')
        grp = mon.groupby(['Month', 'DocType'])['Amount (Net)'].sum().reset_index()
        st.plotly_chart(px.bar(grp, x='Month', y='Amount (Net)', color='DocType', barmode='group'), use_container_width=True)
    with c2:
        exp_df = df_year[df_year['DocType'].isin(['Expense', 'Bill'])]
        if not exp_df.empty:
            st.plotly_chart(px.pie(exp_df, values='Amount (Net)', names='Category', hole=0.4), use_container_width=True)

# --- ΕΓΓΡΑΦΕΣ (GRID EDITING - ΟΠΩΣ ΤΟ EXCEL) ---
elif menu == "📝 Εγγραφές & Επεξεργασία":
    st.title("📝 Διαχείριση Συναλλαγών")
    st.caption("Επεξεργάσου τα δεδομένα στον πίνακα και πάτα 'Αποθήκευση' στο τέλος.")
    
    # Φίλτρα
    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Αναζήτηση")
    type_filter = c2.multiselect("Φίλτρο Τύπου", df['DocType'].unique())
    
    df_view = df_year.copy()
    if search:
        df_view = df_view[df_view.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
    if type_filter:
        df_view = df_view[df_view['DocType'].isin(type_filter)]

    # Λίστα Τραπεζών για Dropdown (δυναμική)
    existing_banks = list(df['Bank Account'].unique())
    default_banks = ['Alpha Bank', 'Eurobank', 'Piraeus', 'National Bank', 'Revolut', 'Ταμείο Μετρητών']
    bank_options = sorted(list(set([x for x in existing_banks + default_banks if str(x) != 'nan'])))

    # DATA EDITOR (Το βασικό εργαλείο)
    edited_df = st.data_editor(
        df_view.sort_values('DocDate', ascending=False),
        num_rows="dynamic", # Επιτρέπει προσθήκη γραμμών
        use_container_width=True,
        hide_index=True,
        column_config={
            "DocDate": st.column_config.DateColumn("Ημ/νία"),
            "Payment Date": st.column_config.DateColumn("Ημ. Πληρωμής"),
            "Amount (Net)": st.column_config.NumberColumn("Καθαρό", format="€%.2f"),
            "Amount (Gross)": st.column_config.NumberColumn("Μικτό", format="€%.2f"),
            "DocType": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill", "Equity Distribution"]),
            "Status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"]),
            "Payment Method": st.column_config.SelectboxColumn("Πληρωμή", options=["Bank Transfer", "Cash", "Card"]),
            "Bank Account": st.column_config.SelectboxColumn("Λογαριασμός", options=bank_options),
        }
    )
    
    st.markdown("---")
    # ΤΟ ΚΟΥΜΠΙ ΠΟΥ ΣΩΖΕΙ ΤΑ ΠΑΝΤΑ
    if st.button("💾 Αποθήκευση Αλλαγών στη Βάση", type="primary"):
        # Πρέπει να ενώσουμε τις αλλαγές του edited_df με το γενικό df
        # Για απλότητα στο MVP, υποθέτουμε ότι δουλεύεις στο τρέχον έτος.
        # Η πιο ασφαλής μέθοδος εδώ: Ξαναφορτώνουμε όλη τη βάση, σβήνουμε τις παλιές εγγραφές του έτους και βάζουμε τις νέες.
        # ΑΛΛΑ για να μην μπερδευτείς: Θα σώσουμε ΑΥΤΟ που βλέπεις (edited_df) + τα υπόλοιπα έτη από το original df.
        
        other_years_df = df[df['DocDate'].dt.year != selected_year]
        final_df_to_save = pd.concat([other_years_df, edited_df], ignore_index=True)
        
        save_data(final_df_to_save)
        st.balloons()

# --- TREASURY ---
elif menu == "🏦 Treasury":
    st.title("🏦 Ταμεία & Τράπεζες")
    
    # Υπολογισμός υπολοίπων (Διαχρονικά)
    df_paid = df[df['Status'] == 'Paid'].copy()
    df_paid['Flow'] = df_paid.apply(lambda x: x['Amount (Gross)'] if x['DocType'] == 'Income' else -x['Amount (Gross)'], axis=1)
    
    balances = df_paid.groupby('Bank Account')['Flow'].sum().reset_index()
    
    st.metric("Συνολική Ρευστότητα", f"€{balances['Flow'].sum():,.2f}")
    
    cols = st.columns(3)
    for i, row in balances.iterrows():
        with cols[i % 3]:
            st.info(f"**{row['Bank Account']}**\n\n#### €{row['Flow']:,.2f}")
    
    st.subheader("Αναλυτική Κίνηση")
    sel_bank = st.selectbox("Επιλογή Λογαριασμού", balances['Bank Account'].unique())
    mask = (df_paid['Bank Account'] == sel_bank) & (df_paid['DocDate'].dt.year == selected_year)
    st.dataframe(df_paid[mask][['DocDate', 'Description', 'Flow']].sort_values('DocDate', ascending=False), use_container_width=True)

# --- AGING ---
elif menu == "⏳ Οφειλές":
    st.title("⏳ Ποιοι χρωστάνε / Ποιους χρωστάμε")
    
    c1, c2 = st.columns(2)
    
    unpaid_in = df[(df['DocType'] == 'Income') & (df['Status'] == 'Unpaid')]
    unpaid_out = df[(df['DocType'].isin(['Expense', 'Bill'])) & (df['Status'] == 'Unpaid')]
    
    with c1:
        st.subheader("Απαιτήσεις (Πελάτες)")
        st.metric("Σύνολο", f"€{unpaid_in['Amount (Gross)'].sum():,.2f}")
        st.dataframe(unpaid_in[['DocDate', 'Counterparty', 'Amount (Gross)']], use_container_width=True)
        
    with c2:
        st.subheader("Υποχρεώσεις (Προμηθευτές)")
        st.metric("Σύνολο", f"€{unpaid_out['Amount (Gross)'].sum():,.2f}")
        st.dataframe(unpaid_out[['DocDate', 'Counterparty', 'Amount (Gross)']], use_container_width=True)
