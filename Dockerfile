# FlowSlide Docker Image with Enhanced Database Health Check
# Compatible with GitHub Actions and local builds
# Multi-stage build for minimal image size

# Build stage
FROM python:3.11-slim AS builder

# Set environment variables for build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright \
    HOME=/root

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
COPY pyproject.toml uv.toml uv.lock* README.md ./
# Cache bust arg to force rebuild on new commits (for CI reliability)
ARG CACHE_BUST
RUN echo "Cache bust: ${CACHE_BUST}" > /build-cache-bust


# Install Python dependencies using uv (faster and more reliable)
# uv.toml configures extra-index-url for apryse-sdk automatically
# Create a virtual environment and install all Python dependencies into it.
# We install into /opt/venv in the builder stage and copy that venv to the final image.
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel && \
    # Install CPU-only PyTorch wheels first to avoid pulling CUDA libs into the venv
    # This uses the official CPU wheel index and prevents pip from selecting CUDA-enabled
    # manylinux wheels which are very large and can exhaust buildkit temporary storage.
    /opt/venv/bin/pip install --no-cache-dir torch torchvision torchaudio -f https://download.pytorch.org/whl/cpu/torch_stable.html && \
    # Install the project and development extras into the venv.
    # Do not pass pyproject.toml to pip -r (that's for requirements files).
    /opt/venv/bin/pip install --no-cache-dir -e '.[dev]' --extra-index-url https://pypi.apryse.com && \
    echo "✅ All dependencies installed successfully into /opt/venv"

# Clean up build artifacts
RUN find /opt/venv -name "*.pyc" -delete && \
    find /opt/venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Production stage
FROM python:3.11-slim AS production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright \
    HOME=/root

# Install essential runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libmagic1 \
    libpq-dev \
    postgresql-client \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install PDF and document processing tools (core only)
# Cache buster: 2025-08-13-v2
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Note: wkhtmltopdf installation skipped due to compatibility issues
# Alternative PDF generation methods will be used via Playwright/Chrome

# Install fonts and display tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    fonts-liberation \
    fontconfig \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install browser dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    chromium \
    libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install network tools (try different netcat packages)
RUN apt-get update && \
    (apt-get install -y --no-install-recommends netcat-traditional || \
     apt-get install -y --no-install-recommends netcat-openbsd || \
     apt-get install -y --no-install-recommends netcat) \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (for compatibility, but run as root)
RUN groupadd -r flowslide && \
    useradd -r -g flowslide -m -d /home/flowslide flowslide && \
    mkdir -p /home/flowslide/.cache/ms-playwright /root/.cache/ms-playwright

# Copy Python packages from builder
# Note: Using system Python instead of virtual environment for simplicity

# Install Playwright with minimal footprint (like LandPPT)
RUN pip install --no-cache-dir playwright==1.40.0 && \
    playwright install chromium && \
    chown -R flowslide:flowslide /home/flowslide && \
    rm -rf /tmp/* /var/tmp/*

# Set work directory
WORKDIR /app

# Copy application code (minimize layers)
COPY run.py ./
COPY src/ ./src/
# Ensure template examples are included in the final image so the entrypoint can import them
COPY template_examples/ ./template_examples/

# Copy standard scripts first (always available)
COPY docker-healthcheck.sh docker-entrypoint.sh ./

# Create tools directory and placeholder for database health check tools
RUN mkdir -p tools && \
    echo "#!/usr/bin/env python3\nprint('Database tools not available')" > tools/placeholder.py && \
    chmod +x tools/placeholder.py

# Create enhanced scripts from standard ones
RUN cp docker-healthcheck.sh docker-healthcheck-enhanced.sh && \
    cp docker-entrypoint.sh docker-entrypoint-enhanced.sh

# Create directories and set permissions in one layer
RUN chmod +x docker-healthcheck*.sh docker-entrypoint*.sh 2>/dev/null || true && \
    find tools -name "*.py" -exec chmod +x {} \; 2>/dev/null || true && \
    mkdir -p temp/ai_responses_cache temp/style_genes_cache temp/summeryanyfile_cache temp/templates_cache \
             research_reports lib/Linux lib/MacOS lib/Windows uploads data tools logs db && \
    chown -R flowslide:flowslide /app /home/flowslide && \
    chmod -R 755 /app /home/flowslide && \
    chmod 777 /app/db && \
    # Set .env permissions if file exists (for mounted volumes)
    [ -f "/app/.env" ] && chmod 666 /app/.env || true && \
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
    echo "Backup handled by Python service (boto3)" && \
    echo "#!/bin/bash\necho 'Backup handled by Python service using boto3'" > backup-active.sh && \
    chmod +x backup-active.sh

# Copy the venv created during the build stage into the production image so runtime
# has all Python dependencies available.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"

# Keep flowslide user but run as root to handle file permissions
# USER flowslide

# Expose port
EXPOSE 8000

# Enhanced health check with fallback
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD ./docker-healthcheck-active.sh

# Set entrypoint and command with smart script selection
ENTRYPOINT ["./docker-entrypoint-active.sh"]
CMD ["python", "run.py"]

# Metadata labels
LABEL maintainer="FlowSlide Team" \
      description="FlowSlide with enhanced database health check capabilities" \
      version="enhanced" \
      org.opencontainers.image.title="FlowSlide Enhanced" \
      org.opencontainers.image.description="FlowSlide application with integrated database monitoring" \
      org.opencontainers.image.vendor="FlowSlide" \
      org.opencontainers.image.source="https://github.com/openai118/FlowSlide" \
    org.opencontainers.image.licenses="Apache-2.0"
