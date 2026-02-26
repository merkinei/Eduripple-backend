# Dockerfile for EduRipple Backend
# Production build for Railway deployment

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies:
#   - WeasyPrint needs: libcairo2, libpango-1.0, libpangocairo-1.0, libgdk-pixbuf2.0, libffi-dev, shared-mime-info
#   - PostgreSQL client: libpq5
#   - Build tools: gcc, libpq-dev (for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libpq5 \
    curl \
    # WeasyPrint system dependencies
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    libglib2.0-0 \
    libxml2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create writable directories for SQLite databases and logs
RUN mkdir -p /app/logs /app/resources /app/backups /data \
    && chmod -R 777 /data \
    && chmod -R 755 /app

# DATA_DIR: persistent volume mount point on Railway (defaults to /data)
ENV DATA_DIR=/data
ENV PORT=5000

# Expose port (Railway overrides this)
EXPOSE ${PORT}

# Copy seed curriculum.db into /app so init_data.py can seed the volume.
# Override DATA_DIR temporarily so the seed DB is created in /app, not /data.
RUN DATA_DIR=/app python -c "from curriculum_db import init_curriculum_db; init_curriculum_db()" || true
RUN cp /app/curriculum.db /app/seed_curriculum.db 2>/dev/null || true

# Use shell form so $PORT is expanded at runtime.
# init_data.py seeds the persistent volume on first boot, then gunicorn starts.
CMD python init_data.py && gunicorn -w 4 -b 0.0.0.0:$PORT --timeout 120 --access-logfile - --error-logfile - "wsgi:app"
