# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-11

### Added
- **Core Processing Engine:**
  - Native PDF parsing using `pdfplumber` with positional bounding box preservation.
  - Local OCR fallback using `RapidOCR` (ONNX Runtime) for scanned image invoices without third-party cloud APIs.
  - Address parsing, Indian phone number normalizer (10-digit mobile detection), and 6-digit PIN code extraction.
  - Multi-page invoice aggregation and PO number fallback extraction.
- **B2B Excel Workbook Generator:**
  - Exact 3-sheet workbook generator (`Orders`, `Boxes`, `Invoice`) matching logistics bulk upload templates.
  - Custom cell style mirroring preserving template fonts, alignments, borders, and fills.
  - Strict string literal protection against formula injection (`=`, `@`, `+`, `-`).
- **Single-Worker Local API (`backend/app`):**
  - FastAPI backend with transactional filesystem storage (`BatchStore`).
  - Batch endpoints for upload, validation, review, and on-demand workbook regeneration.
  - Configurable business defaults with runtime validation and batch-level re-validation.
  - Security controls: MIME and magic byte validation (`%PDF-`), batch size limits (100 MiB), per-file limits (50 MB), and safe path traversal defenses.
- **Web User Interface (`frontend`):**
  - React 18, TypeScript, and Tailwind CSS SPA with responsive design and Lucide icons.
  - Drag-and-drop batch upload supporting up to 25 PDFs per batch.
  - Batch review table highlighting status (`Ready`, `Review Required`, `Failed`) with specific warning reasons.
  - Inline invoice editor with multi-box dimension/weight management.
  - Business defaults configuration modal.
  - Historical batch selector (reloading the 50 most recent batches).
- **Docker & Deployment Infrastructure:**
  - Multi-stage Dockerfile for the frontend with Nginx Alpine reverse proxy.
  - Python 3.12-slim Dockerfile with non-root security user (`invoice`) for backend.
  - `docker-compose.yml` orchestrating frontend and backend with automatic health checks and persistent volume storage.
- **Repository Health & CI/CD:**
  - GitHub Actions CI workflow covering Python tests and TypeScript production build.
  - Comprehensive `.gitignore`, `.env.example`, `.editorconfig`, issue templates, and PR template.
