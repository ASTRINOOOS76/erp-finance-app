import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import os
from datetime import datetime, date

# --- 1. ΡΥΘΜΙΣΕΙΣ ΣΕΛΙΔΑΣ ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="🏢")

# --- CSS (Στυλ) ---
st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #f0f2f6; border-radius: 5px;
        padding-top: 10px; padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] { background-color: #4CAF50; color: white; }
</style>
""", unsafe_allow_html=True)

# --- 2. ΣΥΣΤΗΜΑ LOGIN ---
def check_login():
    users = {
        "admin": "admin123",
        "user": "1234"
    }

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("🔐 SalesTree ERP Login")
            st.markdown("Παρακαλώ συνδεθείτε.")
            
            username = st.text_input("Όνομα Χρήστη")
            password = st.text_input("Κωδικός Πρόσβασης", type="password")
            
            if st.button("Είσοδος"):
                if username in users and users[username] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success("Επιτυχής σύνδεση!")
                    st.rerun()
                else:
                    st.error("Λάθος στοιχεία.")
        st.stop()

check_login()

# --- 3. ΦΟΡΤΩΣΗ ΔΕΔΟΜΕΝΩΝ ---
def get_excel_path():
    excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
    return excel_files[0] if excel_files else None

@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name="Journal", engine='openpyxl')
        
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
        
        numeric_cols = ['Amount (Net)', 'Amount (Gross)', 'VAT Amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        cols_needed = ['DocType', 'Payment Method', 'Bank Account', 'Counterparty', 'Status', 'Description', 'Category']
        for c in cols_needed:
            if c not in df.columns: df[c] = ""
                
        df.loc[df['Payment Method'] == 'Cash', 'Bank Account'] = 'Ταμείο Μετρητών'
        return df
    except Exception as e:
        return None

path = get_excel_path()
if path:
    if 'df' not in st.session_state:
        st.session_state.df = load_data(path)
    if 'bank_list' not in st.session_state:
        existing_banks = st.session_state.df['Bank Account'].unique().tolist() if st.session_state.df is not None else []
        default_banks = ['Alpha Bank', 'Eurobank', 'Piraeus', 'National Bank', 'Revolut', 'Ταμείο Μετρητών']
        all_banks = list(set([x for x in existing_banks + default_banks if str(x) != 'nan' and str(x) != '']))
        st.session_state.bank_list = sorted(all_banks)
else:
    st.error("⚠️ Δεν βρέθηκε αρχείο Excel. Ανέβασέ το στο GitHub!")
    st.stop()

df = st.session_state.df

# --- 4. SIDEBAR & ΦΙΛΤΡΑ ---
st.sidebar.title("🏢 SalesTree ERP")
st.sidebar.info(f"👤 **{st.session_state.username}**")
if st.sidebar.button("Έξοδος"):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.divider()

# Ημερομηνίες
st.sidebar.header("📅 Περίοδος")
today = date.today()
default_start = date(today.year, 1, 1)
default_end = date(today.year, 12, 31)
date_range = st.sidebar.date_input("Επιλογή", value=(default_start, default_end), format="DD/MM/YYYY")

if len(date_range) == 2:
    start_date, end_date = date_range
    mask = (df['DocDate'].dt.date >= start_date) & (df['DocDate'].dt.date <= end_date)
    df_filtered = df[mask]
else:
    df_filtered = df

menu = st.sidebar.radio("Μενού", [
    "📊 Dashboard", 
    "🏦 Treasury", 
    "📝 Journal", 
    "⏳ Aging (Οφειλές)",
    "⚙️ Ρυθμίσεις"
])

# --- 5. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Εικόνα Επιχείρησης")
    st.caption(f"Περίοδος: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    income = df_filtered[df_filtered['DocType'] == 'Income']['Amount (Net)'].sum()
    expenses = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    profit = income - expenses
    margin = (profit / income * 100) if income > 0 else 0
    
    paid_in = df_filtered[(df_filtered['Status']=='Paid') & (df_filtered['DocType']=='Income')]['Amount (Gross)'].sum()
    paid_out = df_filtered[(df_filtered['Status']=='Paid') & (df_filtered['DocType']!='Income')]['Amount (Gross)'].sum()

    col1.metric("Πωλήσεις (Net)", f"€{income:,.0f}", "+")
    col2.metric("Λειτουργικά Έξοδα", f"€{expenses:,.0f}", "-")
    col3.metric("EBITDA (Κέρδη)", f"€{profit:,.0f}", f"{margin:.1f}%")
    col4.metric("Ταμειακή Ροή", f"€{(paid_in-paid_out):,.0f}")
    
    st.divider()
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("🗓️ Μηνιαία Κίνηση")
        if not df_filtered.empty:
            monthly = df_filtered.copy()
            monthly['Month'] = monthly['DocDate'].dt.strftime('%Y-%m')
            grp = monthly.groupby(['Month', 'DocType'])['Amount (Net)'].sum().reset_index()
            grp = grp[grp['DocType'].isin(['Income', 'Expense'])]
            
            fig = px.bar(grp, x='Month', y='Amount (Net)', color='DocType', barmode='group',
                         color_discrete_map={'Income': '#2ecc71', 'Expense': '#e74c3c'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Δεν υπάρχουν κινήσεις για αυτή την περίοδο.")
        
    with c2:
        st.subheader("🍰 Κέντρα Κόστους")
        exp = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]
        if not exp.empty:
            fig2 = px.pie(exp, values='Amount (Net)', names='Category', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Δεν υπάρχουν έξοδα.")

# --- 6. TREASURY ---
elif menu == "🏦 Treasury":
    st.title("🏦 Διαχείριση Ρευστότητας")
    tab1, tab2, tab3 = st.tabs(["💰 Υπόλοιπα", "📈 Κίνηση", "➕ Νέα Τράπεζα"])
    
    with tab1:
        st.write("*(Συνολικά υπόλοιπα μέχρι σήμερα)*")
        df_paid = df[df['Status'] == 'Paid'].copy()
        df_paid['SignedAmount'] = df_paid.apply(lambda x: x['Amount (Gross)'] if x['DocType'] == 'Income' else -x['Amount (Gross)'], axis=1)
        
        balances = df_paid.groupby('Bank Account')['SignedAmount'].sum().reset_index()
        balances.columns = ['Λογαριασμός', 'Υπόλοιπο']
        
        st.metric("Σύνολο Διαθεσίμων", f"€{balances['Υπόλοιπο'].sum():,.2f}")
        
        if not balances.empty:
            cols = st.columns(3)
            for index, row in balances.iterrows():
                with cols[index % 3]:
                    st.info(f"**{row['Λογαριασμός']}**\n\n### €{row['Υπόλοιπο']:,.2f}")

    with tab2:
        if 'bank_list' in st.session_state and st.session_state.bank_list:
            selected_bank = st.selectbox("Επιλογή Λογαριασμού", st.session_state.bank_list)
            bank_txns = df_filtered[(df_filtered['Bank Account'] == selected_bank) & (df_filtered['Status']=='Paid')].sort_values('DocDate')
            
            if not bank_txns.empty:
                st.dataframe(bank_txns[['DocDate', 'Description', 'Amount (Gross)', 'DocType']], use_container_width=True)
            else:
                st.warning(f"Δεν υπάρχουν κινήσεις για {selected_bank}.")
        else:
            st.warning("Δεν υπάρχουν τράπεζες.")

    with tab3:
        with st.form("add_bank"):
            new_bank = st.text_input("Νέος Λογαριασμός")
            if st.form_submit_button("Προσθήκη"):
                if 'bank_list' not in st.session_state: st.session_state.bank_list = []
                st.session_state.bank_list.append(new_bank)
                st.success("Προστέθηκε!")

# --- 7. JOURNAL ---
elif menu == "📝 Journal":
    st.title("📝 Ημερολόγιο Συναλλαγών")
    
    # Export Button
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        st.session_state.df.to_excel(writer, sheet_name='Journal', index=False)
    st.download_button("💾 Κατέβασμα Excel (Backup)", buffer, "Finance_Data_Backup.xlsx")

    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Αναζήτηση")
    type_filter = c2.multiselect("Τύπος", df['DocType'].unique())
    
    df_view = df_filtered.copy()
    if search:
        df_view = df_view[df_view.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
    if type_filter:
        df_view = df_view[df_view['DocType'].isin(type_filter)]

    banks_options = st.session_state.bank_list if 'bank_list' in st.session_state else []
    edited_df = st.data_editor(
        df_view.sort_values('DocDate', ascending=False),
        num_rows="dynamic",
        column_config={
            "DocDate": st.column_config.DateColumn("Ημερομηνία"),
            "Amount (Net)": st.column_config.NumberColumn("Καθαρό", format="€%.2f"),
            "Bank Account": st.column_config.SelectboxColumn("Λογαριασμός", options=banks_options),
            "DocType": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill", "Equity Distribution"]),
            "Status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"]),
        },
        use_container_width=True,
        hide_index=True
    )
    
    if not edited_df.equals(df_view):
        st.warning("⚠️ Πραγματοποιείτε αλλαγές. Μην ξεχάσετε να κατεβάσετε το αρχείο!")
        st.session_state.df.update(edited_df)

# --- 8. AGING ---
elif menu == "⏳ Aging (Οφειλές)":
    st.title("⏳ Οφειλές & Απαιτήσεις")
    st.info("💡 Εμφανίζονται όλες οι ανοιχτές υποχρεώσεις ανεξαρτήτως ημερομηνίας.")

    unpaid_in = df[(df['DocType'] == 'Income') & (df['Status'] == 'Unpaid')]
    unpaid_out = df[(df['DocType'].isin(['Expense', 'Bill'])) & (df['Status'] == 'Unpaid')]

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Μας Χρωστάνε (Πελάτες)")
        if not unpaid_in.empty:
            st.dataframe(unpaid_in[['DocDate', 'Counterparty', 'Amount (Gross)']], use_container_width=True)
            st.metric("Σύνολο", f"€{unpaid_in['Amount (Gross)'].sum():,.2f}")
        else:
            st.success("Καμία οφειλή πελάτη.")

    with c2:
        st.subheader("Χρωστάμε (Προμηθευτές)")
        if not unpaid_out.empty:
            st.dataframe(unpaid_out[['DocDate', 'Counterparty', 'Amount (Gross)']], use_container_width=True)
            st.error(f"Σύνολο: €{unpaid_out['Amount (Gross)'].sum():,.2f}")
        else:
            st.success("Καμία οφειλή σε προμηθευτή.")

# --- 9. ΡΥΘΜΙΣΕΙΣ (FIXED) ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Πίνακας Ελέγχου")
    
    # 1. Profile Section
    st.subheader("👤 Προφίλ Χρήστη")
    col1, col2 = st.columns(2)
    col1.info(f"🔑 Συνδεδεμένος ως: **{st.session_state.username}**")
    col2.warning(f"📅 Επιλεγμένη Περίοδος: **{start_date.strftime('%d/%m/%Y')}** έως **{end_date.strftime('%d/%m/%Y')}**")
    
    st.divider()
    
    # 2. Bank List (Clean Table)
    st.subheader("🏦 Ενεργοί Λογαριασμοί Τραπεζών")
    st.write("Οι παρακάτω λογαριασμοί είναι διαθέσιμοι για επιλογή στις εγγραφές:")
    
    if 'bank_list' in st.session_state:
        # Δείχνουμε τη λίστα σαν ωραίο πίνακα (DataFrame)
        banks_df = pd.DataFrame(st.session_state.bank_list, columns=["Όνομα Λογαριασμού"])
        st.dataframe(banks_df, use_container_width=True, hide_index=True)
    else:
        st.write("Δεν υπάρχουν καταχωρημένες τράπεζες.")
    
    st.divider()
    
    # 3. System Stats
    st.subheader("📊 Στατιστικά Συστήματος")
    c1, c2 = st.columns(2)
    c1.metric("Συνολικές Εγγραφές στη Βάση", len(df))
    c2.metric("Τελευταία Ενημέρωση", datetime.now().strftime("%H:%M"))
