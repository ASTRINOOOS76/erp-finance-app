import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- Ρυθμίσεις Σελίδας ---
st.set_page_config(page_title="SalesTree Finance ERP", layout="wide", page_icon="💰")

# --- Φόρτωση Δεδομένων ---
@st.cache_data
def load_data():
    # ΕΔΩ ΕΙΝΑΙ Η ΔΙΑΔΡΟΜΗ ΓΙΑ ΤΟΝ ΦΑΚΕΛΟ DATA
    file_path = "data/finance_data.xlsx"
    
    try:
        # Διάβασμα του Excel (Tab: Journal)
        df = pd.read_excel(file_path, sheet_name="Journal", engine='openpyxl')
        
        # Καθαρισμός ημερομηνιών
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
        
        # Καθαρισμός αριθμών
        numeric_cols = ['Amount (Net)', 'Amount (Gross)', 'VAT Amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Στήλη Μήνα
        df['Month'] = df['DocDate'].dt.to_period('M').astype(str)
        
        return df
    except FileNotFoundError:
        st.error(f"Δεν βρίσκω το αρχείο! Ψάχνω εδώ: {file_path}")
        st.info("Σιγουρέψου ότι το αρχείο Excel είναι μέσα στον φάκελο 'data' και λέγεται 'finance_data.xlsx'")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Κάτι πήγε στραβά: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.stop()

# --- Sidebar ---
st.sidebar.title("📊 SalesTree ERP")
years = sorted(df['DocDate'].dt.year.dropna().unique().astype(int), reverse=True)
selected_year = st.sidebar.selectbox("Έτος", years)

df_year = df[df['DocDate'].dt.year == selected_year]
page = st.sidebar.radio("Μενού", ["Dashboard", "Journal", "Checks"])

# --- Σελίδα 1: Dashboard ---
if page == "Dashboard":
    st.title(f"Εικόνα {selected_year}")
    
    # KPIs
    inc = df_year[df_year['DocType'] == 'Income']['Amount (Net)'].sum()
    exp = df_year[df_year['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Έσοδα", f"€{inc:,.2f}")
    col2.metric("Έξοδα", f"€{exp:,.2f}")
    col3.metric("Κέρδος", f"€{inc - exp:,.2f}")
    
    st.divider()
    
    # Chart
    monthly = df_year[df_year['DocType'].isin(['Income', 'Expense', 'Bill'])]
    monthly_grp = monthly.groupby(['Month', 'DocType'])['Amount (Net)'].sum().reset_index()
    
    st.plotly_chart(px.bar(monthly_grp, x='Month', y='Amount (Net)', color='DocType', barmode='group'), use_container_width=True)

# --- Σελίδα 2: Journal ---
elif page == "Journal":
    st.title("📝 Ημερολόγιο")
    search = st.text_input("Αναζήτηση...")
    
    if search:
        df_year = df_year[df_year.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        
    st.dataframe(df_year.sort_values('DocDate', ascending=False), use_container_width=True, hide_index=True)

# --- Σελίδα 3: Checks ---
elif page == "Checks":
    st.title("⚠️ Έλεγχοι")
    prob = df[(df['Status']=='Paid') & (df['Payment Date'].isna())]
    if not prob.empty:
        st.error(f"Βρήκα {len(prob)} πληρωμένα χωρίς ημερομηνία!")
        st.dataframe(prob)
    else:
        st.success("Όλα κομπλέ.")

