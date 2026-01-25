import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- Ρυθμίσεις Σελίδας ---
st.set_page_config(page_title="SalesTree Finance ERP", layout="wide", page_icon="💰")

# --- CSS για εμφάνιση ---
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# --- Φόρτωση Δεδομένων από Excel ---
@st.cache_data
def load_data():
    file_path = "data/finance_data.xlsx"
    
    try:
        # Διαβάζουμε το Tab "Journal" από το Excel
        # engine='openpyxl' χρειάζεται για αρχεία .xlsx
        df = pd.read_excel(file_path, sheet_name="Journal", engine='openpyxl')
        
        # Καθαρισμός και μετατροπή ημερομηνιών
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
        
        # Καθαρισμός αριθμητικών πεδίων (αν κατά λάθος έχουν περάσει ως κείμενο)
        numeric_cols = ['Amount (Net)', 'Amount (Gross)', 'VAT Amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Δημιουργία στήλης Μήνα
        df['Month'] = df['DocDate'].dt.to_period('M').astype(str)
        
        return df
    except FileNotFoundError:
        st.error("Το αρχείο 'finance_data.xlsx' δεν βρέθηκε στον φάκελο 'data/'.")
        return pd.DataFrame()
    except ValueError as e:
        st.error(f"Πρόβλημα με την ανάγνωση του Tab 'Journal'. Βεβαιώσου ότι υπάρχει στο Excel. ({e})")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Σφάλμα: {e}")
        return pd.DataFrame()

df = load_data()

# Αν δεν υπάρχουν δεδομένα, σταμάτα εδώ
if df.empty:
    st.stop()

# --- Sidebar Filters ---
st.sidebar.title("📊 SalesTree Finance")

# Επιλογή Έτους
available_years = sorted(df['DocDate'].dt.year.dropna().unique().astype(int), reverse=True)
selected_year = st.sidebar.selectbox("Επιλογή Έτους", available_years)

# Φιλτράρισμα βάσει έτους
df_year = df[df['DocDate'].dt.year == selected_year]

# Πλοήγηση
page = st.sidebar.radio("Μενού", ["Dashboard", "Journal", "Checks"])

# --- Σελίδα 1: Dashboard ---
if page == "Dashboard":
    st.title(f"Οικονομική Επισκόπηση {selected_year}")

    # KPIs
    total_income = df_year[df_year['DocType'] == 'Income']['Amount (Net)'].sum()
    total_expense = df_year[df_year['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    net_profit = total_income - total_expense
    
    cash_in = df_year[(df_year['Status'] == 'Paid') & (df_year['DocType'] == 'Income')]['Amount (Gross)'].sum()
    cash_out = df_year[(df_year['Status'] == 'Paid') & (df_year['DocType'].isin(['Expense', 'Bill']))]['Amount (Gross)'].sum()
    net_cash = cash_in - cash_out

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Έσοδα (Net)", f"€{total_income:,.2f}")
    col2.metric("Έξοδα (Net)", f"€{total_expense:,.2f}", delta_color="inverse")
    col3.metric("Κέρδος/Ζημία", f"€{net_profit:,.2f}", delta=f"{net_profit:,.2f}")
    col4.metric("Ταμείο (Cash)", f"€{net_cash:,.2f}")

    st.divider()

    # Chart
    monthly_stats = df_year.groupby(['Month', 'DocType'])['Amount (Net)'].sum().reset_index()
    monthly_stats = monthly_stats[monthly_stats['DocType'].isin(['Income', 'Expense', 'Bill'])]
    
    fig = px.bar(monthly_stats, x='Month', y='Amount (Net)', color='DocType', 
                 title="Μηνιαία Κίνηση", barmode='group',
                 color_discrete_map={'Income': '#00CC96', 'Expense': '#EF553B', 'Bill': '#EF553B'})
    st.plotly_chart(fig, use_container_width=True)

# --- Σελίδα 2: Journal ---
elif page == "Journal":
    st.title("📝 Ημερολόγιο Συναλλαγών")
    
    search_text = st.text_input("🔍 Αναζήτηση")
    
    df_display = df_year.copy()
    if search_text:
        df_display = df_display[df_display.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)]

    st.dataframe(
        df_display.sort_values(by='DocDate', ascending=False),
        column_config={
            "DocDate": st.column_config.DateColumn("Ημ/νία"),
            "Amount (Net)": st.column_config.NumberColumn("Καθαρό", format="€%.2f"),
            "Amount (Gross)": st.column_config.NumberColumn("Μικτό", format="€%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )

# --- Σελίδα 3: Checks ---
elif page == "Checks":
    st.title("⚠️ Ποιοτικός Έλεγχος")
    
    # Check: Paid without Date
    missing_date = df[(df['Status'] == 'Paid') & (df['Payment Date'].isna())]
    if not missing_date.empty:
        st.error(f"Υπάρχουν {len(missing_date)} εγγραφές που φαίνονται Πληρωμένες (Paid) αλλά δεν έχουν Ημερομηνία Πληρωμής!")
        st.dataframe(missing_date)
    else:
        st.success("Όλα καλά με τις ημερομηνίες πληρωμών.")
