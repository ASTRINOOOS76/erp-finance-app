import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import io
import os
from datetime import datetime, date

# --- 1. ΡΥΘΜΙΣΕΙΣ & ΜΟΝΤΕΡΝΟ DESIGN ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")
DB_FILE = "erp.db"

# Εδώ είναι το "Professional Theme"
st.markdown("""
<style>
    /* 1. ΦΟΝΤΟ ΕΦΑΡΜΟΓΗΣ - Απαλό Γκρι */
    .stApp {
        background-color: #f1f5f9;
    }

    /* 2. SIDEBAR - Σκούρο Μπλε για Αντίθεση */
    section[data-testid="stSidebar"] {
        background-color: #0f172a;
    }
    /* Τα γράμματα στο Sidebar ΛΕΥΚΑ για να φαίνονται */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] span, 
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] div {
        color: #f8fafc !important;
    }

    /* 3. ΚΥΡΙΩΣ ΚΕΙΜΕΝΟ - Σκούρο για να διαβάζεται */
    h1, h2, h3, h4, p, li, div {
        color: #1e293b; 
    }

    /* 4. METRICS (Κουτάκια) - Λευκά με σκιά */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border-left: 5px solid #3b82f6; /* Μπλε γραμμή αριστερά */
    }
    div[data-testid="metric-container"] label {
        color: #64748b !important; /* Γκρι τίτλος metric */
    }
    div[data-testid="metric-container"] div {
        color: #0f172a !important; /* Μαύρο νούμερο */
    }

    /* 5. TABS - Καθαρό στυλ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #e2e8f0;
        border-radius: 5px;
        color: #334155;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: white !important;
    }

    /* 6. BUTTONS */
    .stButton>button {
        background-color: #3b82f6;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #2563eb;
    }
</style>
""", unsafe_allow_html=True)

# --- GL ACCOUNTS MAP ---
GL_MAP = {
    4000: "Πωλήσεις / Έσοδα Υπηρεσιών",
    5000: "Κόστος Πωληθέντων (Αγορές)",
    6000: "Λειτουργικά Έξοδα (Γενικά)",
    6100: "Αμοιβές Τρίτων & Ενοίκια",
    6200: "Παροχές Τρίτων (ΔΕΗ/ΟΤΕ)",
    7000: "Όψεως & Καταθέσεις (Τράπεζες)",
    7010: "Ταμείο Μετρητών",
    8000: "Κεφάλαιο & Μερίσματα"
}

# --- 2. DATABASE ENGINE ---
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db_and_migrate():
    if os.path.exists(DB_FILE): return True 

    excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
    file_to_load = None

    if excel_files:
        file_to_load = excel_files[0]
    else:
        st.warning("⚠️ Δεν βρέθηκε Βάση Δεδομένων.")
        st.info("📂 Παρακαλώ ανεβάστε το Excel (Journal).")
        uploaded = st.file_uploader("Upload Excel", type=['xlsx'])
        if uploaded:
            with open("temp_init.xlsx", "wb") as f:
                f.write(uploaded.getbuffer())
            file_to_load = "temp_init.xlsx"
        else:
            return False

    if file_to_load:
        try:
            with st.spinner("Γίνεται ανάλυση αρχείου..."):
                xl = pd.ExcelFile(file_to_load, engine='openpyxl')
                sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
                df = pd.read_excel(file_to_load, sheet_name=sheet)
                
                df.columns = df.columns.str.strip()
                rename_map = {
                    'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 
                    'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType'
                }
                df.rename(columns=rename_map, inplace=True)
                
                if 'GL Account' not in df.columns: df['GL Account'] = 0

                df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce').dt.strftime('%Y-%m-%d')
                if 'Payment Date' in df.columns:
                    df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce').dt.strftime('%Y-%m-%d')
                
                conn = get_connection()
                df.to_sql('journal', conn, if_exists='replace', index=False)
                conn.close()
            
            st.success("✅ Η βάση δημιουργήθηκε!")
            if file_to_load == "temp_init.xlsx": os.remove("temp_init.xlsx")
            st.rerun()
            return True
        except Exception as e:
            st.error(f"Σφάλμα: {e}")
            return False

# --- 3. DATA FUNCTIONS ---
def load_data_from_db():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM journal", conn)
        required_cols = ['DocDate', 'Payment Date', 'Amount (Net)', 'Amount (Gross)', 'VAT Amount', 
                         'DocType', 'Payment Method', 'Bank Account', 'Status', 'Description', 'Category', 'GL Account', 'Counterparty']
        
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0 if 'Amount' in col or 'GL' in col else ""

        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
        
        for col in ['Amount (Net)', 'Amount (Gross)', 'VAT Amount', 'GL Account']:
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df.loc[df['Payment Method'] == 'Cash', 'Bank Account'] = 'Ταμείο Μετρητών'
        conn.close()
        return df
    except:
        conn.close()
        return pd.DataFrame()

def save_data_to_db(df_to_save):
    try:
        conn = get_connection()
        save_copy = df_to_save.copy()
        if 'DocDate' in save_copy.columns:
            save_copy['DocDate'] = save_copy['DocDate'].dt.strftime('%Y-%m-%d')
        if 'Payment Date' in save_copy.columns:
            save_copy['Payment Date'] = save_copy['Payment Date'].dt.strftime('%Y-%m-%d')
        save_copy.to_sql('journal', conn, if_exists='replace', index=False)
        conn.close()
        st.toast("✅ Αποθηκεύτηκε!", icon="💾")
    except Exception as e:
        st.error(f"Error: {e}")

# --- 4. LOGIN ---
def check_login():
    users = {"admin": "admin123", "user": "1234"}
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False

    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("🔐 SalesTree ERP")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if username in users and users[username] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Λάθος στοιχεία.")
        st.stop()

check_login()

# --- INITIALIZATION ---
if not init_db_and_migrate():
    st.stop()

if 'df' not in st.session_state:
    st.session_state.df = load_data_from_db()

if st.session_state.df.empty:
    st.warning("⚠️ Η βάση είναι κενή.")
    if st.button("🗑️ Διαγραφή & Επανεκκίνηση"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.rerun()
    st.stop()

# Τράπεζες
existing_banks = st.session_state.df['Bank Account'].unique().tolist()
default_banks = ['Alpha Bank', 'Eurobank', 'Piraeus', 'National Bank', 'Revolut', 'Ταμείο Μετρητών']
st.session_state.bank_list = sorted(list(set([x for x in existing_banks + default_banks if str(x) != 'nan' and str(x) != ''])))

df = st.session_state.df 

# --- 5. SIDEBAR ---
st.sidebar.title("🏢 SalesTree ERP")
st.sidebar.markdown(f"<p style='color:white;'>👤 <b>{st.session_state.username}</b></p>", unsafe_allow_html=True)
if st.sidebar.button("Logout"): 
    st.session_state.logged_in = False
    st.rerun()
st.sidebar.divider()

today = date.today()
dates = st.sidebar.date_input("Περίοδος", value=(date(today.year, 1, 1), date(today.year, 12, 31)), format="DD/MM/YYYY")
if len(dates) == 2:
    start, end = dates
    df_filtered = df[(df['DocDate'].dt.date >= start) & (df['DocDate'].dt.date <= end)]
else:
    df_filtered = df

menu = st.sidebar.radio("Μενού", 
    ["📊 Dashboard", "👥 Μέτοχοι", "⚖️ Ισοζύγιο", "🖨️ Αναφορές", "🏦 Treasury", "📝 Journal", "⏳ Aging", "⚙️ Ρυθμίσεις"]
)

# --- 6. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Εικόνα Επιχείρησης")
    
    inc = df_filtered[df_filtered['DocType'] == 'Income']['Amount (Net)'].sum()
    exp = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    prof = inc - exp
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Πωλήσεις", f"€{inc:,.0f}")
    c2.metric("Έξοδα", f"€{exp:,.0f}")
    c3.metric("Κέρδος", f"€{prof:,.0f}")
    
    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Top 5 Πελάτες (Τζίρος)")
        top_clients = df_filtered[df_filtered['DocType']=='Income'].groupby('Counterparty')['Amount (Net)'].sum().nlargest(5).reset_index()
        if not top_clients.empty:
            st.plotly_chart(px.bar(top_clients, x='Amount (Net)', y='Counterparty', orientation='h', color='Amount (Net)'), use_container_width=True)
        else:
            st.info("Δεν υπάρχουν πωλήσεις.")
    with c2:
        st.markdown("### Top 5 Κατηγορίες Εξόδων")
        top_exp = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])].groupby('Category')['Amount (Net)'].sum().nlargest(5).reset_index()
        if not top_exp.empty:
             st.plotly_chart(px.pie(top_exp, values='Amount (Net)', names='Category', hole=0.5), use_container_width=True)
        else:
            st.info("Δεν υπάρχουν έξοδα.")

# --- 7. ΜΕΤΟΧΟΙ ---
elif menu == "👥 Μέτοχοι":
    st.title("👥 Διαχείριση Μετόχων")
    div_df = df_filtered[df_filtered['DocType'] == 'Equity Distribution'].copy()
    
    tab1, tab2 = st.tabs(["💰 Διανομές", "➕ Πληρωμή Μερίσματος"])
    
    with tab1:
        total_div = div_df['Amount (Net)'].sum()
        st.metric("Σύνολο Μερισμάτων", f"€{total_div:,.2f}")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("Ανάλυση ανά Μέτοχο")
            if not div_df.empty:
                shareholder_stats = div_df.groupby('Counterparty')['Amount (Net)'].sum().reset_index()
                st.dataframe(shareholder_stats, use_container_width=True, hide_index=True)
            else:
                st.info("Δεν έχουν καταβληθεί μερίσματα.")
        with col2:
            if not div_df.empty:
                fig = px.pie(shareholder_stats, values='Amount (Net)', names='Counterparty')
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Νέα Πληρωμή")
        with st.form("dividend_form"):
            col1, col2 = st.columns(2)
            d_date = col1.date_input("Ημερομηνία", value=date.today())
            partner = col2.text_input("Μέτοχος")
            amount = st.number_input("Ποσό (€)", min_value=0.01)
            bank = st.selectbox("Πληρωμή Από", st.session_state.bank_list)
            
            if st.form_submit_button("💾 Καταχώρηση"):
                new_row = {
                    'DocDate': d_date, 'DocType': 'Equity Distribution',
                    'Counterparty': partner, 'Description': 'Διανομή Κερδών',
                    'Amount (Net)': amount, 'Amount (Gross)': amount, 'VAT Amount': 0,
                    'Payment Method': 'Bank Transfer', 'Bank Account': bank, 'Status': 'Paid',
                    'Category': 'Dividends', 'GL Account': 8000, 'Payment Date': d_date
                }
                new_df = pd.DataFrame([new_row])
                new_df['DocDate'] = pd.to_datetime(new_df['DocDate'])
                new_df['Payment Date'] = pd.to_datetime(new_df['Payment Date'])
                
                updated_df = pd.concat([st.session_state.df, new_df], ignore_index=True)
                save_data_to_db(updated_df)
                st.session_state.df = updated_df
                st.success("Καταχωρήθηκε!")
                st.rerun()

# --- 8. ΙΣΟΖΥΓΙΟ ---
elif menu == "⚖️ Ισοζύγιο":
    st.title("⚖️ Ισοζύγιο")
    tb = df_filtered.groupby('GL Account').agg({'Amount (Net)': 'sum', 'Amount (Gross)': 'sum'}).reset_index()
    tb['Περιγραφή'] = tb['GL Account'].map(GL_MAP).fillna("Άγνωστος")
    tb = tb[['GL Account', 'Περιγραφή', 'Amount (Net)', 'Amount (Gross)']].sort_values('GL Account')
    
    st.dataframe(tb, use_container_width=True, hide_index=True)
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: tb.to_excel(writer, sheet_name='Trial Balance', index=False)
    st.download_button("🖨️ Λήψη Excel", buf, "Trial_Balance.xlsx")

# --- 9. ΑΝΑΦΟΡΕΣ ---
elif menu == "🖨️ Αναφορές":
    st.title("🖨️ Αναφορές")
    tab1, tab2 = st.tabs(["🏛️ ΦΠΑ", "📈 P&L"])
    
    with tab1:
        vat_out = df_filtered[df_filtered['DocType'] == 'Income']['VAT Amount'].sum()
        vat_in = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]['VAT Amount'].sum()
        res = vat_out - vat_in
        c1, c2, c3 = st.columns(3)
        c1.metric("ΦΠΑ Πωλήσεων", f"€{vat_out:,.2f}")
        c2.metric("ΦΠΑ Αγορών", f"€{vat_in:,.2f}")
        c3.metric("Αποτέλεσμα", f"€{res:,.2f}")
        
        st.dataframe(df_filtered[df_filtered['VAT Amount']!=0][['DocDate','Counterparty','VAT Amount']], use_container_width=True)

    with tab2:
        pl = df_filtered[df_filtered['DocType'].isin(['Income','Expense','Bill'])].groupby(['Category','DocType'])['Amount (Net)'].sum().unstack().fillna(0)
        st.dataframe(pl, use_container_width=True)

# --- 10. TREASURY ---
elif menu == "🏦 Treasury":
    st.title("🏦 Ρευστότητα")
    df_pd = df[df['Status'] == 'Paid'].copy()
    df_pd['Sgn'] = df_pd.apply(lambda x: x['Amount (Gross)'] if x['DocType'] == 'Income' else -x['Amount (Gross)'], axis=1)
    bal = df_pd.groupby('Bank Account')['Sgn'].sum().reset_index()
    
    st.metric("Σύνολο", f"€{bal['Sgn'].sum():,.2f}")
    cols = st.columns(3)
    for i, r in bal.iterrows():
        with cols[i%3]: st.info(f"**{r['Bank Account']}**\n\n### €{r['Sgn']:,.2f}")

# --- 11. JOURNAL ---
elif menu == "📝 Journal":
    st.title("📝 Ημερολόγιο")
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: st.session_state.df.to_excel(writer, sheet_name='Journal', index=False)
    st.download_button("💾 Backup Excel", buf, "Finance_Backup.xlsx")

    c1, c2 = st.columns(2)
    s_txt = c1.text_input("Αναζήτηση")
    t_flt = c2.multiselect("Τύπος", df['DocType'].unique())
    
    v = df_filtered.copy()
    if s_txt: v = v[v.astype(str).apply(lambda x: x.str.contains(s_txt, case=False)).any(axis=1)]
    if t_flt: v = v[v['DocType'].isin(t_flt)]

    edf = st.data_editor(v.sort_values('DocDate', ascending=False), num_rows="dynamic", use_container_width=True, hide_index=True,
        column_config={
            "DocDate": st.column_config.DateColumn("Ημ/νία"),
            "Amount (Net)": st.column_config.NumberColumn("Καθαρό", format="€%.2f"),
            "Bank Account": st.column_config.SelectboxColumn("Τράπεζα", options=st.session_state.bank_list),
            "DocType": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill", "Equity Distribution"]),
            "Status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"]),
            "GL Account": st.column_config.SelectboxColumn("GL", options=sorted(list(GL_MAP.keys())))
        }
    )
    
    if st.button("💾 Αποθήκευση στη Βάση", type="primary"):
        st.session_state.df.update(edf)
        new_rows = edf[~edf.index.isin(st.session_state.df.index)]
        if not new_rows.empty:
            st.session_state.df = pd.concat([st.session_state.df, new_rows], ignore_index=True)
        save_data_to_db(st.session_state.df)
        st.balloons()

# --- 12. AGING ---
elif menu == "⏳ Aging":
    st.title("⏳ Οφειλές")
    c1, c2 = st.columns(2)
    with c1: 
        st.subheader("Πελάτες")
        st.dataframe(df[(df['DocType']=='Income')&(df['Status']=='Unpaid')][['DocDate','Counterparty','Amount (Gross)']], use_container_width=True)
    with c2: 
        st.subheader("Προμηθευτές")
        st.dataframe(df[(df['DocType'].isin(['Expense','Bill']))&(df['Status']=='Unpaid')][['DocDate','Counterparty','Amount (Gross)']], use_container_width=True)

# --- 13. SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    if st.button("🗑️ Hard Reset"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.rerun()
