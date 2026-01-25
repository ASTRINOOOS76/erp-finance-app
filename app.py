import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

# --- Ρυθμίσεις Σελίδας ---
st.set_page_config(page_title="ERP Finance Dashboard", layout="wide")

# --- Φόρτωση Δεδομένων ---
@st.cache_data
def load_data():
    # Φόρτωση του Journal
    journal_df = pd.read_csv("data/Journal.csv")
    
    # Μετατροπή ημερομηνιών σε σωστό format
    journal_df['DocDate'] = pd.to_datetime(journal_df['DocDate'], errors='coerce')
    journal_df['Payment Date'] = pd.to_datetime(journal_df['Payment Date'], errors='coerce')
    
    # Καθαρισμός ποσών (αφαίρεση συμβόλων αν υπάρχουν και μετατροπή σε float)
    cols_to_numeric = ['Amount (Net)', 'VAT Amount', 'Amount (Gross)']
    for col in cols_to_numeric:
        # Αν είναι string με κόμματα/σύμβολα, θέλει καθάρισμα. Αν είναι ήδη numbers, το αφήνουμε.
        if journal_df[col].dtype == 'object':
             journal_df[col] = pd.to_numeric(journal_df[col].astype(str).str.replace(',', ''), errors='coerce')
    
    # Φόρτωση Master Data (αν χρειαστεί για drop-downs αργότερα)
    # master_df = pd.read_csv("data/Master_Data.csv") 
    
    return journal_df

try:
    df = load_data()
except FileNotFoundError:
    st.error("Τα αρχεία CSV δεν βρέθηκαν στον φάκελο 'data/'.")
    st.stop()

# --- Sidebar (Πλοήγηση & Φίλτρα) ---
st.sidebar.title("SalesTree ERP")
page = st.sidebar.radio("Μενού", ["Dashboard", "Journal / Transactions", "Data Checks"])

st.sidebar.markdown("---")
st.sidebar.header("Φίλτρα")

# Φίλτρο Έτους
years = df['DocDate'].dt.year.unique()
selected_year = st.sidebar.selectbox("Επιλογή Έτους", sorted(years, reverse=True))

# Εφαρμογή φίλτρου
df_filtered = df[df['DocDate'].dt.year == selected_year]

# --- Σελίδα 1: Dashboard ---
if page == "Dashboard":
    st.title(f"📊 Οικονομική Επισκόπηση {selected_year}")

    # Υπολογισμοί KPIs
    income = df_filtered[df_filtered['DocType'] == 'Income']['Amount (Net)'].sum()
    expenses = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    net_result = income - expenses
    
    # Cashflow (βάσει Payment Date και Status='Paid')
    paid_in = df_filtered[(df_filtered['Status'] == 'Paid') & (df_filtered['DocType'] == 'Income')]['Amount (Gross)'].sum()
    paid_out = df_filtered[(df_filtered['Status'] == 'Paid') & (df_filtered['DocType'].isin(['Expense', 'Bill']))]['Amount (Gross)'].sum()
    cash_balance = paid_in - paid_out

    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Έσοδα (Net)", f"€{income:,.2f}")
    col2.metric("Έξοδα (Net)", f"€{expenses:,.2f}", delta_color="inverse")
    col3.metric("Καθαρό Κέρδος", f"€{net_result:,.2f}", delta=f"{net_result:,.2f}")
    col4.metric("Cashflow (Gross)", f"€{cash_balance:,.2f}")

    st.markdown("---")

    # Γράφημα Μηνιαίας Κίνησης
    df_filtered['Month'] = df_filtered['DocDate'].dt.strftime('%Y-%m')
    monthly_data = df_filtered.groupby(['Month', 'DocType'])['Amount (Net)'].sum().reset_index()
    
    # Κρατάμε μόνο Income και Expense για το γράφημα
    chart_data = monthly_data[monthly_data['DocType'].isin(['Income', 'Expense', 'Bill'])]
    
    fig = px.bar(chart_data, x='Month', y='Amount (Net)', color='DocType', 
                 title="Μηνιαία Έσοδα vs Έξοδα", barmode='group',
                 color_discrete_map={'Income': 'green', 'Expense': 'red', 'Bill': 'red'})
    st.plotly_chart(fig, use_container_width=True)

    # Breakdown ανά Κατηγορία (Expenses)
    st.subheader("Ανάλυση Εξόδων ανά Κατηγορία")
    expenses_only = df_filtered[df_filtered['DocType'].isin(['Expense', 'Bill'])]
    if not expenses_only.empty:
        fig_pie = px.pie(expenses_only, values='Amount (Net)', names='Category', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Δεν υπάρχουν έξοδα για το επιλεγμένο έτος.")

# --- Σελίδα 2: Journal ---
elif page == "Journal / Transactions":
    st.title("📝 Ημερολόγιο Συναλλαγών")
    
    # Αναζήτηση
    search_term = st.text_input("Αναζήτηση (Περιγραφή, Συνεργάτης, Κατηγορία)")
    
    if search_term:
        mask = df_filtered.apply(lambda x: x.astype(str).str.contains(search_term, case=False).any(), axis=1)
        display_df = df_filtered[mask]
    else:
        display_df = df_filtered

    # Εμφάνιση πίνακα
    st.dataframe(
        display_df.sort_values(by='DocDate', ascending=False),
        use_container_width=True,
        column_config={
            "DocDate": st.column_config.DateColumn("Ημερομηνία"),
            "Amount (Net)": st.column_config.NumberColumn("Καθαρό Ποσό", format="€%.2f"),
            "Amount (Gross)": st.column_config.NumberColumn("Μικτό Ποσό", format="€%.2f"),
        }
    )

# --- Σελίδα 3: Data Checks ---
elif page == "Data Checks":
    st.title("⚠️ Έλεγχοι & Exceptions")
    
    st.write("Έλεγχος βάσει των κανόνων του αρχείου Checks.csv")
    
    # 1. Paid but missing Payment Date
    check1 = df[(df['Status'] == 'Paid') & (df['Payment Date'].isna())]
    if not check1.empty:
        st.error(f"Βρέθηκαν {len(check1)} εγγραφές 'Paid' χωρίς ημερομηνία πληρωμής!")
        st.dataframe(check1[['DocNo', 'Description', 'Amount (Gross)', 'Status', 'Payment Date']])
    else:
        st.success("Όλες οι πληρωμένες εγγραφές έχουν ημερομηνία.")

    # 2. Missing Category
    check2 = df[df['Category'].isna() | (df['Category'] == '')]
    if not check2.empty:
        st.warning(f"Βρέθηκαν {len(check2)} εγγραφές χωρίς Κατηγορία.")
        st.dataframe(check2)
    else:
        st.success("Όλες οι εγγραφές έχουν Κατηγορία.")