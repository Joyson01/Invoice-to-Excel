import os
import shutil
import uuid
import json
from typing import List
from pathlib import Path
from threading import Lock
from collections import Counter
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.models import InvoiceData, InvoiceUpdate
from app.parser import parse_pdf
from app.validator import validate_batch
from app.storage import BatchStore
from app.excel_generator import generate_excel
from app.config import get_config, update_config

app = FastAPI(title="B2B Invoice Extractor API", version="1.0.0")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(BASE_DIR, "output"))
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
TEMPLATE_PATH = os.getenv("TEMPLATE_PATH", os.path.join(os.path.dirname(BASE_DIR), "templates", "B2B_bulk_upload_template.xlsx"))
if not os.getenv("TEMPLATE_PATH") and not os.path.exists(TEMPLATE_PATH):
    TEMPLATE_PATH = os.path.join(os.path.dirname(BASE_DIR), "B2B_bulk_upload_template.xlsx")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

SESSIONS = BatchStore(Path(os.getenv("STATE_DIR", os.path.join(BASE_DIR, "data"))) / "batches")
batch_write_lock = Lock()

@app.get("/api/config")
def read_config():
    return get_config()

@app.patch("/api/config")
def patch_config(updates: dict):
    try:
        return update_config(updates)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc

@app.get("/api/health")
def health():
    if not os.path.isfile(TEMPLATE_PATH):
        raise HTTPException(status_code=503, detail="The Excel template is unavailable.")
    return {"status": "ok", "template_found": True}

@app.post("/api/upload")
def upload_pdfs(files: List[UploadFile] = File(...)):
    """Upload one or more PDF invoices, extract data (with OCR fallback for scanned PDFs), and return validated invoices."""
    if len(files) > 25:
        raise HTTPException(status_code=400, detail="Upload at most 25 invoices per batch.")
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
        
    session_id = str(uuid.uuid4())
    session_upload_dir = os.path.join(UPLOAD_DIR, session_id)
    os.makedirs(session_upload_dir, exist_ok=True)
    
    extracted_invoices: List[InvoiceData] = []
    
    stored_files = []
    batch_size = 0
    try:
        for file in files:
            filename = os.path.basename((file.filename or "").replace("\\", "/"))
            if not filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Please upload PDF files only.")
            file_path = os.path.join(session_upload_dir, f"{uuid.uuid4()}.pdf")
            size = 0
            header = b""
            with open(file_path, "wb") as buffer:
                while chunk := file.file.read(1024 * 1024):
                    if not header:
                        header = chunk[:1024]
                    size += len(chunk)
                    batch_size += len(chunk)
                    if batch_size > 100 * 1024 * 1024:
                        raise HTTPException(status_code=413, detail="The batch exceeds 100 MiB.")
                    if size > MAX_FILE_SIZE_BYTES:
                        raise HTTPException(status_code=413, detail=f"{filename} exceeds the file size limit.")
                    buffer.write(chunk)
            if b"%PDF-" not in header:
                raise HTTPException(status_code=400, detail=f"{filename} is not a PDF file.")
            stored_files.append((file_path, filename))
    except Exception:
        shutil.rmtree(session_upload_dir, ignore_errors=True)
        raise
    finally:
        for file in files:
            file.file.close()

    for file_path, filename in stored_files:
        try:
            invoices = parse_pdf(file_path)
            for invoice in invoices:
                invoice.filename = filename
            extracted_invoices.extend(invoices)
        except Exception as exc:
            extracted_invoices.append(InvoiceData(
                filename=filename,
                warnings=[f"Failed to process: {str(exc)}"],
                status="Failed"
            ))
            
    # Validate entire batch
    validated = validate_batch(extracted_invoices)
    SESSIONS[session_id] = validated
    
    return {
        "session_id": session_id,
        "count": len(validated),
        "invoices": [inv.model_dump() for inv in validated]
    }

@app.get("/api/batches")
def list_batches():
    batches = []
    for session_id, invoices in SESSIONS.items():
        statuses = Counter(invoice.status for invoice in invoices)
        batches.append({
            "session_id": session_id,
            "filename": invoices[0].filename if invoices else "",
            "count": len(invoices),
            "needs_attention": len(invoices) - statuses["Ready"],
        })
        if len(batches) == 50:
            break
    return {"batches": batches}


@app.get("/api/invoices/{session_id}")
def get_invoices(session_id: str):
    """Retrieve invoices for a session."""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"invoices": [inv.model_dump() for inv in SESSIONS[session_id]]}

@app.put("/api/invoices/{session_id}/{invoice_id}")
def update_invoice(session_id: str, invoice_id: str, update_data: InvoiceUpdate):
    """Update fields on an invoice and re-validate."""
    with batch_write_lock:
        if session_id not in SESSIONS:
            raise HTTPException(status_code=404, detail="Session not found")

        invoices = SESSIONS[session_id]
        target_inv = next((inv for inv in invoices if inv.id == invoice_id), None)

        if not target_inv:
            raise HTTPException(status_code=404, detail="Invoice not found")

        updates = update_data.model_dump(exclude_unset=True)
        try:
            candidate = InvoiceData.model_validate({**target_inv.model_dump(), **updates})
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc
        invoices[invoices.index(target_inv)] = candidate
        SESSIONS[session_id] = validate_batch(invoices)
        return candidate.model_dump()


@app.post("/api/generate/{session_id}")
def generate_workbook(session_id: str):
    """Generate Excel workbook from current invoices in session."""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
        
    invoices = SESSIONS[session_id]
    if not invoices:
        raise HTTPException(status_code=400, detail="No invoices in session to export")
        
    session_out_dir = os.path.join(OUTPUT_DIR, session_id)
    try:
        with batch_write_lock:
            out_path = generate_excel(invoices, TEMPLATE_PATH, session_out_dir)
        filename = os.path.basename(out_path)
        return {
            "success": True,
            "filename": filename,
            "download_url": f"/api/download/{session_id}/{filename}"
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {str(exc)}")

@app.get("/api/download/{session_id}/{filename}")
def download_file(session_id: str, filename: str):
    """Download the generated Excel file."""
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")
    safe_filename = os.path.basename(filename)
    if safe_filename != filename or not filename.endswith(".xlsx"):
        raise HTTPException(status_code=404, detail="File not found")
    file_path = os.path.join(OUTPUT_DIR, session_id, safe_filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=safe_filename
    )
