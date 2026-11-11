import os
import shutil
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from app.config import settings
from app.extraction.label_processor import process_labels

router = APIRouter()

@router.post("/process")
async def upload_and_process_labels(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(settings.UPLOAD_DIR, "labels", job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    input_path = os.path.join(job_dir, "input.pdf")
    output_pdf = os.path.join(job_dir, "output.pdf")
    output_csv = os.path.join(job_dir, "manifest.csv")
    
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    stats = process_labels(input_path, output_pdf, output_csv)
    
    return {
        "job_id": job_id,
        "stats": stats,
        "pdf_url": f"/api/labels/{job_id}/download/pdf",
        "csv_url": f"/api/labels/{job_id}/download/csv"
    }

@router.get("/{job_id}/download/{file_type}")
async def download_label_file(job_id: str, file_type: str):
    job_dir = os.path.join(settings.UPLOAD_DIR, "labels", job_id)
    
    if file_type == "pdf":
        path = os.path.join(job_dir, "output.pdf")
        media_type = "application/pdf"
        filename = f"deduped_labels_{job_id[:8]}.pdf"
    elif file_type == "csv":
        path = os.path.join(job_dir, "manifest.csv")
        media_type = "text/csv"
        filename = f"manifest_{job_id[:8]}.csv"
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
        
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(path, media_type=media_type, filename=filename)
