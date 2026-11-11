from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.responses import FileResponse
import os
import glob
from app.database import get_db
from app.models.db_models import Job, Invoice as DBInvoice
from app.extraction.engine import process_pdf
from app.config import settings
from app.excel.generator import generate_excel
from app.excel.audit_report import generate_audit_csv
from app.models.schemas import InvoiceData

router = APIRouter()

@router.post("/{job_id}/process")
async def process_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job.status = "processing"
    await db.commit()
    
    job_dir = os.path.join(settings.UPLOAD_DIR, job_id)
    pdfs = glob.glob(os.path.join(job_dir, "*.pdf"))
    
    for pdf in pdfs:
        invoices_data = process_pdf(pdf)
        for inv_data in invoices_data:
            db_inv = DBInvoice(
                job_id=job.id,
                source_file=os.path.basename(pdf),
                status=inv_data.status,
                data=inv_data.model_dump()
            )
            db.add(db_inv)
            
        job.processed += 1
        
    job.status = "completed"
    await db.commit()
    return {"status": "processing_started"}

@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/{job_id}/results")
async def get_job_results(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBInvoice).where(DBInvoice.job_id == job_id))
    db_invoices = result.scalars().all()
    invoices = [InvoiceData(**inv.data) for inv in db_invoices]
    return {"job_id": job_id, "invoices": invoices, "duplicates": []}

@router.post("/{job_id}/generate-excel")
async def generate_excel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBInvoice).where(DBInvoice.job_id == job_id))
    db_invoices = result.scalars().all()
    invoices = [InvoiceData(**inv.data) for inv in db_invoices] # if inv.status == "approved" or something
    
    excel_path = generate_excel(invoices, settings.TEMPLATE_PATH, os.path.join(settings.OUTPUT_DIR, job_id))
    audit_path = generate_audit_csv(invoices, os.path.join(settings.OUTPUT_DIR, job_id))
    
    return {"excel_url": f"/api/jobs/{job_id}/download-excel", "audit_url": f"/api/jobs/{job_id}/download-audit"}

@router.get("/{job_id}/download-excel")
async def download_excel(job_id: str):
    dir_path = os.path.join(settings.OUTPUT_DIR, job_id)
    files = glob.glob(os.path.join(dir_path, "*.xlsx"))
    if not files:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(files[0])

@router.get("/{job_id}/download-audit")
async def download_audit(job_id: str):
    dir_path = os.path.join(settings.OUTPUT_DIR, job_id)
    files = glob.glob(os.path.join(dir_path, "*.csv"))
    if not files:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(files[0])
    
@router.get("/{job_id}/pdf/{filename}")
async def get_job_pdf(job_id: str, filename: str):
    pdf_path = os.path.join(settings.UPLOAD_DIR, job_id, filename)
    if not os.path.exists(pdf_path):
         raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(pdf_path)
