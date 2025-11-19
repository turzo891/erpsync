# Dockerfile for ERP Sync
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directory for database and logs
RUN mkdir -p /data /logs

# Make scripts executable
RUN chmod +x main.py troubleshoot.py

# Expose Django server port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Default command (can be overridden)
CMD ["gunicorn", "erpsync_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
