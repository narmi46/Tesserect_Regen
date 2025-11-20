# app.py

import streamlit as st
import pdfplumber
import pytesseract
from PIL import Image
import json
import os
import tempfile
from tabulate import tabulate

from transaction_patterns import parse_transactions  # <-- central import

st.title("📄 Bank Statement Parser (Modular Regex Version)")
st.write("Upload your bank statement PDF and extract transactions. Regex patterns are modular for future banks.")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload your bank statement PDF", type=["pdf"])

if uploaded_file:

    # Save uploaded PDF to a temp file
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_pdf.write(uploaded_file.read())
    temp_pdf.close()

    st.success("✅ PDF uploaded successfully.")

    # Directory for OCR images
    TEMP_DIR = "temp_ocr_images"
    os.makedirs(TEMP_DIR, exist_ok=True)

    # --- Text extraction (with OCR fallback) ---
    def extract_text(page, page_num):
        # Try native text extraction
        text = page.extract_text()

        # Fallback to OCR if needed
        if not text or text.strip() == "":
            img_path = os.path.join(TEMP_DIR, f"page_{page_num}.png")
            page.to_image(resolution=300).save(img_path)
            text = pytesseract.image_to_string(Image.open(img_path))

        return text

    # --------------------------
    # Process entire PDF
    # --------------------------
    all_transactions = []

    with pdfplumber.open(temp_pdf.name) as pdf:
        total_pages = len(pdf.pages)
        st.info(f"📄 Total pages detected: {total_pages}")

        # You can let user pick default year (optional)
        default_year = st.text_input("Default year for MTASB-style statements (e.g. 2025):", value="2025")

        for page_num, page in enumerate(pdf.pages, start=1):
            st.write(f"Processing page {page_num}/{total_pages}...")
            text = extract_text(page, page_num)

            page_transactions = parse_transactions(text, page_num, default_year=default_year)
            all_transactions.extend(page_transactions)

    st.success(f"✅ Extraction complete! Found {len(all_transactions)} transactions.")

    # --------------------------
    # Display in Streamlit
    # --------------------------
    if all_transactions:
        st.subheader("📊 Extracted Transactions")
        st.dataframe(all_transactions)
    else:
        st.warning("No transactions detected. You may need to adjust regex patterns in transaction_patterns.py.")

    # --------------------------
    # Download JSON
    # --------------------------
    json_output = json.dumps(all_transactions, indent=4)

    st.download_button(
        "⬇️ Download JSON file",
        json_output,
        "transactions.json",
        "application/json"
    )

    # --------------------------
    # Download TXT table
    # --------------------------
    if all_transactions:
        rows = []
        for t in all_transactions:
            rows.append([
                t["date"],
                t["description"],
                f"{t['debit']:.2f}",
                f"{t['credit']:.2f}",
                f"{t['balance']:.2f}",
                t["page"]
            ])

        headers = ["Date", "Description", "Debit", "Credit", "Balance", "Page"]
        table_text = tabulate(rows, headers=headers, tablefmt="grid")

        st.download_button(
            "⬇️ Download Table (.txt)",
            table_text,
            "transactions_table.txt",
            "text/plain"
        )
