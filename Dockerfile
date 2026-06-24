# ---- Build stage ----
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Runtime stage ----
FROM python:3.11-slim

# Create non-root user
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/app/.local

# Copy application code (excluding files from .dockerignore)
COPY --chown=app:app . .

# Ensure local Python packages are on PATH
ENV PATH=/home/app/.local/bin:$PATH

# Health check: the daemon process should always be alive
HEALTHCHECK --interval=300s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "src.main" > /dev/null || exit 1

USER app

# Default: run as daemon (continuous mode)
CMD ["python", "-m", "src.main", "--daemon"]
