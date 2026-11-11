"""Upload endpoint - handles multipart PDF file uploads."""

import logging
import os
import re
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.database import SessionLocal
from app.models.db_models import Job

log = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILENAME_LENGTH = 255


def _sanitize_filename(filename: str) -> str:
    """Remove dangerous characters from filenames."""
    # Keep only alphanumeric, dots, hyphens, underscores
    name = re.sub(r"[^\w.\-]", "_", filename)
    if len(name) > MAX_FILENAME_LENGTH:
        name = name[:MAX_FILENAME_LENGTH]
    return name


def _validate_file(file: UploadFile) -> None:
    """Validate file type and basic properties."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File has no filename")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Only PDF files are accepted.",
        )

    # Check content type
    if file.content_type and "pdf" not in file.content_type.lower():
        log.warning("File %s has unexpected content type: %s", file.filename, file.content_type)


@router.post("/invoices/upload")
async def upload_invoices(files: list[UploadFile] = File(...)):
    """Upload one or more invoice PDF files for processing.

    Creates a processing job and stores the uploaded files.
    Returns the job_id for subsequent processing and status checks.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Validate all files first
    for f in files:
        _validate_file(f)

    # Create job record
    async with SessionLocal() as db:
        job = Job(total_files=len(files))
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    # Store files
    job_dir = os.path.join(settings.UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    saved_files = []
    for file in files:
        safe_name = _sanitize_filename(file.filename)
        file_path = os.path.join(job_dir, safe_name)

        # Avoid overwriting - append counter if needed
        base, ext = os.path.splitext(file_path)
        counter = 1
        while os.path.exists(file_path):
            file_path = f"{base}_{counter}{ext}"
            counter += 1

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Basic PDF validation: check magic bytes
            with open(file_path, "rb") as f:
                header = f.read(5)
                if header != b"%PDF-":
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=400,
                        detail=f"File '{file.filename}' is not a valid PDF",
                    )

            file_size = os.path.getsize(file_path)
            if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                os.remove(file_path)
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{file.filename}' exceeds {settings.MAX_FILE_SIZE_MB}MB limit",
                )

            saved_files.append(safe_name)
            log.info("Saved %s (%d bytes)", safe_name, file_size)

        except HTTPException:
            raise
        except Exception as exc:
            log.error("Failed to save %s: %s", file.filename, exc)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file '{file.filename}'",
            )

    return {
        "job_id": job_id,
        "file_count": len(saved_files),
        "files": saved_files,
        "status": "uploaded",
    }
