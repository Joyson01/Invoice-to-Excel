# Standalone Utility Scripts

This directory contains standalone CLI scripts:

- `rajputana_b2b_upload.py`: Standalone CLI tool to extract Rajputana TAX INVOICE PDFs directly into the 3-sheet B2B Excel workbook format without running the web server. Run with:
  ```bash
  python scripts/rajputana_b2b_upload.py --help
  ```

- `first_label_per_awb.py`: Standalone CLI tool to process multi-page label PDFs, retaining only the first label page per AWB and dropping identical duplicate package pages. Run with:
  ```bash
  python scripts/first_label_per_awb.py --help
  ```
