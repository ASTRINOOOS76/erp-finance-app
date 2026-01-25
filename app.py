import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import os
from datetime import datetime, date

# --- 1. ΡΥΘΜΙΣΕΙΣ ΣΕΛΙΔΑΣ ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")

# --- CSS ---
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
</style>
""", unsafe_allow_html=True)

# --- 2. LOGIN ---
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

# --- 3. DATA LOADING ---
def get_excel_path():
    excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
    return excel_files[0] if excel_files else None

@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name="Journal", engine='openpyxl')
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        for col in ['Amount (Net)', 'Amount (Gross)', 'VAT Amount']:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        cols_needed = ['DocType', 'Payment Method', 'Bank Account', 'Status', 'Description', 'Category', 'GL Account']
        for c in cols_needed:
            if c not in df.columns: df[c] = ""
        
        df.loc[df['Payment Method'] == 'Cash', 'Bank Account'] = 'Ταμείο Μετρητών'
        return df
    except: return None

path = get_excel_path()
if path:
    if 'df' not in st.session_state: st.session_state.df = load_data(path)
    if 'bank_list' not in st.session_state:
        existing = st.session_state.df['Bank Account'].unique().tolist() if st.session_state.df is not None else []
        default = ['Alpha Bank', 'Eurobank', 'Piraeus', 'National Bank', 'Revolut', 'Ταμείο Μετρητών']
        st.session_state.bank_list = sorted(list(set([x for x in existing + default if str(x) != 'nan' and str(x) != ''])))
else:
    st.error("⚠️ Ανεβάστε το Excel στο GitHub!"); st.stop()

df = st.session_state.df

# --- 4. SIDEBAR ---
st.sidebar.title("🏢 SalesTree ERP")
st.sidebar.info(f"👤 **{st.session_state.username}**")
if st.sidebar.button("Logout"): st.session_state.logged_in = False; st.rerun()
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

# --- 5. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Εικόνα Επιχείρησης")
    
    inc = df_filtered[df_filtered['DocType'] == 'Income']['Amount (Net)'].sum()
    exp = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    prof = inc - exp
    
    # Cashflow based on Paid status
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

# --- 6. TREASURY ---
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

# --- 7. JOURNAL ---
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
            "GL Account": st.column_config.NumberColumn("GL Code (Λογαριασμός)", help="Δες Ρυθμίσεις για επεξήγηση")
        }
    )
    if not edf.equals(v): st.session_state.df.update(edf); st.warning("⚠️ Κάντε Save!")

# --- 8. AGING ---
elif menu == "⏳ Aging":
    st.title("⏳ Οφειλές")
    u_in = df[(df['DocType'] == 'Income') & (df['Status'] == 'Unpaid')]
    u_out = df[(df['DocType'].isin(['Expense', 'Bill'])) & (df['Status'] == 'Unpaid')]
    c1, c2 = st.columns(2)
    with c1: st.subheader("Πελάτες"); st.dataframe(u_in[['DocDate','Counterparty','Amount (Gross)']]); st.metric("Σύνολο", f"€{u_in['Amount (Gross)'].sum():,.2f}")
    with c2: st.subheader("Προμηθευτές"); st.dataframe(u_out[['DocDate','Counterparty','Amount (Gross)']]); st.metric("Σύνολο", f"€{u_out['Amount (Gross)'].sum():,.2f}")

# --- 9. ΡΥΘΜΙΣΕΙΣ (ΕΝΗΜΕΡΩΜΕΝΟ) ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις & Βοήθεια")
    
    tab_info, tab_gl = st.tabs(["ℹ️ Σύστημα", "📚 Λογιστικό Σχέδιο (GL Accounts)"])
    
    with tab_info:
        st.subheader("Στοιχεία Σύνδεσης")
        st.info(f"Χρήστης: {st.session_state.username}")
        st.subheader("Τράπεζες")
        st.table(pd.DataFrame(st.session_state.bank_list, columns=["Τράπεζα"]))
    
    with tab_gl:
        st.subheader("Επεξήγηση Κωδικών (GL Codes)")
        st.write("Χρησιμοποιήστε αυτούς τους κωδικούς στη στήλη **GL Account** στο Ημερολόγιο.")
        
        # ΕΔΩ ΕΙΝΑΙ Ο ΠΙΝΑΚΑΣ ΠΟΥ ΖΗΤΗΣΕΣ
        gl_data = {
            "Κωδικός (GL)": [4000, 5000, 6000, 7000, 7010, 8000, 9999],
            "Περιγραφή": [
                "Έσοδα Υπηρεσιών / Πωλήσεις",
                "Άμεσα Κόστη (Πωληθέντων)",
                "Λειτουργικά Έξοδα (Ενοίκια, ΔΕΗ, κλπ)",
                "Τράπεζα (Assets)",
                "Ταμείο (Cash Assets)",
                "Διανομή Κερδών / Μερίσματα",
                "Αδιευκρίνιστα / Λάθος"
            ],
            "Τύπος": ["Έσοδο", "Έξοδο", "Έξοδο", "Ενεργητικό", "Ενεργητικό", "Κεφάλαιο", "-"]
        }
        st.table(pd.DataFrame(gl_data))
