import os
import fitz  # PyMuPDF
import pytesseract
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
import pdfplumber
import re
from pymongo import MongoClient
from datetime import datetime


# MongoDB Configuration
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "document_analysis"
MONGO_COLLECTION = "extracted_data"

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]


# Set your Tesseract path here
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DOCUMENT_KEYWORDS = {
    "Tax Invoice": [
        "tax invoice", "gst invoice","tax invoice no", "sales invoice", "inv #"
    ],
    "E-Invoice": [
        "e-invoice"
    ],
    "Booking Confirmation": [
        "booking confirmation"
    ],
    "Certificate": [
        "gst certificate", "registration certificate"
    ],
    "Statement": [
        "commission statement"
    ],
    "Credit Note": [
        "credit note", "gst credit note"
    ],
    "Debit Note": [
        "debit note", "gst debit note"
    ],
    "Cover Letter": [
        "covering letter", "cover letter"
    ]
}


GST_REGEX = r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b'
INVOICE_NUMBER_PATTERNS = {
    "Invoice_number": [
        r'(?:invoice[\s\-]*number|invoice[\s\-]*no|inv[\s\-]*#|invoice[\s\-]*#)[:\-]?\s*([A-Za-z0-9\-/]+)',
        r'Invoice No\.?\s*:\s*([A-Za-z0-9\-/]+)',
        r'Invoice Number\.?\s*:\s*([A-Za-z0-9\-/]+)',
        r'INV-\d{4}-\d{4}'   # Example: INV-2023-1234
    ],
    "bill_number": [
        r'(?:bill[\s\-]*number|bill[\s\-]*no|bill[\s\-]*#)[:\-]?\s*([A-Za-z0-9\-/]+)',
        r'Bill No\.?\s*:\s*([A-Za-z0-9\-/]+)'
    ],
    "tax_invoice": [
        r'(?:tax[\s\-]*invoice[\s\-]*no)[:\-]?\s*([A-Za-z0-9\-/]+)',
        r'Tax Invoice No\.?\s*:\s*([A-Za-z0-9\-/]+)'
    ]
}


def pdf_has_text(pdf_path):
    doc = fitz.open(pdf_path)
    for page in doc:
        if page.get_text().strip():
            return True
    return False


def extract_text_pdfplumber(pdf_path):
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                texts.append(page_text)
    return "\n".join(texts)


def convert_pdf_to_images(pdf_path):
    return convert_from_path(pdf_path, dpi=300)


def extract_text_from_image(img):
    if isinstance(img, Image.Image):
        img = np.array(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray).strip()
    return text


def detect_keywords(text):
    text_lower = text.lower()
    matched_categories = set()

    for category, keywords in DOCUMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                matched_categories.add(category)
                break  # No need to check other keywords if one matches

    return list(matched_categories)



def extract_metadata(text):
    gst_numbers = re.findall(GST_REGEX, text, re.IGNORECASE)
    
    invoice_matches = {}
    seen_numbers = set()  # To track already seen invoice numbers
    
    # Check each invoice type pattern
    for inv_type, patterns in INVOICE_NUMBER_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if inv_type not in invoice_matches:
                    invoice_matches[inv_type] = []
                for num in matches:
                    if num not in seen_numbers:  # Only add if not seen before
                        invoice_matches[inv_type].append(num)
                        seen_numbers.add(num)
    
    # Flatten all invoice numbers while maintaining type information
    invoice_numbers = []
    for inv_type, numbers in invoice_matches.items():
        for num in numbers:
            invoice_numbers.append({
                "invoice_number": num,
                "type": inv_type.replace("_", " ").title()
            })
    
    return {
        "gst_numbers": list(set(gst_numbers)),
        "invoice_numbers": invoice_numbers,
        "invoice_count": len(invoice_numbers)
    }

def analyze_file(file_path):
    file_ext = file_path.lower().split('.')[-1]

    if file_ext == "pdf":
        print(f"📄 Checking PDF: {file_path}")
        if pdf_has_text(file_path):
            print("📝 PDF has embedded text. Extracting with pdfplumber...")
            text = extract_text_pdfplumber(file_path)
        else:
            print("🖼️ PDF likely image-based. Converting to images for OCR...")
            images = convert_pdf_to_images(file_path)
            text = ""
            for img in images:
                text += extract_text_from_image(img) + "\n"

    elif file_ext in ("jpg", "jpeg", "png"):
        print(f"🖼️ Checking Image: {file_path}")
        img = cv2.imread(file_path)
        if img is None:
            return {"error": f"Could not read image {file_path}"}
        text = extract_text_from_image(img)

    else:
        return {"error": "Unsupported file type"}

    doc_types = detect_keywords(text)
    metadata = extract_metadata(text)

    return {
        "text": text.strip(),
        "types": doc_types,
        "metadata": metadata
    }


if __name__ == "__main__":
    folder_path = "./pdfs"  # Change this to your folder path
    supported_extensions = (".pdf", ".jpg", ".jpeg", ".png")

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        # Skip unsupported files
        if not filename.lower().endswith(supported_extensions):
            print(f"⏩ Skipping unsupported file: {filename}")
            continue

        try:
            result = analyze_file(file_path)

            print(f"\n==============================")
            print(f"📂 File: {filename}")
            print(f"==============================")

            if "error" in result:
                print("❌ Error:", result["error"])
                continue

            print(f"\n--- Extracted Text ---\n")
            print(result["text"])

            print("\n--- Detected Document Type(s) ---")
            if result["types"]:
                for dtype in result["types"]:
                    print(f"✅ {dtype}")
            else:
                print("⚠️ No known document type detected.")

            print("\n--- Extracted Metadata ---")
            print("📌 GST Numbers:", result["metadata"].get("gst_numbers", []))
            print("\n📄 Invoice Numbers:")
            for inv in result["metadata"].get("invoice_numbers", []):
                print(f"  - {inv['invoice_number']} (Type: {inv['type']})")
            print("\n🧾 Number of Invoices:", result["metadata"].get("invoice_count", 0))

            # --- Determine Status Flags ---
            is_document_type = bool(result["types"])
            is_gst_number = bool(result["metadata"].get("gst_numbers"))
            is_invoice_number = bool(result["metadata"].get("invoice_numbers"))

            # --- MongoDB Document ---
            mongo_doc = {
                "file_name": filename,
                "file_path": file_path,
                "extracted_text": result["text"],
                "document_types": result["types"],
                "metadata": result["metadata"],
                "document_type_sucess": is_document_type,
                "gst_number_sucess": is_gst_number,
                "invoice_number_sucess": is_invoice_number,
                "invoice_count": result["metadata"].get("invoice_count", 0),
                "processed_at": datetime.utcnow()
            }

            collection.insert_one(mongo_doc)
            print(f"📥 Saved to MongoDB")
            print(f"🔍 Flags - Document Type: {is_document_type}, GST: {is_gst_number}, Invoice: {is_invoice_number}")

        except Exception as e:
            print(f"❌ Exception while processing {filename}: {str(e)}")
