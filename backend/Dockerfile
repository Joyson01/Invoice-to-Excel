FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies for pdfplumber (uses pdfminer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Create data directories
RUN groupadd --system invoice && useradd --system --gid invoice invoice && mkdir -p /app/data /app/template && chown invoice:invoice /app/data
USER invoice

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
