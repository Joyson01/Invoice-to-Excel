# =============================================================================
# Multi-stage Unified Production Dockerfile (100% Free Cloud Deployment Ready)
# Builds React frontend and serves both API and Web UI via FastAPI on $PORT
# =============================================================================

# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Backend & Web Server
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies for RapidOCR / OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files and templates
COPY backend/app ./app
COPY templates/ ./templates
COPY 66075.pdf PDF.pdf scanned_invoice.pdf ./

# Copy compiled frontend assets from Stage 1
COPY --from=frontend-builder /build/dist ./frontend_dist

# Create dedicated data directory with non-root security user
RUN groupadd --system invoice && useradd --system --gid invoice invoice \
    && mkdir -p /app/data /app/uploads /app/output \
    && chown -R invoice:invoice /app/data /app/uploads /app/output

USER invoice

# Cloud platforms (Render, Hugging Face, Railway, Cloud Run) supply $PORT dynamically
ENV PORT=8000
ENV TEMPLATE_PATH=/app/templates/B2B_bulk_upload_template.xlsx
ENV STATE_DIR=/app/data
ENV UPLOAD_DIR=/app/uploads
ENV OUTPUT_DIR=/app/output
ENV CORS_ORIGINS=*

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
