import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- Ρυθμίσεις Σελίδας ---
st.set_page_config(page_title="SalesTree Finance ERP", layout="wide")

# --- Debugging: Να δούμε τι βλέπει το Python ---
st.write("📂 **Τρέχων Φάκελος:**", os.getcwd())
st.write("📄 **Αρχεία που βλέπω εδώ:**", os.listdir())

# --- Φόρτωση Δεδομένων ---
@st.cache_data
def load_data():
    # Δοκιμάζουμε διάφορα ονόματα μήπως έχει γίνει λάθος στην μετονομασία
    possible_names = [
        "finance_data.xlsx", 
        "finance_data.xlsx.xlsx", 
        "SalesTree_Finance_ERP_style_FINAL.xlsx",
        "data/finance_data.xlsx"
    ]
    
    file_path = None
    for name in possible_names:
        if os.path.exists(name):
            file_path = name
            st.success(f"✅ Βρέθηκε το αρχείο: {name}")
            break
    
    if not file_path:
        st.error("❌ ΔΕΝ ΒΡΕΘΗΚΕ ΤΟ ΑΡΧΕΙΟ EXCEL. Κοίτα τη λίστα 'Αρχεία που βλέπω εδώ' πιο πάνω.")
        return pd.DataFrame()

    try:
        df = pd.read_excel(file_path, sheet_name="Journal", engine='openpyxl')
        
        # Καθαρισμός
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
        for col in ['Amount (Net)', 'Amount (Gross)']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df['Month'] = df['DocDate'].dt.to_period('M').astype(str)
        return df
    except Exception as e:
        st.error(f"Βρέθηκε το αρχείο αλλά χτύπησε λάθος: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.title("📊 SalesTree Finance")
    st.dataframe(df.head())
