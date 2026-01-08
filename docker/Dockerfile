# Multi-stage Dockerfile for Prime Parser service

# Stage 1: Builder
FROM python:3.14-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Build wheels for dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels .

# Stage 2: Runtime
FROM python:3.14-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels

# Install dependencies from wheels
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

# Copy application code
COPY --chown=appuser:appuser src/ /app/src/
#COPY --chown=appuser:appuser config/ /app/config/

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 19779

# Set default environment
ENV ENVIRONMENT=prod \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:19779/').read()"

# Run application
CMD ["uvicorn", "src.prime_parser.main:app", "--host", "0.0.0.0", "--port", "19779"]
