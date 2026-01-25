import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import os
from datetime import datetime, date

# --- Ρυθμίσεις Σελίδας & Θέμα ---
st.set_page_config(page_title="SalesTree ERP System", layout="wide", page_icon="🏢")

# --- Custom CSS για "ERP Look" ---
st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 5px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4CAF50;
        color: white;
    }
    h1, h2, h3 { color: #2c3e50; }
</style>
""", unsafe_allow_html=True)

# --- Βοηθητικές Συναρτήσεις ---
def get_excel_path():
    excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
    return excel_files[0] if excel_files else None

@st.cache_data
def load_data(file_path):
    try:
        # Διάβασμα Journal
        df = pd.read_excel(file_path, sheet_name="Journal", engine='openpyxl')
        
        # Προσπάθεια ανάγνωσης Master Data (για Τράπεζες)
        try:
            banks_df = pd.read_excel(file_path, sheet_name="Master_Data", engine='openpyxl')
            # Ψάχνουμε τη στήλη με τα ονόματα τραπεζών (υποθέτουμε ότι υπάρχει)
            # Αν δεν υπάρχει, θα φτιάξουμε μια dummy λίστα
        except:
            banks_df = pd.DataFrame()

        # Καθαρισμός Journal
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
        
        numeric_cols = ['Amount (Net)', 'Amount (Gross)', 'VAT Amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Εξασφάλιση απαραίτητων στηλών
        cols_needed = ['DocType', 'Payment Method', 'Bank Account', 'Counterparty', 'Status', 'Description']
        for c in cols_needed:
            if c not in df.columns:
                df[c] = ""
                
        # Αν η στήλη Bank Account είναι κενή σε μετρητά, βάλε "Cash Desk"
        df.loc[df['Payment Method'] == 'Cash', 'Bank Account'] = 'Ταμείο Μετρητών'

        return df
    except Exception as e:
        return None

# --- Φόρτωση State ---
path = get_excel_path()
if path:
    if 'df' not in st.session_state:
        st.session_state.df = load_data(path)
        # Φτιάχνουμε μια λίστα τραπεζών από τα υπάρχοντα δεδομένα + default
        existing_banks = st.session_state.df['Bank Account'].unique().tolist()
        default_banks = ['Alpha Bank', 'Eurobank', 'Piraeus', 'National Bank', 'Revolut', 'Ταμείο Μετρητών']
        # Ενωση λιστών και καθαρισμός κενών
        all_banks = list(set([x for x in existing_banks + default_banks if str(x) != 'nan' and str(x) != '']))
        st.session_state.bank_list = sorted(all_banks)
else:
    st.error("⚠️ Δεν βρέθηκε αρχείο Excel. Ανέβασέ το στο GitHub!")
    st.stop()

df = st.session_state.df

# --- SIDEBAR MENU ---
st.sidebar.title("🏢 SalesTree ERP")
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50) # Εικονίδιο ERP
menu = st.sidebar.radio("Modules", [
    "📊 Dashboard", 
    "🏦 Treasury (Ταμεία & Τράπεζες)", 
    "📝 Journal (Εγγραφές)", 
    "⏳ Aging & Debts (Οφειλές)",
    "⚙️ Ρυθμίσεις"
])
st.sidebar.divider()

# Global Filter
years = sorted(df['DocDate'].dt.year.dropna().unique().astype(int), reverse=True)
selected_year = st.sidebar.selectbox("Οικονομική Χρήση", years)
df_year = df[df['DocDate'].dt.year == selected_year]

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title(f"Επιχειρηματική Εικόνα {selected_year}")
    
    # KPIs Top Row
    col1, col2, col3, col4 = st.columns(4)
    
    income = df_year[df_year['DocType'] == 'Income']['Amount (Net)'].sum()
    expenses = df_year[df_year['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    profit = income - expenses
    margin = (profit / income * 100) if income > 0 else 0
    
    col1.metric("Πωλήσεις (Net)", f"€{income:,.0f}", "+")
    col2.metric("Λειτουργικά Έξοδα", f"€{expenses:,.0f}", "-")
    col3.metric("EBITDA (Κέρδη)", f"€{profit:,.0f}", f"{margin:.1f}%")
    
    # Cashflow KPI
    paid_in = df_year[(df_year['Status']=='Paid') & (df_year['DocType']=='Income')]['Amount (Gross)'].sum()
    paid_out = df_year[(df_year['Status']=='Paid') & (df_year['DocType']!='Income')]['Amount (Gross)'].sum()
    col4.metric("Ταμειακή Ροή", f"€{(paid_in-paid_out):,.0f}")
    
    st.divider()
    
    # Main Charts
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("🗓️ Μηνιαία Αποτελέσματα")
        monthly = df_year.copy()
        monthly['Month'] = monthly['DocDate'].dt.strftime('%Y-%m')
        grp = monthly.groupby(['Month', 'DocType'])['Amount (Net)'].sum().reset_index()
        grp = grp[grp['DocType'].isin(['Income', 'Expense'])]
        
        fig = px.bar(grp, x='Month', y='Amount (Net)', color='DocType', barmode='group',
                     color_discrete_map={'Income': '#2ecc71', 'Expense': '#e74c3c'})
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("🍰 Κέντρα Κόστους")
        exp = df_year[df_year['DocType'].isin(['Expense', 'Bill'])]
        if not exp.empty:
            fig2 = px.donut(exp, values='Amount (Net)', names='Category', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Δεν υπάρχουν έξοδα.")

# --- 2. TREASURY (Banks) ---
elif menu == "🏦 Treasury (Ταμεία & Τράπεζες)":
    st.title("🏦 Διαχείριση Ρευστότητας & Τραπεζών")
    
    # Tabs για οργάνωση
    tab1, tab2, tab3 = st.tabs(["💰 Επισκόπηση Υπολοίπων", "📈 Ανάλυση Κίνησης", "➕ Προσθήκη Τράπεζας"])
    
    with tab1:
        # Υπολογισμός υπολοίπων ανά τράπεζα (Running Total από την αρχή του χρόνου έως σήμερα)
        # Προσοχή: Εδώ παίρνουμε ΟΛΑ τα έτη για να βγει το σωστό υπόλοιπο, όχι μόνο το selected_year
        df_paid = df[df['Status'] == 'Paid'].copy()
        
        # Λογική: Income προσθέτει, Expense αφαιρεί
        df_paid['SignedAmount'] = df_paid.apply(
            lambda x: x['Amount (Gross)'] if x['DocType'] == 'Income' else -x['Amount (Gross)'], axis=1
        )
        
        # Group by Bank Account
        balances = df_paid.groupby('Bank Account')['SignedAmount'].sum().reset_index()
        balances.columns = ['Τράπεζα / Ταμείο', 'Υπόλοιπο']
        
        # Συνολικό Ταμείο
        total_cash = balances['Υπόλοιπο'].sum()
        st.metric("💵 Συνολική Ρευστότητα Επιχείρησης", f"€{total_cash:,.2f}")
        
        # Grid με κάρτες για κάθε τράπεζα
        st.subheader("Διαθέσιμα ανά Λογαριασμό")
        
        cols = st.columns(3)
        for index, row in balances.iterrows():
            col = cols[index % 3]
            bank_name = row['Τράπεζα / Ταμείο']
            amount = row['Υπόλοιπο']
            if bank_name: # Αν δεν είναι κενό
                with col:
                    st.info(f"**{bank_name}**\n\n### €{amount:,.2f}")

    with tab2:
        st.subheader("Κίνηση Λογαριασμών")
        selected_bank = st.selectbox("Επίλεξε Λογαριασμό για προβολή", st.session_state.bank_list)
        
        bank_txns = df_paid[df_paid['Bank Account'] == selected_bank].sort_values('DocDate')
        
        if not bank_txns.empty:
            # Υπολογισμός Running Balance για το γράφημα
            bank_txns['Balance'] = bank_txns.apply(
                lambda x: x['Amount (Gross)'] if x['DocType'] == 'Income' else -x['Amount (Gross)'], axis=1
            ).cumsum()
            
            # Γράφημα Γραμμής (Trend)
            fig_line = px.line(bank_txns, x='DocDate', y='Balance', title=f'Εξέλιξη Υπολοίπου: {selected_bank}', markers=True)
            fig_line.update_traces(line_color='#2980b9')
            st.plotly_chart(fig_line, use_container_width=True)
            
            # Πίνακας Κινήσεων
            st.dataframe(bank_txns[['DocDate', 'DocType', 'Counterparty', 'Description', 'Amount (Gross)']].sort_values('DocDate', ascending=False), use_container_width=True)
        else:
            st.warning("Δεν βρέθηκαν συναλλαγές για αυτόν τον λογαριασμό.")

    with tab3:
        st.subheader("Δημιουργία Νέου Λογαριασμού")
        with st.form("add_bank_form"):
            new_bank_name = st.text_input("Όνομα Τράπεζας / Λογαριασμού (π.χ. 'PayPal', 'Eurobank Όψεως')")
            submitted = st.form_submit_button("Προσθήκη στη Λίστα")
            if submitted and new_bank_name:
                if new_bank_name not in st.session_state.bank_list:
                    st.session_state.bank_list.append(new_bank_name)
                    st.success(f"Ο λογαριασμός '{new_bank_name}' προστέθηκε! Τώρα μπορείτε να τον επιλέξετε στις εγγραφές.")
                else:
                    st.warning("Αυτός ο λογαριασμός υπάρχει ήδη.")

# --- 3. JOURNAL (Data Entry) ---
elif menu == "📝 Journal (Εγγραφές)":
    st.title("📝 Διαχείριση Συναλλαγών")
    
    # EXPORT BUTTON TOP
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        st.session_state.df.to_excel(writer, sheet_name='Journal', index=False)
    
    st.download_button(
        label="💾 SAVE: Κατέβασμα Excel για αποθήκευση",
        data=buffer,
        file_name="Finance_Data_v2.xlsx",
        mime="application/vnd.ms-excel",
        key='download-btn'
    )
    st.caption("⚠️ Θυμήσου: Αφού κάνεις αλλαγές, κατέβασε το αρχείο και ανέβασέ το στο GitHub!")

    # Φίλτρα
    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Αναζήτηση Συναλλαγής")
    type_filter = c2.multiselect("Φίλτρο Τύπου", df['DocType'].unique())
    
    # Data View
    df_display = df_year.copy()
    if search:
        df_display = df_display[df_display.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
    if type_filter:
        df_display = df_display[df_display['DocType'].isin(type_filter)]

    # EDITABLE GRID
    edited_df = st.data_editor(
        df_display.sort_values('DocDate', ascending=False),
        num_rows="dynamic",
        column_config={
            "DocDate": st.column_config.DateColumn("Ημερομηνία"),
            "Amount (Net)": st.column_config.NumberColumn("Καθαρό", format="€%.2f"),
            "Amount (Gross)": st.column_config.NumberColumn("Μικτό", format="€%.2f"),
            "VAT Amount": st.column_config.NumberColumn("ΦΠΑ", format="€%.2f"),
            "DocType": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill", "Equity Distribution"]),
            "Payment Method": st.column_config.SelectboxColumn("Πληρωμή", options=["Cash", "Bank Transfer", "Card"]),
            "Bank Account": st.column_config.SelectboxColumn("Λογαριασμός", options=st.session_state.bank_list), # ΕΔΩ ΧΡΗΣΙΜΟΠΟΙΟΥΜΕ ΤΗ ΛΙΣΤΑ
            "Status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"]),
        },
        use_container_width=True,
        hide_index=True,
        key="journal_editor"
    )
    
    # Save changes logic (simple update of session state)
    if not edited_df.equals(df_display):
        # Update logic needs to be robust in full app, here we assume direct update for filtered view
        # For simplicity in this demo, we assume user is editing the filtered view and we might lose data if not careful.
        # So we warn:
        st.warning("⚠️ Πραγματοποιείτε αλλαγές. Μην ξεχάσετε να πατήσετε το 'SAVE' κουμπί επάνω.")
        # In a real app, we would merge 'edited_df' back into 'st.session_state.df' using Index matching.
        # For MVP: We update the master dataframe
        st.session_state.df.update(edited_df)

# --- 4. AGING (Debts) ---
elif menu == "⏳ Aging & Debts (Οφειλές)":
    st.title("⏳ Ενηλικίωση Υπολοίπων (Aging Report)")
    
    # Πελάτες (Receivables)
    st.subheader("🟢 Απαιτήσεις από Πελάτες (Ποιοι μας χρωστάνε)")
    unpaid_income = df[(df['DocType'] == 'Income') & (df['Status'] == 'Unpaid')]
    
    if not unpaid_income.empty:
        unpaid_income['DaysOpen'] = (pd.Timestamp.now() - unpaid_income['DocDate']).dt.days
        
        # Bucket function
        def get_bucket(days):
            if days < 30: return "0-30 Ημέρες"
            elif days < 60: return "30-60 Ημέρες"
            elif days < 90: return "60-90 Ημέρες"
            else: return "90+ Ημέρες (Κίνδυνος)"
            
        unpaid_income['Period'] = unpaid_income['DaysOpen'].apply(get_bucket)
        
        # Pivot Table
        aging_pivot = unpaid_income.pivot_table(index='Counterparty', columns='Period', values='Amount (Gross)', aggfunc='sum', fill_value=0)
        st.dataframe(aging_pivot.style.background_gradient(cmap="Reds", axis=None).format("€{:.2f}"), use_container_width=True)
    else:
        st.success("Κανένας πελάτης δεν χρωστάει!")

    st.divider()

    # Προμηθευτές (Payables)
    st.subheader("🔴 Υποχρεώσεις σε Προμηθευτές (Ποιους χρωστάμε)")
    unpaid_bills = df[(df['DocType'].isin(['Bill', 'Expense'])) & (df['Status'] == 'Unpaid')]
    
    if not unpaid_bills.empty:
        unpaid_bills['DaysOpen'] = (pd.Timestamp.now() - unpaid_bills['DocDate']).dt.days
        st.dataframe(unpaid_bills[['DocDate', 'Counterparty', 'Description', 'Amount (Gross)', 'DaysOpen']].sort_values('DaysOpen', ascending=False), use_container_width=True)
        
        total_debt = unpaid_bills['Amount (Gross)'].sum()
        st.error(f"Συνολικό Χρέος προς τρίτους: €{total_debt:,.2f}")
    else:
        st.success("Δεν χρωστάμε τίποτα!")

# --- 5. SETTINGS ---
elif menu == "⚙️ Ρυθμίσεις":
    st.title("⚙️ Ρυθμίσεις ERP")
    
    st.subheader("Διαχείριση Λιστών")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("🏦 **Ενεργοί Λογαριασμοί Τραπεζών**")
        st.table(pd.DataFrame(st.session_state.bank_list, columns=["Όνομα Λογαριασμού"]))
        
    with col2:
        st.write("📁 **Διαγνωστικά Συστήματος**")
        st.json({
            "Loaded File": path,
            "Total Rows": len(df),
            "Memory Usage (MB)": f"{df.memory_usage(deep=True).sum() / 1024**2:.2f}"
        })
