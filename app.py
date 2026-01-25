import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime

# --- Ρυθμίσεις Σελίδας ---
st.set_page_config(page_title="SalesTree ERP", layout="wide", page_icon="💶")

# --- CSS για εμφάνιση ---
st.markdown("""
<style>
    .metric-card {background-color: #f9f9f9; border-radius: 10px; padding: 15px; border: 1px solid #ddd;}
    .big-font {font-size:20px !important; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- Φόρτωση Δεδομένων ---
@st.cache_data
def load_data():
    # Ψάχνουμε το αρχείο
    excel_files = [f for f in os.listdir() if f.endswith('.xlsx') and not f.startswith('~$')]
    if not excel_files:
        return None, None
    
    file_path = excel_files[0]
    try:
        df = pd.read_excel(file_path, sheet_name="Journal", engine='openpyxl')
        
        # Μετατροπές
        df['DocDate'] = pd.to_datetime(df['DocDate'], errors='coerce')
        df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
        
        numeric_cols = ['Amount (Net)', 'Amount (Gross)', 'VAT Amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        # Σιγουρεύουμε ότι υπάρχουν οι στήλες για να μην χτυπάει
        required_cols = ['DocType', 'Payment Method', 'Category', 'Counterparty', 'Description', 'Status']
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        return df, file_path
    except Exception as e:
        st.error(f"Σφάλμα ανάγνωσης: {e}")
        return None, None

# Φόρτωση στην αρχή (Session State για να κρατάμε τις αλλαγές όσο είναι ανοιχτό)
if 'df' not in st.session_state:
    loaded_df, loaded_path = load_data()
    if loaded_df is not None:
        st.session_state.df = loaded_df
        st.session_state.file_path = loaded_path
    else:
        st.error("❌ Δεν βρέθηκε αρχείο Excel (.xlsx). Ανέβασέ το στο GitHub!")
        st.stop()

df = st.session_state.df

# --- Sidebar ---
st.sidebar.title("📊 SalesTree ERP")
st.sidebar.markdown("---")
page = st.sidebar.radio("Μενού", [
    "🏠 Επισκόπηση (Dashboard)", 
    "📝 Εγγραφές & Διορθώσεις", 
    "🏛️ ΦΠΑ & Εφορία", 
    "💰 Ταμείο & Τράπεζες",
    "👥 Μέτοχοι & Μερίσματα"
])
st.sidebar.markdown("---")

# Φίλτρο Έτους (Global)
years = sorted(df['DocDate'].dt.year.dropna().unique().astype(int), reverse=True)
selected_year = st.sidebar.selectbox("Οικονομικό Έτος", years)
df_year = df[df['DocDate'].dt.year == selected_year]

# --- Σελίδα 1: Dashboard ---
if page == "🏠 Επισκόπηση (Dashboard)":
    st.title(f"📊 Οικονομική Εικόνα {selected_year}")
    
    # Υπολογισμοί
    income_net = df_year[df_year['DocType'] == 'Income']['Amount (Net)'].sum()
    expense_net = df_year[df_year['DocType'].isin(['Expense', 'Bill'])]['Amount (Net)'].sum()
    profit = income_net - expense_net
    
    # ΦΠΑ
    vat_collected = df_year[df_year['DocType'] == 'Income']['VAT Amount'].sum()
    vat_paid = df_year[df_year['DocType'].isin(['Expense', 'Bill'])]['VAT Amount'].sum()
    vat_payable = vat_collected - vat_paid

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Τζίρος (Καθαρός)", f"€{income_net:,.2f}")
    c2.metric("💸 Έξοδα (Καθαρά)", f"€{expense_net:,.2f}")
    c3.metric("📈 Κέρδος", f"€{profit:,.2f}", delta_color="normal")
    c4.metric("🏛️ ΦΠΑ προς Απόδοση", f"€{vat_payable:,.2f}", delta_color="inverse")

    st.divider()
    
    # Γράφημα
    monthly = df_year.copy()
    monthly['Month'] = monthly['DocDate'].dt.to_period('M').astype(str)
    chart_df = monthly.groupby(['Month', 'DocType'])['Amount (Net)'].sum().reset_index()
    chart_df = chart_df[chart_df['DocType'].isin(['Income', 'Expense'])]
    
    st.plotly_chart(px.bar(chart_df, x='Month', y='Amount (Net)', color='DocType', barmode='group', 
                           color_discrete_map={'Income': 'green', 'Expense': 'red'}), use_container_width=True)

# --- Σελίδα 2: Εγγραφές & Διορθώσεις ---
elif page == "📝 Εγγραφές & Διορθώσεις":
    st.title("📝 Διαχείριση Εγγραφών")
    st.info("💡 Μπορείς να επεξεργαστείς τα δεδομένα απευθείας στον πίνακα. Για να σώσεις τις αλλαγές, πάτα το κουμπί 'Κατέβασμα' στο τέλος.")

    # Data Editor
    edited_df = st.data_editor(
        df_year.sort_values(by='DocDate', ascending=False),
        num_rows="dynamic",  # Επιτρέπει προσθήκη γραμμών
        column_config={
            "DocDate": st.column_config.DateColumn("Ημερομηνία"),
            "Payment Date": st.column_config.DateColumn("Ημ. Πληρωμής"),
            "Amount (Net)": st.column_config.NumberColumn("Καθαρό", format="€%.2f"),
            "VAT Amount": st.column_config.NumberColumn("ΦΠΑ", format="€%.2f"),
            "Amount (Gross)": st.column_config.NumberColumn("Μικτό", format="€%.2f"),
            "DocType": st.column_config.SelectboxColumn("Τύπος", options=["Income", "Expense", "Bill", "Equity Distribution"]),
            "Payment Method": st.column_config.SelectboxColumn("Τρόπος Πληρ.", options=["Cash", "Bank Transfer", "Card"]),
            "Status": st.column_config.SelectboxColumn("Κατάσταση", options=["Paid", "Unpaid"]),
        },
        use_container_width=True,
        hide_index=True
    )

    # Ενημέρωση Session State αν αλλάξει κάτι
    if not edited_df.equals(df_year):
        # Εδώ ενημερώνουμε το κεντρικό dataframe (θέλει προσοχή με τα indexes, για απλότητα αντικαθιστούμε το filtered)
        # Στην πλήρη έκδοση θα κάναμε merge. Εδώ απλά κρατάμε το edited για εξαγωγή.
        st.session_state.latest_edits = edited_df

    st.markdown("---")
    
    # EXPORT BUTTON
    col_dl, col_dummy = st.columns([1, 4])
    with col_dl:
        # Ετοιμασία Excel για κατέβασμα
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # Σώζουμε ΟΛΟ το df, όχι μόνο το έτος, αλλά με τις αλλαγές του έτους (εδώ απλοποιημένα σώζουμε αυτό που βλέπεις)
            # Σωστή πρακτική: Merge changes back to main DF. 
            # Για το MVP: Κατεβάζεις αυτό που βλέπεις.
            edited_df.to_excel(writer, sheet_name='Journal', index=False)
            
        st.download_button(
            label="💾 Κατεβάστε το Ενημερωμένο Excel",
            data=buffer,
            file_name="Updated_Finance_Data.xlsx",
            mime="application/vnd.ms-excel"
        )

# --- Σελίδα 3: ΦΠΑ ---
elif page == "🏛️ ΦΠΑ & Εφορία":
    st.title("🏛️ Υπολογισμός ΦΠΑ")
    
    col1, col2 = st.columns(2)
    
    # ΦΠΑ Εσόδων
    vat_in = df_year[df_year['DocType'] == 'Income']['VAT Amount'].sum()
    col1.subheader("ΦΠΑ Πωλήσεων (+)")
    col1.metric("Εισπραχθέν ΦΠΑ", f"€{vat_in:,.2f}")
    col1.dataframe(df_year[df_year['DocType'] == 'Income'][['DocDate', 'Description', 'Amount (Net)', 'VAT Amount']])

    # ΦΠΑ Εξόδων
    vat_out = df_year[df_year['DocType'].isin(['Expense', 'Bill'])]['VAT Amount'].sum()
    col2.subheader("ΦΠΑ Αγορών/Εξόδων (-)")
    col2.metric("Πληρωθέν ΦΠΑ", f"€{vat_out:,.2f}")
    col2.dataframe(df_year[df_year['DocType'].isin(['Expense', 'Bill'])][['DocDate', 'Description', 'Amount (Net)', 'VAT Amount']])

    st.markdown("---")
    final_vat = vat_in - vat_out
    if final_vat > 0:
        st.error(f"🔴 Τελικό Πληρωτέο ΦΠΑ: €{final_vat:,.2f}")
    else:
        st.success(f"🟢 Πιστωτικό ΦΠΑ (Επιστροφή): €{abs(final_vat):,.2f}")

# --- Σελίδα 4: Ταμείο & Τράπεζες ---
elif page == "💰 Ταμείο & Τράπεζες":
    st.title("💰 Διαχείριση Ρευστότητας")
    
    # Φιλτράρουμε μόνο τα ΠΛΗΡΩΜΕΝΑ (Paid)
    paid_df = df_year[df_year['Status'] == 'Paid']
    
    # 1. ΤΑΜΕΙΟ (CASH)
    cash_df = paid_df[paid_df['Payment Method'] == 'Cash']
    cash_in = cash_df[cash_df['DocType'] == 'Income']['Amount (Gross)'].sum()
    cash_out = cash_df[cash_df['DocType'].isin(['Expense', 'Bill', 'Equity Distribution'])]['Amount (Gross)'].sum()
    cash_balance = cash_in - cash_out
    
    # 2. ΤΡΑΠΕΖΑ (BANK)
    bank_df = paid_df[paid_df['Payment Method'].isin(['Bank Transfer', 'Card', 'Τράπεζα'])]
    bank_in = bank_df[bank_df['DocType'] == 'Income']['Amount (Gross)'].sum()
    bank_out = bank_df[bank_df['DocType'].isin(['Expense', 'Bill', 'Equity Distribution'])]['Amount (Gross)'].sum()
    bank_balance = bank_in - bank_out
    
    c1, c2 = st.columns(2)
    c1.info(f"💵 **Υπόλοιπο Ταμείου (Cash):** €{cash_balance:,.2f}")
    c2.info(f"🏦 **Υπόλοιπο Τράπεζας:** €{bank_balance:,.2f}")
    
    st.subheader("Αναλυτική Κίνηση Ταμείου")
    st.dataframe(cash_df[['DocDate', 'Description', 'DocType', 'Amount (Gross)']].sort_values('DocDate', ascending=False), use_container_width=True)

# --- Σελίδα 5: Μέτοχοι ---
elif page == "👥 Μέτοχοι & Μερίσματα":
    st.title("👥 Καρτέλα Μετόχων")
    
    # Φίλτρο για Equity Distribution
    equity_df = df_year[df_year['DocType'] == 'Equity Distribution']
    
    total_divs = equity_df['Amount (Net)'].sum()
    st.metric("Συνολικά Μερίσματα Έτους", f"€{total_divs:,.2f}")
    
    st.subheader("Πληρωμές προς Εταίρους")
    if not equity_df.empty:
        # Group by Partner (Counterparty)
        per_partner = equity_df.groupby('Counterparty')['Amount (Net)'].sum().reset_index()
        col1, col2 = st.columns([1, 2])
        col1.dataframe(per_partner, hide_index=True)
        
        fig = px.pie(per_partner, values='Amount (Net)', names='Counterparty', title="Κατανομή Μερισμάτων")
        col2.plotly_chart(fig, use_container_width=True)
        
        st.write("Αναλυτική Λίστα:")
        st.dataframe(equity_df, use_container_width=True)
    else:
        st.info("Δεν έχουν καταχωρηθεί μερίσματα για αυτό το έτος.")
