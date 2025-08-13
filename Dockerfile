# LandPPT Docker Image with Enhanced Database Health Check
# Compatible with GitHub Actions and local builds
# Multi-stage build for minimal image size

# Build stage
FROM python:3.11-slim AS builder

# Set environment variables for build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Set work directory and copy dependency files
WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./

# Install Python dependencies to a specific directory
RUN uv pip install --target=/opt/venv apryse-sdk>=11.5.0 --extra-index-url=https://pypi.apryse.com && \
    uv pip install --target=/opt/venv -r pyproject.toml && \
    # Install database health check dependencies
    uv pip install --target=/opt/venv psycopg2-binary requests && \
    # Clean up build artifacts
    find /opt/venv -name "*.pyc" -delete && \
    find /opt/venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Production stage
FROM python:3.11-slim AS production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src:/opt/venv \
    PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright \
    HOME=/root

# Install only essential runtime dependencies in one layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    poppler-utils \
    libmagic1 \
    ca-certificates \
    curl \
    chromium \
    libgomp1 \
    fonts-liberation \
    fonts-noto-cjk \
    fontconfig \
    netcat-openbsd \
    libpq-dev \
    postgresql-client \
    unzip \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache

# Install rclone for backup functionality
RUN curl https://rclone.org/install.sh | bash

# Create non-root user (for compatibility, but run as root)
RUN groupadd -r landppt && \
    useradd -r -g landppt -m -d /home/landppt landppt && \
    mkdir -p /home/landppt/.cache/ms-playwright /root/.cache/ms-playwright

# Copy Python packages from builder
COPY --from=builder /opt/venv /opt/venv

# Install Playwright with minimal footprint
RUN pip install --no-cache-dir playwright==1.40.0 && \
    playwright install chromium && \
    chown -R landppt:landppt /home/landppt && \
    rm -rf /tmp/* /var/tmp/*

# Set work directory
WORKDIR /app

# Copy application code (minimize layers)
COPY run.py ./
COPY src/ ./src/
COPY template_examples/ ./template_examples/
COPY .env.example ./.env

# Copy standard scripts first (always available)
COPY docker-healthcheck.sh docker-entrypoint.sh ./

# Copy backup scripts
COPY backup_to_r2.sh backup_to_r2_enhanced.sh ./

# Create tools directory and copy database health check tools
RUN mkdir -p tools
COPY database_health_check.py quick_db_check.py database_diagnosis.py simple_performance_test.py ./tools/ 
# Create placeholder if tools are missing
RUN [ -f "tools/database_health_check.py" ] || echo "#!/usr/bin/env python3\nprint('Database tools not available')" > tools/placeholder.py

# Copy enhanced scripts (create them if missing)
COPY docker-healthcheck-enhanced.sh ./
COPY docker-entrypoint-enhanced.sh ./
# Create placeholder scripts if enhanced versions are missing
RUN [ -f "docker-healthcheck-enhanced.sh" ] || cp docker-healthcheck.sh docker-healthcheck-enhanced.sh
RUN [ -f "docker-entrypoint-enhanced.sh" ] || cp docker-entrypoint.sh docker-entrypoint-enhanced.sh

# Create directories and set permissions in one layer
RUN chmod +x docker-healthcheck*.sh docker-entrypoint*.sh backup_to_r2*.sh 2>/dev/null || true && \
    chmod +x tools/*.py 2>/dev/null || true && \
    mkdir -p temp/ai_responses_cache temp/style_genes_cache temp/summeryanyfile_cache temp/templates_cache \
             research_reports lib/Linux lib/MacOS lib/Windows uploads data tools logs && \
    chown -R landppt:landppt /app /home/landppt && \
    chmod -R 755 /app /home/landppt && \
    chmod 666 /app/.env && \
    # Create smart script selection
    if [ -f "docker-healthcheck-enhanced.sh" ]; then \
        echo "Using enhanced health check script" && \
        ln -sf docker-healthcheck-enhanced.sh docker-healthcheck-active.sh; \
    else \
        echo "Using standard health check script" && \
        ln -sf docker-healthcheck.sh docker-healthcheck-active.sh; \
    fi && \
    if [ -f "docker-entrypoint-enhanced.sh" ]; then \
        echo "Using enhanced entrypoint script" && \
        ln -sf docker-entrypoint-enhanced.sh docker-entrypoint-active.sh; \
    else \
        echo "Using standard entrypoint script" && \
        ln -sf docker-entrypoint.sh docker-entrypoint-active.sh; \
    fi && \
    # Create backup script selection
    if [ -f "backup_to_r2_enhanced.sh" ]; then \
        echo "Using enhanced backup script" && \
        ln -sf backup_to_r2_enhanced.sh backup-active.sh; \
    else \
        echo "Using standard backup script" && \
        ln -sf backup_to_r2.sh backup-active.sh; \
    fi

# Keep landppt user but run as root to handle file permissions
# USER landppt

# Expose port
EXPOSE 8000

# Enhanced health check with fallback
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD ./docker-healthcheck-active.sh

# Set entrypoint and command with smart script selection
ENTRYPOINT ["./docker-entrypoint-active.sh"]
CMD ["python", "run.py"]

# Metadata labels
LABEL maintainer="LandPPT Team" \
      description="LandPPT with enhanced database health check capabilities" \
      version="enhanced" \
      org.opencontainers.image.title="LandPPT Enhanced" \
      org.opencontainers.image.description="LandPPT application with integrated database monitoring" \
      org.opencontainers.image.vendor="LandPPT" \
      org.opencontainers.image.licenses="MIT"
