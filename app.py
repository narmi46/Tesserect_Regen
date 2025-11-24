import streamlit as st
import pdfplumber
import json

from maybank import parse_transactions_mbb
from public_bank import parse_transactions_pbb


# ---------------------------------------------------
# Streamlit UI
# ---------------------------------------------------

st.set_page_config(page_title="Bank Statement Parser", layout="wide")

st.title("📄 Bank Statement Parser")
st.write("Upload a bank statement PDF and extract transactions using regex patterns.")


# ---------------------
# Bank Selection
# ---------------------

bank_choice = st.selectbox(
    "Select Bank Format",
    ["Auto-detect", "Maybank (MBB)", "Public Bank (PBB)"]
)

bank_hint = None
if bank_choice == "Maybank (MBB)":
    bank_hint = "mbb"
elif bank_choice == "Public Bank (PBB)":
    bank_hint = "pbb"


uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
default_year = st.text_input("Default Year", "2025")


# ---------------------------------------------------
# Auto-detect Parser (only Maybank + PBB)
# ---------------------------------------------------

def auto_detect_and_parse(text, page_num, default_year):
    # Try Maybank first
    t1 = parse_transactions_mbb(text, page_num)
    if t1:
        return t1

    # Try Public Bank second
    t2 = parse_transactions_pbb(text, page_num, default_year)
    if t2:
        return t2

    return []


# ---------------------------------------------------
# Main PDF Processing
# ---------------------------------------------------

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:

        all_transactions = []

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""

            if bank_hint == "mbb":
                tx = parse_transactions_mbb(text, page_num)

            elif bank_hint == "pbb":
                tx = parse_transactions_pbb(text, page_num, default_year)

            else:
                tx = auto_detect_and_parse(text, page_num, default_year)

            all_transactions.extend(tx)

        # ---------------------------------------------------
        # Show Data
        # ---------------------------------------------------
        st.subheader("Extracted Transactions")
        st.json(all_transactions)

        # ---------------------------------------------------
        # JSON Download
        # ---------------------------------------------------
        json_data = json.dumps(all_transactions, indent=4)

        st.download_button(
            "Download JSON",
            data=json_data,
            file_name="transactions.json",
            mime="application/json"
        )

        # ---------------------------------------------------
        # TXT Download
        # ---------------------------------------------------
        txt_lines = []
        for t in all_transactions:
            line = (
                f"{t['date']} | {t['description']} | "
                f"DR: {t['debit']} | CR: {t['credit']} | BAL: {t['balance']}"
            )
            txt_lines.append(line)

        txt_data = "\n".join(txt_lines)

        st.download_button(
            "Download TXT",
            data=txt_data,
            file_name="transactions.txt",
            mime="text/plain"
        )
