"""API router - aggregates all endpoint modules under /api."""

from fastapi import APIRouter

from app.api import config_api, invoices, jobs, upload, labels

api_router = APIRouter(prefix="/api")

# Upload: POST /api/invoices/upload
api_router.include_router(upload.router, tags=["upload"])

# Jobs: /api/jobs/...
api_router.include_router(jobs.router, tags=["jobs"])

# Invoices: /api/invoices/...
api_router.include_router(invoices.router, tags=["invoices"])

# Config: /api/config
api_router.include_router(config_api.router, tags=["config"])
api_router.include_router(labels.router, prefix="/labels", tags=["labels"])
