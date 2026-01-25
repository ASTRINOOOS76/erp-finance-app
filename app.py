import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- Ρυθμίσεις Σελίδας ---
st.set_page_config(page_title="SalesTree Finance ERP", layout="wide", page_icon="💰")

# --- Debugging (θα το αφήσουμε λίγο ακόμα) ---
st.write(f"📂 **Τρέχων Φάκελος:** `{os.getcwd()}`")
files_in_folder = os.listdir()
st.write(f"📄 **Αρχεία φακέλου:** `{files_in_folder}`")

# --- Έξυπνη Φόρτωση Δεδομένων ---
@st.cache_data
def load_data():
    # Βρες όλα τα αρχεία που τελειώνουν σε .xlsx
    excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
    
    if not excel_files:
        st.error("❌ Δεν βρήκα κανένα αρχείο Excel (.xlsx) στον φάκελο!")
        return pd.DataFrame()
    
    # Πάρε το πρώτο που θα βρεις
    file_path = excel_files[0]
    st.success(f"✅ Βρέθηκε και χρησιμοποιείται το αρχείο: **{file_path}**")

    try:
        # Διάβασμα του Excel (Tab: Journal)
        df = pd.read_excel(file_path, sheet_name="Journal", engine='openpyxl')
        
        # Καθαρισμός
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
        
        numeric_cols = ['Amount (Net)', 'Amount (Gross)', 'VAT Amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Month'] = df['DocDate'].dt.to_period('M').astype(str)
        return df
        
    except ValueError as e:
        st.error(f"⚠️ Το αρχείο '{file_path}' βρέθηκε, αλλά δεν έχει καρτέλα 'Journal' ή είναι κατεστραμμένο.\nΛεπτομέρειες: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Γενικό Σφάλμα: {e}")
        return pd.DataFrame()

df = load_data()

# Αν δεν φορτώσει δεδομένα, σταματάμε εδώ
if df.empty:
    st.stop()

# --- Κύρια Εφαρμογή ---
st.sidebar.title("📊 SalesTree ERP")
years = sorted(df['DocDate'].dt.year.dropna().unique().astype(int), reverse=True)
if not years:
    st.warning("Το αρχείο δεν έχει ημερομηνίες!")
    st.stop()
    
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
    if not monthly.empty:
        monthly_grp = monthly.groupby(['Month', 'DocType'])['Amount (Net)'].sum().reset_index()
        st.plotly_chart(px.bar(monthly_grp, x='Month', y='Amount (Net)', color='DocType', barmode='group'), use_container_width=True)
    else:
        st.info("Δεν υπάρχουν κινήσεις για γραφήματα.")

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
        st.error(f"Βρέθηκαν {len(prob)} πληρωμένα χωρίς ημερομηνία!")
        st.dataframe(prob)
    else:
        st.success("Όλα καλά.")
