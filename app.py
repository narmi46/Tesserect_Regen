import streamlit as st
import pdfplumber
import pandas as pd

from maybank import parse_transactions_mbb, parse_transactions_mtasb
from public_bank import parse_transactions_pbb


# ---------------------------------------------------
# Streamlit UI
# ---------------------------------------------------

st.set_page_config(page_title="Bank Statement Parser", layout="wide")

st.title("📄 Bank Statement Parser")
st.write("Upload a bank statement PDF and extract transactions using modular regex patterns.")


# ---------------------
# Bank Selection
# ---------------------

bank_choice = st.selectbox(
    "Select Bank Format",
    ["Auto-detect", "Maybank (MBB)", "MTASB", "Public Bank (PBB)"]
)

# Convert UI choice to parser hint
bank_hint = None
if bank_choice == "Maybank (MBB)":
    bank_hint = "mbb"
elif bank_choice == "MTASB":
    bank_hint = "mtasb"
elif bank_choice == "Public Bank (PBB)":
    bank_hint = "pbb"


uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

default_year = st.text_input("Default Year", "2025")


def auto_detect_and_parse(text, page_num, default_year):
    """Try all available bank parsers and return first match."""
    # Try MTASB
    t1 = parse_transactions_mtasb(text, page_num, default_year)
    if t1:
        return t1

    # Try Maybank
    t2 = parse_transactions_mbb(text, page_num)
    if t2:
        return t2

    # Try Public Bank
    t3 = parse_transactions_pbb(text, page_num, default_year)
    if t3:
        return t3

    return []


if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:

        all_transactions = []

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""

            # User selects a specific bank
            if bank_hint == "mbb":
                tx = parse_transactions_mbb(text, page_num)
            elif bank_hint == "mtasb":
                tx = parse_transactions_mtasb(text, page_num, default_year)
            elif bank_hint == "pbb":
                tx = parse_transactions_pbb(text, page_num, default_year)
            else:
                tx = auto_detect_and_parse(text, page_num, default_year)

            all_transactions.extend(tx)

        # Display results
        df = pd.DataFrame(all_transactions)

        st.subheader("Extracted Transactions")
        st.dataframe(df, use_container_width=True)

        # Download CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name="transactions.csv",
            mime="text/csv"
        )
