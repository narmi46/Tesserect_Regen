import streamlit as st
import pdfplumber
import json

from maybank import parse_transactions_maybank
from public_bank import parse_transactions_pbb


st.set_page_config(page_title="Bank Statement Parser", layout="wide")

st.title("📄 Bank Statement Parser")
st.write("Upload a bank statement PDF and extract transactions.")


bank_choice = st.selectbox(
    "Select Bank Format",
    ["Auto-detect", "Maybank", "Public Bank (PBB)"]
)

bank_hint = None
if bank_choice == "Maybank":
    bank_hint = "maybank"
elif bank_choice == "Public Bank (PBB)":
    bank_hint = "pbb"


uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
default_year = st.text_input("Default Year", "2025")


def auto_detect_and_parse(text, page_num, default_year):
    t1 = parse_transactions_maybank(text, page_num, default_year)
    if t1:
        return t1

    t2 = parse_transactions_pbb(text, page_num, default_year)
    if t2:
        return t2

    return []


if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:

        all_tx = []

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""

            if bank_hint == "maybank":
                tx = parse_transactions_maybank(text, page_num, default_year)
            elif bank_hint == "pbb":
                tx = parse_transactions_pbb(text, page_num, default_year)
            else:
                tx = auto_detect_and_parse(text, page_num, default_year)

            all_tx.extend(tx)

        st.subheader("Extracted Transactions")
        st.json(all_tx)

        json_data = json.dumps(all_tx, indent=4)
        st.download_button(
            "Download JSON",
            json_data,
            file_name="transactions.json",
            mime="application/json"
        )

        txt_data = "\n".join(
            f"{t['date']} | {t['description']} | DR:{t['debit']} | CR:{t['credit']} | BAL:{t['balance']}"
            for t in all_tx
        )

        st.download_button(
            "Download TXT",
            txt_data,
            file_name="transactions.txt",
            mime="text/plain"
        )
