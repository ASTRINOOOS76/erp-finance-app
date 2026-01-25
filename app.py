import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import io
import os
from datetime import datetime, date

# --- 1. ΡΥΘΜΙΣΕΙΣ & CSS ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")
DB_FILE = "erp.db"

st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e0e0e0;
        padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #f0f2f6; border-radius: 5px;
        padding-top: 10px; padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] { background-color: #4CAF50; color: white; }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #2c3e50; color: white; }
</style>
""", unsafe_allow_html=True)

# --- GL ACCOUNTS MAP (Λεξικό Κωδικών) ---
# Αυτό συνδέει τον κωδικό με την περιγραφή για το Ισοζύγιο
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
    if os.path.exists(DB_FILE):
        return True 

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
                
                # --- ΕΞΥΠΝΟΣ ΚΑΘΑΡΙΣΜΟΣ ΣΤΗΛΩΝ ---
                df.columns = df.columns.str.strip()
                rename_map = {
                    'Date': 'DocDate', 'Ημερομηνία': 'DocDate', 
                    'Net': 'Amount (Net)', 'Gross': 'Amount (Gross)', 'Type': 'DocType'
                }
                df.rename(columns=rename_map, inplace=True)
                
                # Default GL Account αν λείπει
                if 'GL Account' not in df.columns:
                    df['GL Account'] = 0

                # Καθαρισμός ημερομηνιών
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
                         'DocType', 'Payment Method', 'Bank Account', 'Status', 'Description', 'Category', 'GL Account']
        
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

# Αν η βάση είναι άδεια
if st.session_state.df.empty:
    st.warning("⚠️ Η βάση είναι κενή.")
    if st.button("🗑️ Διαγραφή & Επανεκκίνηση"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.rerun()
    st.stop()

# Τράπεζες
existing = st.session_state.df['Bank Account'].unique().tolist()
default = ['Alpha Bank', 'Eurobank', 'Piraeus', 'National Bank', 'Revolut', 'Ταμείο Μετρητών']
st.session_state.bank_list = sorted(list(set([x for x in existing + default if str(x) != 'nan' and str(x) != ''])))

df = st.session_state.df 

# --- 5. SIDEBAR ---
st.sidebar.title("🏢 SalesTree ERP")
st.sidebar.info(f"👤 **{st.session_state.username}**")
if st.sidebar.button("Logout"): 
    st.session_state.logged_in = False
    st.rerun()
st.sidebar.divider()

# Dates
today = date.today()
dates = st.sidebar.date_input("Περίοδος", value=(date(today.year, 1, 1), date(today.year, 12, 31)), format="DD/MM/YYYY")
if len(dates) == 2:
    start, end = dates
    df_filtered = df[(df['DocDate'].dt.date >= start) & (df['DocDate'].dt.date <= end)]
else:
    df_filtered = df

# --- ΝΕΟ ΜΕΝΟΥ ---
menu = st.sidebar.radio("Μενού", 
    ["📊 Dashboard", "⚖️ Ισοζύγιο", "🖨️ Αναφορές", "🏦 Treasury", "📝 Journal", "⏳ Aging", "⚙️ Ρυθμίσεις"]
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
    
    # SMART ANALYTICS (Top Clients)
    st.subheader("🏆 Smart Analytics (Top Performers)")
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("**Top 5 Πελάτες (Τζίρος)**")
        top_clients = df_filtered[df_filtered['DocType']=='Income'].groupby('Counterparty')['Amount (Net)'].sum().nlargest(5).reset_index()
        if not top_clients.empty:
            st.plotly_chart(px.bar(top_clients, x='Amount (Net)', y='Counterparty', orientation='h', color='Amount (Net)'), use_container_width=True)
        else:
            st.info("Δεν υπάρχουν πωλήσεις.")

    with c2:
        st.markdown("**Top 5 Κατηγορίες Εξόδων**")
        top_exp = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])].groupby('Category')['Amount (Net)'].sum().nlargest(5).reset_index()
        if not top_exp.empty:
             st.plotly_chart(px.pie(top_exp, values='Amount (Net)', names='Category', hole=0.5), use_container_width=True)
        else:
            st.info("Δεν υπάρχουν έξοδα.")

# --- 7. ΙΣΟΖΥΓΙΟ (TRIAL BALANCE) ---
elif menu == "⚖️ Ισοζύγιο":
    st.title("⚖️ Ισοζύγιο Λογαριασμών (Trial Balance)")
    st.caption("Συγκεντρωτική εικόνα ανά Κωδικό Λογιστικής (GL Code).")

    # Group by GL Account
    tb = df_filtered.groupby('GL Account').agg({
        'Amount (Net)': 'sum',
        'Amount (Gross)': 'sum'
    }).reset_index()

    # Map Descriptions
    tb['Περιγραφή'] = tb['GL Account'].map(GL_MAP).fillna("Άγνωστος Λογαριασμός")
    
    # Reorder columns
    tb = tb[['GL Account', 'Περιγραφή', 'Amount (Net)', 'Amount (Gross)']]
    tb.columns = ['Κωδικός', 'Περιγραφή Λογαριασμού', 'Καθαρό Ποσό', 'Μικτό Ποσό']
    
    # Sort
    tb = tb.sort_values('Κωδικός')

    # Display
    st.dataframe(tb, use_container_width=True, hide_index=True)
    
    # Export
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        tb.to_excel(writer, sheet_name='Trial Balance', index=False)
    st.download_button("🖨️ Εκτύπωση (Λήψη Excel)", buf, "Trial_Balance.xlsx", type="primary")

# --- 8. ΑΝΑΦΟΡΕΣ (REPORTS) ---
elif menu == "🖨️ Αναφορές":
    st.title("🖨️ Κέντρο Αναφορών")
    
    tab1, tab2 = st.tabs(["🏛️ Αναφορά ΦΠΑ", "📈 Αποτελέσματα (P&L)"])
    
    with tab1:
        st.subheader("Περιοδική Δήλωση ΦΠΑ (Εκτίμηση)")
        
        vat_out = df_filtered[df_filtered['DocType'] == 'Income']['VAT Amount'].sum()
        vat_in = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]['VAT Amount'].sum()
        vat_result = vat_out - vat_in
        
        col1, col2, col3 = st.columns(3)
        col1.metric("ΦΠΑ Εκροών (Πωλήσεις)", f"€{vat_out:,.2f}")
        col2.metric("ΦΠΑ Εισροών (Αγορές)", f"€{vat_in:,.2f}")
        col3.metric("Αποτέλεσμα", f"€{vat_result:,.2f}", delta="Πληρωμή" if vat_result > 0 else "Επιστροφή", delta_color="inverse")
        
        # Detail Table for VAT
        st.write("Αναλυτικές Κινήσεις ΦΠΑ:")
        vat_df = df_filtered[df_filtered['VAT Amount'] != 0][['DocDate', 'DocType', 'Counterparty', 'VAT Amount']]
        st.dataframe(vat_df, use_container_width=True)
        
        # Print Button
        buf_vat = io.BytesIO()
        with pd.ExcelWriter(buf_vat, engine='xlsxwriter') as writer:
            vat_df.to_excel(writer, sheet_name='VAT Report', index=False)
        st.download_button("🖨️ Εκτύπωση ΦΠΑ", buf_vat, "VAT_Report.xlsx")

    with tab2:
        st.subheader("Αποτελέσματα Χρήσης (P&L)")
        
        pl_data = df_filtered[df_filtered['DocType'].isin(['Income', 'Expense', 'Bill'])]
        pl_grouped = pl_data.groupby(['DocType', 'Category'])['Amount (Net)'].sum().reset_index()
        
        # Pivot for cleaner look
        try:
            pl_pivot = pl_grouped.pivot(index='Category', columns='DocType', values='Amount (Net)').fillna(0)
            st.dataframe(pl_pivot.style.highlight_max(axis=0), use_container_width=True)
            
            # Print Button
            buf_pl = io.BytesIO()
            with pd.ExcelWriter(buf_pl, engine='xlsxwriter') as writer:
                pl_pivot.to_excel(writer, sheet_name='PnL')
            st.download_button("🖨️ Εκτύπωση P&L", buf_pl, "PnL_Report.xlsx")
        except:
            st.info("Δεν υπάρχουν αρκετά δεδομένα για P&L.")

# --- 9. TREASURY ---
elif menu == "🏦 Treasury":
    st.title("🏦 Διαχείριση Ρευστότητας")
    tab1, tab2, tab3 = st.tabs(["💰 Υπόλοιπα", "📈 Κίνηση", "➕ Νέα Τράπεζα"])
    
    with tab1:
        df_pd = df[df['Status'] == 'Paid'].copy()
        df_pd['Sgn'] = df_pd.apply(lambda x: x['Amount (Gross)'] if x['DocType'] == 'Income' else -x['Amount (Gross)'], axis=1)
        bal = df_pd.groupby('Bank Account')['Sgn'].sum().reset_index()
        st.metric("Σύνολο", f"€{bal['Sgn'].sum():,.2f}")
        cols = st.columns(3)
        for i, r in bal.iterrows():
            with cols[i % 3]: st.info(f"**{r['Bank Account']}**\n\n### €{r['Sgn']:,.2f}")

    with tab2:
        sel_bank = st.selectbox("Λογαριασμός", st.session_state.bank_list)
        txns = df_filtered[(df_filtered['Bank Account'] == sel_bank) & (df_filtered['Status']=='Paid')].sort_values('DocDate', ascending=False)
        st.dataframe(txns[['DocDate', 'Description', 'Amount (Gross)', 'DocType']], use_container_width=True)

    with tab3:
        with st.form("new_bank"):
            nb = st.text_input("Όνομα Τράπεζας")
            if st.form_submit_button("Προσθήκη"):
                st.session_state.bank_list.append(nb); st.success("ΟΚ")

# --- 10. JOURNAL ---
elif menu == "📝 Journal":
    st.title("📝 Ημερολόγιο")
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: st.session_state.df.to_excel(writer, sheet_name='Journal', index=False)
    st.download_button("💾 Download Excel Backup", buf, "Finance_Backup.xlsx")

    c1, c2 = st.columns(2)
    s_txt = c1.text_input("Αναζήτηση")
    t_flt = c2.multiselect("Τύπος", df['DocType'].unique())
    
    v = df_filtered.copy()
    if s_txt: v = v[v.astype(str).apply(lambda x: x.str.contains(s_txt, case=False)).any(axis=1)]
    if t_flt: v = v[v['DocType'].isin(t_flt)]

    # Φτιάχνουμε λίστα επιλογών για GL Account (Κωδικός - Περιγραφή)
    gl_options = sorted(list(GL_MAP.keys()))

    edf = st.data_editor(v.sort_values('DocDate', ascending=False), num_rows="dynamic", use_container_width=True, hide_index=True,
        column_config={
            "DocDate": st.column_config.DateColumn("Ημ/νία"),
            "Amount (Net)": st.column_config.NumberColumn("Καθαρό", format="€%.2f"),
            "Bank Account": st.column_config.SelectboxColumn("Τράπεζα", options=st.session_state.bank_list),
            "DocType": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill", "Equity Distribution"]),
            "Status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"]),
            "GL Account": st.column_config.SelectboxColumn("Λογαριασμός (GL)", options=gl_options, help="4000=Πωλήσεις, 6000=Έξοδα, κτλ")
        }
    )
    
    st.markdown("---")
    if st.button("💾 Αποθήκευση στη Βάση", type="primary"):
        st.session_state.df.update(edf)
        new_rows = edf[~edf.index.isin(st.session_state.df.index)]
        if not new_rows.empty:
            st.session_state.df = pd.concat([st.session_state.df, new_rows], ignore_index=True)
        save_data_to_db(st.session_state.df)
        st.balloons()

# --- 11. AGING ---
elif menu == "⏳ Aging":
    st.title("⏳ Οφειλές")
    u_in = df[(df['DocType'] == 'Income') & (df['Status'] == 'Unpaid')]
    u_out = df[(df['DocType'].isin(['Expense', 'Bill'])) & (df['Status'] == 'Unpaid')]
    c1, c2 = st.columns(2)
    with c1: st.subheader("Πελάτες"); st.dataframe(u_in[['DocDate','Counterparty','Amount (Gross)']]); st.metric("Σύνολο", f"€{u_in['Amount (Gross)'].sum():,.2f}")
    with c2: st.subheader("Προμηθευτές"); st.dataframe(u_out[['DocDate','Counterparty','Amount (Gross)']]); st.metric("Σύνολο", f"€{u_out['Amount (Gross)'].sum():,.2f}")

# --- 12. SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    st.write(f"Χρήστης: {st.session_state.username}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Λεξικό Λογαριασμών (GL Map)")
        # Δείχνουμε το λεξικό GL_MAP σε πίνακα
        gl_df = pd.DataFrame(list(GL_MAP.items()), columns=['Κωδικός', 'Περιγραφή'])
        st.dataframe(gl_df, hide_index=True)

    with col2:
        st.subheader("Ενέργειες")
        if st.button("🗑️ Hard Reset (Διαγραφή Βάσης)"):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            st.rerun()
