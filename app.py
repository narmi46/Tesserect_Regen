import streamlit as st
import pdfplumber
import pandas as pd

from banks import parse_page_by_bank, detect_bank_by_text
from exporter import dataframe_to_ascii, dataframe_to_json


# -------------------------------
# Streamlit Setup
# -------------------------------
st.set_page_config(page_title="Bank Parser", layout="wide")
st.title("📄 Bank Statement Parser")

if "status" not in st.session_state:
    st.session_state.status = "idle"
if "results" not in st.session_state:
    st.session_state.results = []


# -------------------------------
# UI: Bank Selection
# -------------------------------
bank_choice = st.selectbox("Select Bank", [
    "Auto-detect", "Maybank", "Public Bank (PBB)", "RHB Bank", "CIMB Bank"
])

bank_map = {
    "Maybank": "maybank",
    "Public Bank (PBB)": "pbb",
    "RHB Bank": "rhb",
    "CIMB Bank": "cimb"
}
bank_hint = bank_map.get(bank_choice)


# -------------------------------
# File Upload
# -------------------------------
uploaded_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
default_year = st.text_input("Default Year", "2025")


# -------------------------------
# Auto-detect Preview
# -------------------------------
if uploaded_files and bank_hint is None:
    st.subheader("🔍 Auto-detected banks:")

    for f in uploaded_files:
        with pdfplumber.open(f) as pdf:
            first_text = pdf.pages[0].extract_text() or ""
            result = detect_bank_by_text(first_text)

            readable = {
                "maybank": "Maybank",
                "pbb": "Public Bank (PBB)",
                "rhb": "RHB Bank",
                "cimb": "CIMB Bank",
                "unknown": "Unknown Format"
            }[result]

            st.info(f"{f.name} → {readable}")


# -------------------------------
# Controls
# -------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("▶ Start"):
        st.session_state.status = "running"

with col2:
    if st.button("⏹ Stop"):
        st.session_state.status = "stopped"

with col3:
    if st.button("🔄 Reset"):
        st.session_state.results = []
        st.session_state.status = "idle"
        st.rerun()


# -------------------------------
# Processing Files
# -------------------------------
if uploaded_files and st.session_state.status == "running":

    result_list = []
    status_box = st.empty()

    for f in uploaded_files:
        st.write(f"### Processing {f.name}")

        with pdfplumber.open(f) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):

                if st.session_state.status == "stopped":
                    st.warning("Stopped by user.")
                    break

                text = page.extract_text() or ""

                tx, bank_used = parse_page_by_bank(
                    text=text,
                    page_obj=page,
                    page_num=page_num,
                    bank_hint=bank_hint,
                    default_year=default_year,
                    source_file=f.name
                )

                status_box.success(f"🏦 Processing {bank_used} (Page {page_num})")

                for t in tx:
                    t["source_file"] = f.name
                    t["bank"] = bank_used

                result_list.extend(tx)

    st.session_state.results = result_list


# -------------------------------
# Display Results
# -------------------------------
if st.session_state.results:
    df = pd.DataFrame(st.session_state.results)
    st.dataframe(df)

    # JSON download
    json_data = dataframe_to_json(df)
    st.download_button("Download JSON", json_data, "transactions.json")

    # TXT download
    ascii_data = dataframe_to_ascii(df)
    st.download_button("Download TXT", ascii_data, "transactions.txt")

