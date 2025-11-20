import streamlit as st
import pdfplumber
import pytesseract
from PIL import Image
import regex as re
import json
import os
from tabulate import tabulate
import tempfile

st.title("📄 Bank Statement Parser (PDF → JSON + Table)")

st.write("Upload your bank statement PDF and extract clean transaction data.")

# --- Upload PDF ---
uploaded_file = st.file_uploader("Upload Bank Statement PDF", type=["pdf"])

if uploaded_file:

    # Save uploaded file temporarily
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_pdf.write(uploaded_file.read())
    temp_pdf.close()

    st.success("PDF uploaded successfully!")

    # OCR temporary image folder
    TEMP_DIR = "temp_ocr_images"
    os.makedirs(TEMP_DIR, exist_ok=True)

    # --- OCR + TEXT EXTRACTION FUNCTION ---
    def extract_text(page, page_num):
        text = page.extract_text()

        if not text or text.strip() == "":
            img_path = f"{TEMP_DIR}/page_{page_num}.png"
            page.to_image(resolution=300).save(img_path)
            text = pytesseract.image_to_string(Image.open(img_path))

        return text

    # --- REGEX PATTERN FOR BANK FORMAT ---
    transaction_pattern = re.compile(
        r"(\d{2}[/]\d{2})\s+"
        r"(.+?)\s+"
        r"([0-9,]+\.\d{2})([+-])\s+"
        r"([0-9,]+\.\d{2})"
    )

    # --- PARSE TRANSACTIONS ---
    def parse_transactions(text, page_num):
        transactions = []

        for line in text.split("\n"):
            match = transaction_pattern.search(line)
            if not match:
                continue

            date_raw, desc, amount_raw, sign, balance_raw = match.groups()

            amount = float(amount_raw.replace(",", ""))
            balance = float(balance_raw.replace(",", ""))

            credit = amount if sign == "+" else 0.0
            debit = amount if sign == "-" else 0.0

            day, month = date_raw.split("/")
            full_date = f"2025-{month}-{day}"

            transactions.append({
                "date": full_date,
                "description": desc.strip(),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

        return transactions

    # --- PROCESS PDF ---
    all_transactions = []

    with pdfplumber.open(temp_pdf.name) as pdf:
        total_pages = len(pdf.pages)
        st.info(f"Total pages detected: {total_pages}")

        for page_num, page in enumerate(pdf.pages, start=1):
            st.write(f"Processing page {page_num}/{total_pages}...")
            text = extract_text(page, page_num)
            extracted_tx = parse_transactions(text, page_num)
            all_transactions.extend(extracted_tx)

    st.success(f"Extraction complete! {len(all_transactions)} transactions found.")

    # --- DISPLAY DATA ---
    st.subheader("📊 Extracted Transactions (Table View)")
    st.dataframe(all_transactions)

    # --- JSON DOWNLOAD ---
    json_output = json.dumps(all_transactions, indent=4)
    st.download_button(
        "⬇️ Download JSON",
        json_output,
        "transactions.json",
        "application/json"
    )

    # --- TEXT TABLE DOWNLOAD ---
    rows = []
    for t in all_transactions:
        rows.append([
            t["date"], t["description"],
            f"{t['debit']:.2f}",
            f"{t['credit']:.2f}",
            f"{t['balance']:.2f}",
            t["page"]
        ])

    headers = ["Date", "Description", "Debit", "Credit", "Balance", "Page"]
    table_text = tabulate(rows, headers=headers, tablefmt="grid")

    st.download_button(
        "⬇️ Download Text Table",
        table_text,
        "transactions_table.txt",
        "text/plain"
    )

    st.success("All files generated successfully!")
