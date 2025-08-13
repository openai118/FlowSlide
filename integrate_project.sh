#!/bin/bash
# LandPPT 项目自动整合脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_header() {
    echo -e "${PURPLE}🎯 $1${NC}"
}

# 检查原项目目录
check_original_project() {
    log_info "检查原项目目录..."
    
    local original_path="../landppt-original"
    
    if [ ! -d "$original_path" ]; then
        log_error "未找到原项目目录: $original_path"
        echo ""
        echo "请按以下步骤获取原项目："
        echo "1. 访问 https://github.com/sligter/LandPPT"
        echo "2. 点击 'Code' -> 'Download ZIP'"
        echo "3. 解压到 f:/projects/landppt-original/"
        echo ""
        exit 1
    fi
    
    log_success "找到原项目目录"
    return 0
}

# 备份当前项目
backup_current_project() {
    log_header "备份当前项目"
    
    local backup_dir="../try1-backup-$(date +%Y%m%d_%H%M%S)"
    
    log_info "创建备份: $backup_dir"
    cp -r . "$backup_dir"
    
    log_success "当前项目已备份到: $backup_dir"
}

# 复制原项目核心文件
copy_original_files() {
    log_header "复制原项目文件"
    
    local original_path="../landppt-original"
    
    # 核心目录
    local core_dirs=("src" "template_examples" "docs")
    
    for dir in "${core_dirs[@]}"; do
        if [ -d "$original_path/$dir" ]; then
            log_info "复制目录: $dir"
            cp -r "$original_path/$dir" ./
            log_success "已复制: $dir"
        else
            log_warning "原项目中未找到目录: $dir"
        fi
    done
    
    # 核心文件
    local core_files=(
        "run.py"
        "pyproject.toml"
        "uv.lock"
        "uv.toml"
        ".python-version"
        "CONTRIBUTING.md"
        "LICENSE"
        "README.md"
        "README_EN.md"
    )
    
    for file in "${core_files[@]}"; do
        if [ -f "$original_path/$file" ]; then
            log_info "复制文件: $file"
            cp "$original_path/$file" ./
            log_success "已复制: $file"
        else
            log_warning "原项目中未找到文件: $file"
        fi
    done
}

# 合并环境配置
merge_env_config() {
    log_header "合并环境配置"
    
    local original_env="../landppt-original/.env.example"
    local current_env=".env.example"
    local merged_env=".env.example.merged"
    
    if [ ! -f "$original_env" ]; then
        log_warning "原项目环境配置不存在，保持当前配置"
        return 0
    fi
    
    log_info "合并环境配置文件..."
    
    # 创建合并后的环境配置
    cat > "$merged_env" << 'EOF'
# LandPPT 完整环境配置文件
# 原项目配置 + 数据库监控 + R2备份功能

# ======================
# AI 提供商配置
# ======================
DEFAULT_AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=your_azure_endpoint_here

# Ollama 本地模型配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# ======================
# 服务器配置
# ======================
HOST=0.0.0.0
PORT=8000
SECRET_KEY=your-secure-secret-key
BASE_URL=http://localhost:8000

# ======================
# 数据库配置
# ======================
DB_HOST=your-supabase-host
DB_PORT=5432
DB_NAME=postgres
DB_USER=your_db_user
DB_PASSWORD=your_secure_password

# ======================
# Supabase 配置
# ======================
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# ======================
# 存储配置
# ======================
STORAGE_BUCKET=your-storage-bucket
STORAGE_PROVIDER=supabase

# ======================
# 研究功能配置
# ======================
TAVILY_API_KEY=your_tavily_api_key_here
SEARXNG_HOST=http://localhost:8888
RESEARCH_PROVIDER=tavily

# ======================
# 图像服务配置
# ======================
ENABLE_IMAGE_SERVICE=true
PIXABAY_API_KEY=your_pixabay_api_key_here
UNSPLASH_ACCESS_KEY=your_unsplash_key_here
SILICONFLOW_API_KEY=your_siliconflow_key_here
POLLINATIONS_API_TOKEN=your_pollinations_token

# ======================
# 导出功能配置
# ======================
APRYSE_LICENSE_KEY=your_apryse_key_here

# ======================
# Cloudflare R2 备份配置
# ======================
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
R2_BUCKET_NAME=landppt-backups
BACKUP_SCHEDULE=0 2 * * *
BACKUP_RETENTION_DAYS=30
BACKUP_WEBHOOK_URL=

# ======================
# 健康检查配置
# ======================
SKIP_DB_CHECK=false
REQUIRE_DB=true
RUN_DB_SCHEMA_CHECK=true

# ======================
# 性能配置
# ======================
MAX_WORKERS=4
REQUEST_TIMEOUT=30
DB_POOL_SIZE=10
MAX_TOKENS=8192
TEMPERATURE=0.7

# ======================
# 应用配置
# ======================
DEBUG=false
LOG_LEVEL=INFO
TEMP_CLEANUP_INTERVAL=24

# ======================
# 安全配置
# ======================
JWT_SECRET=your_jwt_secret_key
API_RATE_LIMIT=100
MAX_UPLOAD_SIZE=50

# ======================
# 邮件配置 (可选)
# ======================
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=true

# ======================
# 监控配置 (可选)
# ======================
METRICS_ENABLED=false
METRICS_PORT=9090
HEALTH_CHECK_ENDPOINT=/health

# ======================
# Redis 配置 (可选)
# ======================
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=false

# ======================
# 开发配置
# ======================
DEV_RELOAD=false
DEV_HOST=0.0.0.0
ALLOWED_HOSTS=localhost,127.0.0.1
EOF

    # 备份原配置并使用新配置
    if [ -f "$current_env" ]; then
        mv "$current_env" "${current_env}.backup"
        log_info "原配置已备份为: ${current_env}.backup"
    fi
    
    mv "$merged_env" "$current_env"
    log_success "环境配置已合并"
}

# 合并 Dockerfile
merge_dockerfile() {
    log_header "合并 Dockerfile"
    
    local original_dockerfile="../landppt-original/Dockerfile"
    local enhanced_dockerfile="Dockerfile.ci-compatible"
    local merged_dockerfile="Dockerfile"
    
    if [ ! -f "$original_dockerfile" ]; then
        log_warning "原项目 Dockerfile 不存在，使用增强版 Dockerfile"
        cp "$enhanced_dockerfile" "$merged_dockerfile"
        return 0
    fi
    
    log_info "合并 Dockerfile..."
    
    # 基于增强版 Dockerfile，添加原项目的特定配置
    cat > "$merged_dockerfile" << 'EOF'
# LandPPT 完整版 Docker 镜像
# 原项目功能 + 数据库监控 + 备份功能

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

# Install runtime dependencies and tools
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
    cron \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache

# Install rclone for backup functionality
RUN curl https://rclone.org/install.sh | bash

# Create non-root user
RUN groupadd -r landppt && \
    useradd -r -g landppt -m -d /home/landppt landppt && \
    mkdir -p /home/landppt/.cache/ms-playwright /root/.cache/ms-playwright

# Copy Python packages from builder
COPY --from=builder /opt/venv /opt/venv

# Install Playwright
RUN pip install --no-cache-dir playwright==1.40.0 && \
    playwright install chromium && \
    chown -R landppt:landppt /home/landppt && \
    rm -rf /tmp/* /var/tmp/*

# Set work directory
WORKDIR /app

# Copy application code
COPY run.py ./
COPY src/ ./src/
COPY template_examples/ ./template_examples/
COPY .env.example ./.env

# Copy Docker scripts
COPY docker-healthcheck.sh docker-entrypoint.sh ./

# Copy database health check tools
RUN mkdir -p tools
COPY database_health_check.py quick_db_check.py database_diagnosis.py simple_performance_test.py ./tools/

# Copy backup scripts
COPY backup_to_r2.sh backup_to_r2_enhanced.sh restore_from_r2.sh backup-manager.sh ./

# Create enhanced scripts if they exist
COPY docker-healthcheck-enhanced.sh ./
COPY docker-entrypoint-enhanced.sh ./

# Set permissions and create directories
RUN chmod +x *.sh tools/*.py 2>/dev/null || true && \
    mkdir -p temp/ai_responses_cache temp/style_genes_cache temp/summeryanyfile_cache temp/templates_cache \
             research_reports lib/Linux lib/MacOS lib/Windows uploads data tools logs && \
    chown -R landppt:landppt /app /home/landppt && \
    chmod -R 755 /app /home/landppt && \
    chmod 666 /app/.env && \
    # Create smart script selection
    if [ -f "docker-healthcheck-enhanced.sh" ]; then \
        ln -sf docker-healthcheck-enhanced.sh docker-healthcheck-active.sh; \
    else \
        ln -sf docker-healthcheck.sh docker-healthcheck-active.sh; \
    fi && \
    if [ -f "docker-entrypoint-enhanced.sh" ]; then \
        ln -sf docker-entrypoint-enhanced.sh docker-entrypoint-active.sh; \
    else \
        ln -sf docker-entrypoint.sh docker-entrypoint-active.sh; \
    fi && \
    if [ -f "backup_to_r2_enhanced.sh" ]; then \
        ln -sf backup_to_r2_enhanced.sh backup-active.sh; \
    else \
        ln -sf backup_to_r2.sh backup-active.sh; \
    fi

# Expose port
EXPOSE 8000

# Enhanced health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD ./docker-healthcheck-active.sh

# Set entrypoint and command
ENTRYPOINT ["./docker-entrypoint-active.sh"]
CMD ["python", "run.py"]

# Metadata labels
LABEL maintainer="LandPPT Team" \
      description="LandPPT with database monitoring and R2 backup capabilities" \
      version="integrated" \
      org.opencontainers.image.title="LandPPT Integrated" \
      org.opencontainers.image.description="Complete AI PPT generation platform with monitoring and backup" \
      org.opencontainers.image.vendor="LandPPT" \
      org.opencontainers.image.licenses="Apache-2.0"
EOF

    log_success "Dockerfile 已合并"
}

# 合并 docker-compose.yml
merge_docker_compose() {
    log_header "合并 docker-compose.yml"
    
    local original_compose="../landppt-original/docker-compose.yml"
    local current_compose="docker-compose.yml"
    local merged_compose="docker-compose.integrated.yml"
    
    log_info "创建完整的 docker-compose 配置..."
    
    cat > "$merged_compose" << 'EOF'
version: '3.8'

services:
  landppt:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: landppt-integrated
    ports:
      - "8000:8000"
    environment:
      # AI 提供商配置
      - DEFAULT_AI_PROVIDER=${DEFAULT_AI_PROVIDER:-openai}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
      - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
      
      # 服务器配置
      - HOST=0.0.0.0
      - PORT=8000
      - SECRET_KEY=${SECRET_KEY}
      - BASE_URL=${BASE_URL:-http://localhost:8000}
      
      # 数据库配置
      - DB_HOST=${DB_HOST}
      - DB_PORT=${DB_PORT:-5432}
      - DB_NAME=${DB_NAME:-postgres}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      
      # Supabase 配置
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      
      # 存储配置
      - STORAGE_BUCKET=${STORAGE_BUCKET}
      - STORAGE_PROVIDER=${STORAGE_PROVIDER:-supabase}
      
      # 研究功能配置
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - SEARXNG_HOST=${SEARXNG_HOST}
      - RESEARCH_PROVIDER=${RESEARCH_PROVIDER:-tavily}
      
      # 图像服务配置
      - ENABLE_IMAGE_SERVICE=${ENABLE_IMAGE_SERVICE:-true}
      - PIXABAY_API_KEY=${PIXABAY_API_KEY}
      - UNSPLASH_ACCESS_KEY=${UNSPLASH_ACCESS_KEY}
      - SILICONFLOW_API_KEY=${SILICONFLOW_API_KEY}
      - POLLINATIONS_API_TOKEN=${POLLINATIONS_API_TOKEN}
      
      # 导出功能配置
      - APRYSE_LICENSE_KEY=${APRYSE_LICENSE_KEY}
      
      # R2 备份配置
      - R2_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
      - R2_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
      - R2_ENDPOINT=${R2_ENDPOINT}
      - R2_BUCKET_NAME=${R2_BUCKET_NAME}
      - BACKUP_WEBHOOK_URL=${BACKUP_WEBHOOK_URL}
      
      # 健康检查配置
      - SKIP_DB_CHECK=${SKIP_DB_CHECK:-false}
      - REQUIRE_DB=${REQUIRE_DB:-true}
      - RUN_DB_SCHEMA_CHECK=${RUN_DB_SCHEMA_CHECK:-true}
      
      # 性能配置
      - MAX_WORKERS=${MAX_WORKERS:-4}
      - REQUEST_TIMEOUT=${REQUEST_TIMEOUT:-30}
      - DB_POOL_SIZE=${DB_POOL_SIZE:-10}
      - MAX_TOKENS=${MAX_TOKENS:-8192}
      - TEMPERATURE=${TEMPERATURE:-0.7}
      
      # 应用配置
      - DEBUG=${DEBUG:-false}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    
    volumes:
      - landppt_data:/app/data
      - landppt_reports:/app/research_reports
      - landppt_cache:/app/temp
      - landppt_uploads:/app/uploads
      - landppt_logs:/app/logs
    
    restart: unless-stopped
    
    healthcheck:
      test: ["CMD", "./docker-healthcheck-active.sh"]
      interval: 30s
      timeout: 15s
      retries: 3
      start_period: 60s
    
    labels:
      - "landppt.service=main"
      - "landppt.description=AI PPT generation platform with monitoring"
    
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

  # 备份调度服务
  backup-scheduler:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: landppt-backup-scheduler
    depends_on:
      - landppt
    environment:
      # 继承主服务的环境变量
      - DB_HOST=${DB_HOST}
      - DB_PORT=${DB_PORT:-5432}
      - DB_NAME=${DB_NAME:-postgres}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - R2_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
      - R2_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
      - R2_ENDPOINT=${R2_ENDPOINT}
      - R2_BUCKET_NAME=${R2_BUCKET_NAME}
      - BACKUP_WEBHOOK_URL=${BACKUP_WEBHOOK_URL}
      - BACKUP_SCHEDULE=${BACKUP_SCHEDULE:-0 2 * * *}
      - BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}
    
    volumes:
      - landppt_data:/app/data:ro
      - landppt_reports:/app/research_reports:ro
      - landppt_logs:/app/logs:ro
    
    restart: unless-stopped
    profiles: ["backup"]
    
    command: >
      sh -c "
        echo 'Backup scheduler starting...'
        echo '$${BACKUP_SCHEDULE} /app/backup-active.sh' > /etc/crontabs/root
        echo 'Cron job scheduled: $${BACKUP_SCHEDULE}'
        crond -f -l 2
      "
    
    healthcheck:
      test: ["CMD", "pgrep", "crond"]
      interval: 60s
      timeout: 10s
      retries: 3
    
    labels:
      - "landppt.service=backup-scheduler"
      - "landppt.description=Automated backup service"

volumes:
  landppt_data:
    driver: local
  landppt_reports:
    driver: local
  landppt_cache:
    driver: local
  landppt_uploads:
    driver: local
  landppt_logs:
    driver: local

networks:
  default:
    name: landppt_network
EOF

    # 备份原配置
    if [ -f "$current_compose" ]; then
        mv "$current_compose" "${current_compose}.backup"
        log_info "原 docker-compose.yml 已备份"
    fi
    
    mv "$merged_compose" "$current_compose"
    log_success "docker-compose.yml 已合并"
}

# 更新脚本文件
update_scripts() {
    log_header "更新脚本文件"
    
    # 检查原项目脚本
    local original_path="../landppt-original"
    local original_scripts=("docker-entrypoint.sh" "docker-healthcheck.sh")
    
    for script in "${original_scripts[@]}"; do
        if [ -f "$original_path/$script" ]; then
            log_info "更新脚本: $script"
            
            # 创建增强版脚本
            local enhanced_script="${script%.sh}-enhanced.sh"
            
            # 基于原脚本创建增强版
            cp "$original_path/$script" "$enhanced_script"
            
            # 在增强版脚本中添加我们的功能
            if [[ "$script" == "docker-healthcheck.sh" ]]; then
                # 添加数据库健康检查
                cat >> "$enhanced_script" << 'EOFSCRIPT'

# 增强的健康检查功能
echo "Running enhanced health check..."

# 检查数据库监控工具
if [ -f "/app/tools/quick_db_check.py" ]; then
    echo "Checking database health..."
    python3 /app/tools/quick_db_check.py --non-interactive || echo "Database check warning"
fi

# 检查备份功能
if command -v rclone >/dev/null 2>&1; then
    echo "Backup tools available"
fi

echo "Enhanced health check completed"
EOFSCRIPT
            
            elif [[ "$script" == "docker-entrypoint.sh" ]]; then
                # 添加启动前检查
                cat >> "$enhanced_script" << 'EOFSCRIPT'

# 增强的启动功能
echo "Running enhanced startup..."

# 创建必要的目录
mkdir -p /app/logs /app/data /app/research_reports /app/temp

# 运行数据库健康检查（如果配置了数据库）
if [ -n "$DB_HOST" ] && [ -f "/app/tools/database_health_check.py" ]; then
    echo "Running database health check..."
    python3 /app/tools/database_health_check.py --non-interactive || echo "Database check completed with warnings"
fi

echo "Enhanced startup completed"
EOFSCRIPT
            fi
            
            chmod +x "$enhanced_script"
            log_success "已创建增强版脚本: $enhanced_script"
        else
            log_warning "原项目中未找到脚本: $script"
        fi
    done
}

# 创建整合后的文档
create_integrated_docs() {
    log_header "创建整合文档"
    
    # 创建完整的 README
    cat > "README_INTEGRATED.md" << 'EOF'
# LandPPT 完整版 - AI驱动的PPT生成平台

## 🌟 项目简介

LandPPT 完整版是一个集成了数据库监控、自动化备份和企业级运维功能的 AI PPT 生成平台。基于原始 LandPPT 项目，我们添加了以下企业级功能：

### 🎯 核心功能
- **AI PPT 生成**: 基于多种 AI 模型的智能演示文稿生成
- **数据库监控**: 实时监控 Supabase 数据库健康状态
- **自动化备份**: Cloudflare R2 自动备份和恢复
- **企业级部署**: Docker 容器化部署和 CI/CD 集成
- **系统监控**: 全面的健康检查和性能监控

### 🚀 增强功能

#### 数据库监控系统
- `database_health_check.py` - 全面健康检查
- `quick_db_check.py` - 快速日常监控  
- `database_diagnosis.py` - 详细诊断工具
- `simple_performance_test.py` - 性能验证

#### 备份和恢复系统
- 自动定时备份到 Cloudflare R2
- 支持数据库、文件、配置的完整备份
- 一键恢复功能
- 备份版本管理和清理

#### 企业级部署
- 多阶段 Docker 构建优化
- GitHub Actions CI/CD 集成
- 健康检查和自愈机制
- 资源限制和性能监控

## 📥 快速开始

### 1. 获取项目
```bash
# 下载完整项目
git clone <your-integrated-repo>
cd landppt-integrated
```

### 2. 配置环境
```bash
# 复制环境配置
cp .env.example .env

# 编辑配置文件，填入你的 API 密钥和数据库信息
# 包括：AI API 密钥、Supabase 配置、R2 备份配置等
```

### 3. 启动服务
```bash
# 使用 Docker Compose 启动
docker-compose up -d

# 或者本地开发
uv sync
uv run python run.py
```

### 4. 访问应用
- Web 界面: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 🔧 配置说明

### 必需配置
- **AI 提供商**: OpenAI、Anthropic、Google 等 API 密钥
- **数据库**: Supabase 数据库连接信息
- **存储**: Supabase Storage 或其他存储服务

### 可选配置  
- **备份**: Cloudflare R2 配置（推荐）
- **研究**: Tavily API 密钥
- **图像**: Pixabay、Unsplash API 密钥
- **通知**: Webhook URL 用于备份通知

## 🛠️ 管理工具

### 数据库监控
```bash
# 快速健康检查
python tools/quick_db_check.py

# 全面健康检查
python tools/database_health_check.py

# 诊断问题
python tools/database_diagnosis.py
```

### 备份管理
```bash
# 启动定时备份
./backup-manager.sh start-scheduler

# 立即执行备份
./backup-manager.sh run-backup

# 查看备份列表
./backup-manager.sh list-backups

# 恢复备份
./restore_from_r2.sh -l  # 列出备份
./restore_from_r2.sh 20241201_020000  # 恢复指定备份
```

### 系统验证
```bash
# 运行完整系统验证
python validate_system.py
```

## 🐳 Docker 部署

### 基础部署
```bash
# 启动主服务
docker-compose up -d landppt

# 启动包含备份服务
docker-compose --profile backup up -d
```

### 生产部署
```bash
# 使用生产配置
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 📊 监控和维护

### 健康检查
- 应用自动健康检查每 30 秒执行一次
- 数据库连接状态实时监控
- 备份任务执行状态跟踪

### 日志管理
```bash
# 查看应用日志
docker-compose logs -f landppt

# 查看备份日志
docker-compose logs -f backup-scheduler

# 查看系统日志
./backup-manager.sh logs
```

### 性能监控
- 数据库性能指标
- 应用响应时间
- 资源使用情况
- 备份执行时间

## 🔒 安全建议

1. **环境变量安全**
   - 使用强密码和复杂的 API 密钥
   - 定期轮换敏感密钥
   - 不要在代码中硬编码密钥

2. **网络安全**
   - 使用 HTTPS 访问
   - 配置防火墙规则
   - 限制数据库访问 IP

3. **备份安全**
   - R2 存储桶访问控制
   - 备份数据加密
   - 定期验证备份完整性

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建功能分支
3. 提交变更
4. 创建 Pull Request

## 📄 许可证

本项目采用 Apache License 2.0 许可证。

## 🙏 致谢

- 原始 LandPPT 项目: https://github.com/sligter/LandPPT
- 所有贡献者和社区成员

---

**如果这个项目对你有帮助，请给我们一个 ⭐️ Star！**
EOF

    log_success "已创建完整项目文档"
}

# 主整合函数
main() {
    log_header "LandPPT 项目自动整合"
    echo "开始时间: $(date)"
    echo "========================================"
    
    # 执行整合步骤
    check_original_project
    backup_current_project
    copy_original_files
    merge_env_config
    merge_dockerfile
    merge_docker_compose  
    update_scripts
    create_integrated_docs
    
    # 设置权限
    log_info "设置文件权限..."
    chmod +x *.sh 2>/dev/null || true
    chmod +x tools/*.py 2>/dev/null || true
    
    # 总结
    echo "========================================"
    log_success "项目整合完成！"
    echo ""
    echo "📁 整合结果:"
    echo "  ✅ 原项目核心文件已复制"
    echo "  ✅ 环境配置已合并"
    echo "  ✅ Docker 配置已优化"
    echo "  ✅ 脚本文件已增强"
    echo "  ✅ 文档已更新"
    echo ""
    echo "🚀 下一步:"
    echo "  1. 编辑 .env 文件，配置你的 API 密钥"
    echo "  2. 运行 'python validate_system.py' 验证系统"
    echo "  3. 使用 'docker-compose up -d' 启动服务"
    echo "  4. 访问 http://localhost:8000 开始使用"
    echo ""
    echo "📚 更多信息请查看:"
    echo "  - README_INTEGRATED.md"
    echo "  - INTEGRATION_GUIDE.md" 
    echo "  - DATABASE_MONITORING_GUIDE.md"
    
    echo ""
    echo "完成时间: $(date)"
}

# 执行主函数
main "$@"
