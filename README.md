# Invoice PDF to Excel (B2B Bulk Upload Generator)

An on-premise, privacy-first invoice processing web application that extracts order and billing details from company invoice PDFs, validates logistics fields, provides an interactive review interface, and exports standardized 3-sheet Excel workbooks for B2B logistics bulk uploads.

All parsing and OCR computations run entirely locally on your host or container — **no cloud OCR accounts, third-party APIs, or external data transmissions are required**.

---

## Table of Contents

- [Features](#features)
- [Architecture & Tech Stack](#architecture--tech-stack)
- [Project Structure](#project-structure)
- [Excel Workbook Format](#excel-workbook-format)
- [Prerequisites](#prerequisites)
- [Quick Start: Local Development](#quick-start-local-development)
  - [1. Backend Setup](#1-backend-setup)
  - [2. Frontend Setup](#2-frontend-setup)
- [Configuration & Environment Variables](#configuration--environment-variables)
- [Production Deployment via Docker](#production-deployment-via-docker)
- [Testing & Quality Verification](#testing--quality-verification)
- [Standalone CLI Utilities](#standalone-cli-utilities)
- [API Reference](#api-reference)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [License](#license)

---

## Features

- **Hybrid PDF Extraction:** Native vector text extraction via `pdfplumber` with automatic fallback to local `RapidOCR` (ONNX Runtime) for scanned image invoices.
- **Accurate Logistics Parsing:**
  - Extracts Order IDs (preferring customer PO numbers with automatic fallback to invoice numbers).
  - Indian mobile phone normalization (extracts valid 10-digit mobile numbers; rejects landlines).
  - Indian 6-digit PIN code extraction bounded strictly to receiver address sections.
  - Line-item description rollup (summarizing SKUs and item quantities).
- **Interactive Web Review Dashboard:**
  - Drag-and-drop batch upload supporting up to 25 invoices (100 MiB total batch size).
  - Color-coded batch statuses: `Ready`, `Review Required`, or `Failed`.
  - Inline modal editor to inspect line items, update fields, and manage custom box dimensions and weights.
  - History drawer retaining the 50 most recently updated batches.
- **Strict B2B Template Mirroring:**
  - Injects data directly into `templates/B2B_bulk_upload_template.xlsx`, preserving exact font styling, alignments, fills, borders, and column dimensions.
  - Literal string enforcement to prevent Excel formula injection (`=`, `@`, `+`, `-`).
- **Configurable Business Defaults:**
  - Optional business defaults for warehouse names, payment modes, insurance, box dimensions, and fallback weights.
  - Defaults are disabled by default for strict invoice extraction, but can be enabled and saved to disk.
- **Zero Cloud Footprint:** No external API keys or cloud services required.

---

## Architecture & Tech Stack

```
   ┌─────────────────────────────────────────────────────────┐
   │                   Web Browser / Client                  │
   └────────────────────────────┬────────────────────────────┘
                                │
               HTTP Requests    │  (Port 3000 / 5173)
                                ▼
   ┌─────────────────────────────────────────────────────────┐
   │              Frontend (React 18 + Vite)                 │
   │  TypeScript · Tailwind CSS · Lucide Icons · Nginx       │
   └────────────────────────────┬────────────────────────────┘
                                │
             API Calls (/api)   │  (Port 8000)
                                ▼
   ┌─────────────────────────────────────────────────────────┐
   │              Backend (FastAPI / Python 3.12)            │
   │  Uvicorn · Pydantic v2 · pdfplumber · RapidOCR · openpyxl│
   └───────────────┬─────────────────────────┬───────────────┘
                   │                         │
                   ▼                         ▼
   ┌───────────────────────────────┐ ┌───────────────────────┐
   │       Templates & Storage     │ │  Transactional State  │
   │  templates/B2B_template.xlsx  │ │  backend/data/        │
   │  backend/uploads/ (temp)      │ │  backend/output/      │
   └───────────────────────────────┘ └───────────────────────┘
```

- **Backend:** Python 3.11+ / 3.12, FastAPI, Pydantic v2, Uvicorn, pdfplumber, RapidOCR (ONNX Runtime), openpyxl.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Lucide React.
- **Containers:** Docker, Docker Compose, Nginx Alpine.

---

## Project Structure

```
.
├── backend/                        # Backend FastAPI service
│   ├── app/
│   │   ├── config.py               # Runtime application settings & persistence
│   │   ├── document_layout.py      # Spatial line & word bounding box clustering
│   │   ├── excel_generator.py      # openpyxl 3-sheet generator with template mirroring
│   │   ├── extraction/             # Modular extractors (phone, pin, field parser)
│   │   ├── field_reader.py         # Label and bounding box matching heuristics
│   │   ├── main.py                 # FastAPI application, routes, and security limits
│   │   ├── models.py               # Pydantic data schemas (InvoiceData, BoxItem, etc.)
│   │   ├── ocr_provider.py         # RapidOCR provider abstraction
│   │   ├── parser.py               # Main multi-page invoice parser
│   │   ├── storage.py              # Transactional JSON batch store
│   │   └── validator.py            # Business validation rules & warnings
│   ├── tests/                      # Backend unit test suite
│   ├── Dockerfile                  # Non-root Python 3.12 container image
│   └── requirements.txt            # Python dependencies
├── docs/                           # Technical documentation & architecture plans
│   └── samples/                    # Reference sample spreadsheets & schemas
├── frontend/                       # Frontend React + TypeScript application
│   ├── src/
│   │   ├── components/             # Reusable UI modals (InvoiceEditModal, SettingsModal)
│   │   ├── lib/                    # API client and response handling
│   │   ├── types/                  # Shared TypeScript interfaces
│   │   ├── App.tsx                 # Main application dashboard
│   │   └── main.tsx                # SPA entry point
│   ├── Dockerfile                  # Multi-stage build with Nginx Alpine proxy
│   ├── nginx.conf                  # Production reverse proxy configuration
│   └── package.json                # Frontend dependencies and build scripts
├── scripts/                        # Standalone automation & CLI tools
│   ├── first_label_per_awb.py      # AWB shipping label deduplication tool
│   └── rajputana_b2b_upload.py     # Standalone CLI batch extractor
├── templates/                      # Canonical Excel templates
│   └── B2B_bulk_upload_template.xlsx
├── tests/                          # Root integration, accuracy, and workflow tests
├── docker-compose.yml              # Production container orchestration
├── .editorconfig                   # Universal code formatting standards
├── .env.example                    # Sample environment configuration
├── CONTRIBUTING.md                 # Contribution & development guide
└── CHANGELOG.md                    # Project version history
```

---

## Excel Workbook Format

The output workbook strictly mirrors `templates/B2B_bulk_upload_template.xlsx` across three mandatory worksheets:

1. **Orders Sheet:**  
   `Order_ID`, `Warehouse_Name`, `Receiver_Name`, `Receiver_Address`, `Receiver_Pincode`, `Receiver_Email`, `Receiver_Mobile`, `Order_description`, `Payment_Mode`, `COD_Value`, `Insurance`, `Invoice`, `Delivery_Challan`, `Declaration`, `Other_Supporting_Documents`, `Reason`.
2. **Boxes Sheet:**  
   `Order_ID`, `Length`, `Width`, `Height`, `Weight`, `Quantity`.
3. **Invoice Sheet:**  
   `Order_ID`, `Invoice_Number`, `Invoice_Amount`, `Invoice_Eway_Bill_Number`.

### Data Integrity Rules:
- **Order ID Priority:** PO Number is preferred. If absent, it falls back to Invoice Number.
- **Numeric Preservation:** Invoice Amount and Box dimensions/weights remain strictly numeric.
- **Identifier Protection:** Leading zeros in Order IDs, Invoice Numbers, and PIN codes are preserved as literal text.
- **Formula Injection Defense:** Extracted text starting with `=`, `+`, `-`, or `@` is sanitized to prevent spreadsheet formula execution.
- **Reason Column:** Incomplete fields or OCR warnings are explicitly appended to the `Reason` column for operational auditability before warehouse upload.

---

## Prerequisites

- **Python:** Version 3.11 or 3.12
- **Node.js:** Version 18.x or 20.x with `npm`
- **System Libraries (Linux):** `libgl1` and `libglib2.0-0` (required by OpenCV/ONNX for RapidOCR)
- **Docker & Docker Compose** (optional, recommended for production)

---

## Quick Start: Local Development

### 1. Backend Setup

From the repository root:

```bash
cd backend

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Start the FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive OpenAPI documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 2. Frontend Setup

In a separate terminal, from the repository root:

```bash
cd frontend

# Install dependencies
npm ci

# Launch development server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser. The Vite development proxy forwards all `/api` requests to the local backend on port 8000.

---

## Configuration & Environment Variables

Copy `.env.example` to `.env` in the root directory:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|---|---|---|
| `APP_BIND_ADDRESS` | `127.0.0.1` | Local IP address to bind container port (loopback for security) |
| `APP_PORT` | `3000` | Frontend web port exposed on host |
| `TEMPLATE_PATH` | `../templates/B2B_bulk_upload_template.xlsx` | Canonical B2B Excel template path |
| `UPLOAD_DIR` | `./uploads` | Temporary storage for active batch uploads |
| `OUTPUT_DIR` | `./output` | Storage for generated Excel exports |
| `STATE_DIR` | `./data` | Persistent batch store and business defaults JSON |
| `MAX_FILE_SIZE_MB`| `50` | Maximum file size allowed per uploaded PDF |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed web origins for backend API |

---

## Production Deployment via Docker

Docker Compose deploys the complete stack with an internal backend network, non-root application user, persistent data volumes, and Nginx reverse proxy:

```bash
# Build and start services in detached mode
docker compose up -d --build

# View application logs
docker compose logs -f

# Check health status
docker compose ps
```

Access the application at [http://localhost:3000](http://localhost:3000).

### Security Notes for Production:
1. **Loopback Binding:** By default, Docker binds `APP_BIND_ADDRESS` to `127.0.0.1`. To serve a private office network, set `APP_BIND_ADDRESS=0.0.0.0` or route traffic through an HTTPS reverse proxy (such as Caddy, Nginx, or Traefik) with TLS certificates.
2. **Persistence Volume:** Application state and exports are stored in the `backend-data` Docker volume. Back up this volume before container upgrades.
3. **Single Backend Worker:** The backend operates with `--workers 1` because session state is synchronized via transactional filesystem locking on the `STATE_DIR`.

---

## Testing & Quality Verification

The repository contains 53 automated tests covering native extraction, real OCR processing, persistence, duplicate correction, formula sanitization, and workflow APIs.

### Run Backend & Pipeline Tests
```bash
# From repository root
backend/.venv/bin/python -m pytest -v
```

### Run Frontend Typecheck & Build
```bash
cd frontend
npm run lint    # Executes tsc --noEmit
npm run build   # Compiles production bundle
```

---

## Standalone CLI Utilities

For headless or batch command-line workflows, dedicated scripts are provided in `scripts/`:

- **Batch Invoice Extractor:**
  ```bash
  python scripts/rajputana_b2b_upload.py --input /path/to/invoices --output ./output
  ```
- **AWB Label Deduplicator:**
  ```bash
  python scripts/first_label_per_awb.py --input /path/to/labels --output ./output
  ```

---

## API Reference

Interactive Swagger documentation is available at `/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Healthcheck verifying backend status and template availability |
| `GET` | `/api/config` | Fetch active business defaults |
| `PATCH`| `/api/config` | Update business defaults (warehouse, insurance, dimensions) |
| `POST` | `/api/upload` | Upload PDF batch (up to 25 files, max 100 MiB) |
| `GET` | `/api/batches` | List 50 most recent batches |
| `GET` | `/api/invoices/{session_id}` | Retrieve invoices and validation statuses for a batch |
| `PUT` | `/api/invoices/{session_id}/{invoice_id}` | Edit invoice details and trigger immediate revalidation |
| `POST` | `/api/generate/{session_id}` | Generate B2B Excel workbook for the batch |
| `GET` | `/api/download/{session_id}/{filename}` | Download generated Excel workbook |

---

## Troubleshooting & FAQ

### 1. `libGL.so.1: cannot open shared object file`
- **Cause:** RapidOCR's underlying OpenCV/ONNX libraries require OpenGL system packages on Linux.
- **Fix:** Run `sudo apt-get install -y libgl1 libglib2.0-0` (or ensure you use the supplied Docker image which installs these packages).

### 2. Scanned Invoice Upload Takes Several Seconds
- **Cause:** Scanned PDFs without embedded text undergo full-page OCR locally on CPU using RapidOCR.
- **Fix:** Processing time depends on page resolution and CPU speed (typically 2-4 seconds per page). Allow proxy timeouts of at least 60s in production Nginx.

### 3. Missing Fields in Excel Export
- **Cause:** If an invoice omits a PO number or email, the field is left blank and a warning is noted in the `Reason` column to prevent fabricated data.
- **Fix:** Enable **"Use business defaults for missing fields"** in the UI **Defaults** panel, or use the **Edit** button to provide values manually before generating the workbook.

---

## License

This project is licensed according to the repository owner's specifications. Please refer to the confirmed project license before commercial redistribution.
