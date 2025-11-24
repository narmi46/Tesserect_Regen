import streamlit as st
import pdfplumber
import json
import pandas as pd

from maybank import parse_transactions_maybank
from public_bank import parse_transactions_pbb
from rhb import parse_transactions_rhb



st.set_page_config(page_title="Bank Statement Parser", layout="wide")

st.title("📄 Bank Statement Parser")
st.write("Upload a bank statement PDF to extract transactions in a clean readable table.")


# --------------------------
# Bank Choice
# --------------------------

bank_choice = st.selectbox(
    "Select Bank Format",
    ["Auto-detect", "Maybank", "Public Bank (PBB)", "RHB Bank"]
)

bank_hint = None
if bank_choice == "Maybank":
    bank_hint = "maybank"
elif bank_choice == "Public Bank (PBB)":
    bank_hint = "pbb"
elif bank_choice == "RHB Bank":
    bank_hint = "rhb"



uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
default_year = st.text_input("Default Year", "2025")


# --------------------------
# Auto-detect logic
# --------------------------

def auto_detect_and_parse(text, page_num, default_year):
    t1 = parse_transactions_maybank(text, page_num, default_year)
    if t1:
        return t1

    t2 = parse_transactions_pbb(text, page_num, default_year)
    if t2:
        return t2
        
    t3 = parse_transactions_rhb(text, page_num)
    if t3:
        return t3


    return []


# --------------------------
# Main PDF Processing
# --------------------------

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
            elif bank_hint == "rhb":
                tx = parse_transactions_rhb(text, page_num)


            all_tx.extend(tx)

        # --------------------------
        # Display Table (Human Readable)
        # --------------------------
        st.subheader("Extracted Transactions (Readable Table)")

        if all_tx:
            df = pd.DataFrame(all_tx)

            # Reorder columns nicely
            df = df[["date", "description", "debit", "credit", "balance", "page"]]

            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No transactions matched the selected bank format.")

        # --------------------------
        # JSON DOWNLOAD
        # --------------------------
        json_data = json.dumps(all_tx, indent=4)
        st.download_button(
            "Download JSON",
            json_data,
            file_name="transactions.json",
            mime="application/json"
        )

               # --------------------------
        # TXT DOWNLOAD (Beautiful Table)
        # --------------------------

        if all_tx:
            df = pd.DataFrame(all_tx)
            df = df[["date", "description", "debit", "credit", "balance"]]

            # column widths
            w_date = 12
            w_desc = 45
            w_debit = 12
            w_credit = 12
            w_balance = 14

            # header
            header = (
                f"{'DATE':<{w_date}} | "
                f"{'DESCRIPTION':<{w_desc}} | "
                f"{'DEBIT':>{w_debit}} | "
                f"{'CREDIT':>{w_credit}} | "
                f"{'BALANCE':>{w_balance}}"
            )

            separator = "-" * len(header)

            # rows
            lines = [header, separator]

            for _, row in df.iterrows():
                line = (
                    f"{str(row['date']):<{w_date}} | "
                    f"{str(row['description'])[:w_desc]:<{w_desc}} | "
                    f"{row['debit']:>{w_debit}.2f} | "
                    f"{row['credit']:>{w_credit}.2f} | "
                    f"{row['balance']:>{w_balance}.2f}"
                )
                lines.append(line)

            txt_data = "\n".join(lines)

            st.download_button(
                "Download TXT",
                txt_data,
                file_name="transactions.txt",
                mime="text/plain"
            )
