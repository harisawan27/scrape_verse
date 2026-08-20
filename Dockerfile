# ==============================================================================
# Web Radar — Production Backend Dockerfile for Hugging Face Spaces
# SDK: docker | Port: 7860
# ==============================================================================

FROM python:3.11-slim

# Avoid writing .pyc files and buffer stdout/stderr for clean streaming logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

WORKDIR /app

# Install system utilities if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python backend package and dependencies
COPY backend/pyproject.toml /app/backend/
RUN pip install --no-cache-dir ./backend

# Copy application source code and database migrations
COPY backend /app/backend
COPY database /app/database

# Hugging Face Space non-root user (user ID 1000)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

EXPOSE 7860

# Run database migrations on startup, then launch FastAPI backend on port 7860
CMD ["sh", "-c", "python database/migrate.py && python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 7860"]
