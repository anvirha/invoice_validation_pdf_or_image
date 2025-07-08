#  Document Type & Metadata Extractor (OCR + MongoDB)

This Python script analyzes scanned **PDFs** and **image files** (`.jpg`, `.png`) to extract:

-  **GSTINs**
-  **Invoice Numbers** (with pattern types)
-  **Document Type** (Tax Invoice, Credit Note, E-Invoice, etc.)
-  Even from image-based PDFs using OCR

The extracted data is stored in a **MongoDB collection**, enabling structured downstream processing and searchability.

---

##  Features

-  Auto-detects document types based on keyword patterns
-  Extracts text from:
  - Text-based PDFs (via **pdfplumber**)
  - Image-based PDFs (via **Tesseract OCR**)
  - Standalone images (`.jpg`, `.jpeg`, `.png`)
-  Identifies and classifies invoice numbers with regex
-  Extracts valid **GSTINs**
-  Cleans and normalizes extracted data
-  Stores structured data in MongoDB with processing status flags

