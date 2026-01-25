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
    .stButton>button:hover { background-color: #1a252f; color: white; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ENGINE ---
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db_and_migrate():
    """Ελέγχει αν υπάρχει βάση. Αν όχι, ζητάει Excel."""
    if os.path.exists(DB_FILE):
        return True # Η βάση υπάρχει

    # Αν δεν υπάρχει βάση, ψάχνουμε τοπικά για Excel
    excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
    file_to_load = None

    if excel_files:
        file_to_load = excel_files[0]
    else:
        # Αν δεν υπάρχει αρχείο, ζητάμε upload
        st.warning("⚠️ Δεν βρέθηκε Βάση Δεδομένων.")
        st.info("📂 Παρακαλώ ανεβάστε το Excel (Journal) για την αρχική εγκατάσταση.")
        uploaded = st.file_uploader("Upload Excel", type=['xlsx'])
        if uploaded:
            with open("temp_init.xlsx", "wb") as f:
                f.write(uploaded.getbuffer())
            file_to_load = "temp_init.xlsx"
        else:
            return False

    if file_to_load:
        try:
            with st.spinner("Γίνεται δημιουργία της βάσης..."):
                xl = pd.ExcelFile(file_to_load, engine='openpyxl')
                sheet = "Journal" if "Journal" in xl.sheet_names else xl.sheet_names[0]
                df = pd.read_excel(file_to_load, sheet_name=sheet)
                
                # Καθαρισμός ημερομηνιών για SQLite
                df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce').dt.strftime('%Y-%m-%d')
                
                conn = get_connection()
                df.to_sql('journal', conn, if_exists='replace', index=False)
                conn.close()
            
            st.success("✅ Η βάση δημιουργήθηκε!")
            if file_to_load == "temp_init.xlsx": os.remove("temp_init.xlsx")
            st.rerun()
            return True
        except Exception as e:
            st.error(f"Σφάλμα κατά τη μετάπτωση: {e}")
            return False

# --- 3. DATA FUNCTIONS ---
def load_data_from_db():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM journal", conn)
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        
        # Καθαρισμός Αριθμών
        for col in ['Amount (Net)', 'Amount (Gross)', 'VAT Amount', 'GL Account']:
            if col in df.columns: 
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Καθαρισμός Κειμένων
        cols_needed = ['DocType', 'Payment Method', 'Bank Account', 'Status', 'Description', 'Category']
        for c in cols_needed:
            if c not in df.columns: df[c] = ""
        
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
        save_copy['DocDate'] = save_copy['DocDate'].dt.strftime('%Y-%m-%d')
        save_copy.to_sql('journal', conn, if_exists='replace', index=False)
        conn.close()
        st.toast("✅ Τα δεδομένα αποθηκεύτηκαν μόνιμα!", icon="💾")
    except Exception as e:
        st.error(f"Αδυναμία αποθήκευσης: {e}")

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

# Φόρτωση δεδομένων στη μνήμη (Session State)
if 'df' not in st.session_state:
    st.session_state.df = load_data_from_db()

# Ανανέωση λίστας τραπεζών
existing = st.session_state.df['Bank Account'].unique().tolist() if not st.session_state.df.empty else []
default = ['Alpha Bank', 'Eurobank', 'Piraeus', 'National Bank', 'Revolut', 'Ταμείο Μετρητών']
st.session_state.bank_list = sorted(list(set([x for x in existing + default if str(x) != 'nan' and str(x) != ''])))

df = st.session_state.df # Alias για ευκολία

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

menu = st.sidebar.radio("Μενού", ["📊 Dashboard", "🏦 Treasury", "📝 Journal", "⏳ Aging", "⚙️ Ρυθμίσεις"])

# --- 6. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Εικόνα Επιχείρησης")
    
    inc = df_filtered[df_filtered['DocType'] == 'Income']['Amount (Net)'].sum()
    exp = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    prof = inc - exp
    
    paid_in = df_filtered[(df_filtered['Status']=='Paid') & (df_filtered['DocType']=='Income')]['Amount (Gross)'].sum()
    paid_out = df_filtered[(df_filtered['Status']=='Paid') & (df_filtered['DocType']!='Income')]['Amount (Gross)'].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Πωλήσεις", f"€{inc:,.0f}")
    c2.metric("Έξοδα", f"€{exp:,.0f}")
    c3.metric("Κέρδος", f"€{prof:,.0f}")
    c4.metric("Ρευστότητα (Cashflow)", f"€{(paid_in-paid_out):,.0f}")
    
    st.divider()
    c1, c2 = st.columns([2, 1])
    with c1:
        mon = df_filtered.copy(); mon['Month'] = mon['DocDate'].dt.strftime('%Y-%m')
        grp = mon.groupby(['Month', 'DocType'])['Amount (Net)'].sum().reset_index()
        st.plotly_chart(px.bar(grp, x='Month', y='Amount (Net)', color='DocType', barmode='group'), use_container_width=True)
    with c2:
        st.subheader("Κατηγορίες Εξόδων")
        exp_df = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]
        if not exp_df.empty: st.plotly_chart(px.pie(exp_df, values='Amount (Net)', names='Category', hole=0.4), use_container_width=True)

# --- 7. TREASURY ---
elif menu == "🏦 Treasury":
    st.title("🏦 Διαχείριση Ρευστότητας")
    tab1, tab2, tab3 = st.tabs(["💰 Υπόλοιπα", "📈 Κίνηση", "➕ Νέα Τράπεζα"])
    
    with tab1:
        # Υπολογισμός σε ΟΛΟ το ιστορικό για σωστά υπόλοιπα
        df_pd = df[df['Status'] == 'Paid'].copy()
        df_pd['Sgn'] = df_pd.apply(lambda x: x['Amount (Gross)'] if x['DocType'] == 'Income' else -x['Amount (Gross)'], axis=1)
        bal = df_pd.groupby('Bank Account')['Sgn'].sum().reset_index()
        st.metric("Σύνολο", f"€{bal['Sgn'].sum():,.2f}")
        cols = st.columns(3)
        for i, r in bal.iterrows():
            with cols[i % 3]: st.info(f"**{r['Bank Account']}**\n\n### €{r['Sgn']:,.2f}")

    with tab2:
        sel_bank = st.selectbox("Λογαριασμός", st.session_state.bank_list)
        # Εδώ δείχνουμε κινήσεις βάσει του φίλτρου ημερομηνίας
        txns = df_filtered[(df_filtered['Bank Account'] == sel_bank) & (df_filtered['Status']=='Paid')].sort_values('DocDate', ascending=False)
        st.dataframe(txns[['DocDate', 'Description', 'Amount (Gross)', 'DocType']], use_container_width=True)

    with tab3:
        with st.form("new_bank"):
            nb = st.text_input("Όνομα Τράπεζας")
            if st.form_submit_button("Προσθήκη"):
                st.session_state.bank_list.append(nb)
                st.success("ΟΚ - Η τράπεζα θα εμφανιστεί στις επιλογές.")

# --- 8. JOURNAL (DATABASE ENABLED) ---
elif menu == "📝 Journal":
    st.title("📝 Ημερολόγιο")
    
    # Download Button (Optional Backup)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: st.session_state.df.to_excel(writer, sheet_name='Journal', index=False)
    st.download_button("💾 Download Excel Backup", buf, "Finance_Backup.xlsx")

    # Filters
    c1, c2 = st.columns(2)
    s_txt = c1.text_input("Αναζήτηση")
    t_flt = c2.multiselect("Τύπος", df['DocType'].unique())
    
    v = df_filtered.copy()
    if s_txt: v = v[v.astype(str).apply(lambda x: x.str.contains(s_txt, case=False)).any(axis=1)]
    if t_flt: v = v[v['DocType'].isin(t_flt)]

    # Editor
    edf = st.data_editor(v.sort_values('DocDate', ascending=False), num_rows="dynamic", use_container_width=True, hide_index=True,
        column_config={
            "DocDate": st.column_config.DateColumn("Ημ/νία"),
            "Amount (Net)": st.column_config.NumberColumn("Καθαρό", format="€%.2f"),
            "Bank Account": st.column_config.SelectboxColumn("Τράπεζα", options=st.session_state.bank_list),
            "DocType": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill", "Equity Distribution"]),
            "Status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"]),
            "GL Account": st.column_config.NumberColumn("GL Code", help="Δες Ρυθμίσεις")
        }
    )
    
    st.markdown("---")
    # ΤΟ ΣΗΜΑΝΤΙΚΟ ΚΟΥΜΠΙ
    if st.button("💾 Αποθήκευση στη Βάση", type="primary"):
        # Ενημέρωση του κεντρικού DF στη μνήμη
        st.session_state.df.update(edf)
        # Προσθήκη νέων γραμμών αν υπάρχουν (αυτό θέλει προσοχή με τα indexes, εδώ κάνουμε απλή ενημέρωση)
        # Για να είμαστε σίγουροι, σώζουμε το edf πάνω στις αντίστοιχες εγγραφές
        
        # Στρατηγική Αποθήκευσης: 
        # Επειδή το edf είναι φιλτραρισμένο, δεν μπορούμε να αντικαταστήσουμε ΟΛΗ τη βάση μόνο με αυτό.
        # Θα ενώσουμε τα δεδομένα που ΔΕΝ βλέπουμε, με αυτά που βλέπουμε (edf).
        
        # 1. Βρίσκουμε τα δεδομένα που είναι ΕΚΤΟΣ φίλτρων (αυτά δεν τα πείραξε ο χρήστης)
        # Χρησιμοποιούμε το index για να τα ξεχωρίσουμε αν είναι δυνατόν, ή απλά ενώνουμε.
        # Εδώ, για ασφάλεια και απλότητα, θα ενημερώσουμε το st.session_state.df και θα σώσουμε ΟΛΟ το df.
        
        # Update session state logic:
        # Αντικαθιστούμε τις γραμμές στο main df που αντιστοιχούν στο edf
        # (Σημείωση: Το data_editor κρατάει το original index αν δεν κάνουμε reset_index)
        st.session_state.df.update(edf)
        
        # Αν προστέθηκαν ΝΕΕΣ γραμμές στο edf, πρέπει να τις προσθέσουμε στο main df
        new_rows = edf[~edf.index.isin(st.session_state.df.index)]
        if not new_rows.empty:
            st.session_state.df = pd.concat([st.session_state.df, new_rows], ignore_index=True)

        # Τώρα σώζουμε ΟΛΟ το session state df στη βάση
        save_data_to_db(st.session_state.df)
        st.balloons()

# --- 9. AGING ---
elif menu == "⏳ Aging":
    st.title("⏳ Οφειλές")
    u_in = df[(df['DocType'] == 'Income') & (df['Status'] == 'Unpaid')]
    u_out = df[(df['DocType'].isin(['Expense', 'Bill'])) & (df['Status'] == 'Unpaid')]
    c1, c2 = st.columns(2)
    with c1: st.subheader("Πελάτες"); st.dataframe(u_in[['DocDate','Counterparty','Amount (Gross)']]); st.metric("Σύνολο", f"€{u_in['Amount (Gross)'].sum():,.2f}")
    with c2: st.subheader("Προμηθευτές"); st.dataframe(u_out[['DocDate','Counterparty','Amount (Gross)']]); st.metric("Σύνολο", f"€{u_out['Amount (Gross)'].sum():,.2f}")

# --- 10. SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις")
    
    tab_info, tab_gl = st.tabs(["ℹ️ Σύστημα", "📚 Λογιστικό Σχέδιο"])
    
    with tab_info:
        st.info(f"Χρήστης: {st.session_state.username}")
        st.write("Τράπεζες:", st.session_state.bank_list)
        if st.button("🗑️ Hard Reset (Διαγραφή Βάσης)"):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            st.rerun()

    with tab_gl:
        gl_data = {
            "Κωδικός": [4000, 5000, 6000, 7000, 7010, 8000, 9999],
            "Περιγραφή": ["Έσοδα", "Κόστη", "Έξοδα", "Τράπεζα", "Ταμείο", "Μερίσματα", "Unmapped"],
            "Τύπος": ["Έσοδο", "Έξοδο", "Έξοδο", "Asset", "Asset", "Equity", "-"]
        }
        st.table(pd.DataFrame(gl_data))
