#!/bin/bash
set -e

# Enhanced Docker Entrypoint Script for LandPPT
# Includes database initialization and health checks

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log with color and timestamp
log() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] ${message}${NC}"
}

log $BLUE "🚀 LandPPT 容器启动�?.."

# Set default environment variables if not provided
export PYTHONPATH="${PYTHONPATH:-/app/src:/opt/venv}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/root/.cache/ms-playwright}"

# Ensure required directories exist
log $BLUE "📁 创建必要目录..."
mkdir -p /app/{temp,uploads,data,logs} \
         /app/temp/{ai_responses_cache,style_genes_cache,summeryanyfile_cache,templates_cache} \
         /app/research_reports \
         /app/lib/{Linux,MacOS,Windows}

# Set proper permissions
chmod -R 755 /app/temp /app/uploads /app/data /app/logs 2>/dev/null || true

# Database connectivity check and initialization
if [ "${SKIP_DB_CHECK:-false}" != "true" ]; then
    log $BLUE "🔍 执行数据库连接检�?.."
    
    # Wait for database to be ready
    if [ -n "$DB_HOST" ] || [ -n "$SUPABASE_URL" ]; then
        max_attempts=30
        attempt=1
        
        while [ $attempt -le $max_attempts ]; do
            log $YELLOW "尝试连接数据�?(�?$attempt/$max_attempts �?..."
            
            if [ -f "/app/tools/quick_db_check.py" ]; then
                # Run database health check
                if python3 -c "
import sys
sys.path.insert(0, '/opt/venv')
import os
import psycopg2

config = {
    'host': os.getenv('DB_HOST', 'your-supabase-host'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'postgres'),
    'user': os.getenv('DB_USER', 'your_db_user'),
    'password': os.getenv('DB_PASSWORD', 'your_secure_password'),
    'sslmode': 'require'
}

try:
    conn = psycopg2.connect(connect_timeout=5, **config)
    with conn.cursor() as cur:
        cur.execute('SELECT 1;')
        cur.fetchone()
    conn.close()
    print('数据库连接成�?)
except Exception as e:
    print(f'数据库连接失�? {e}')
    exit(1)
" 2>/dev/null; then
                log $GREEN "�?数据库连接成�?
                break
            else
                log $YELLOW "⚠️ 数据库连接失败，等待重试..."
                sleep 2
                attempt=$((attempt + 1))
            fi
        done
        
        if [ $attempt -gt $max_attempts ]; then
            if [ "${REQUIRE_DB:-true}" = "true" ]; then
                log $RED "�?数据库连接失败，无法启动应用"
                exit 1
            else
                log $YELLOW "⚠️ 数据库连接失败，但允许应用启�?
            fi
        fi
    else
        log $YELLOW "⚠️ 未配置数据库连接信息，跳过数据库检�?
    fi
else
    log $YELLOW "⚠️ 跳过数据库检�?(SKIP_DB_CHECK=true)"
fi

# Run database schema verification if enabled
if [ "${RUN_DB_SCHEMA_CHECK:-false}" = "true" ] && [ -f "/app/tools/database_health_check.py" ]; then
    log $BLUE "🔍 执行数据�?Schema 验证..."
    if python3 /app/tools/database_health_check.py --non-interactive 2>/dev/null; then
        log $GREEN "�?数据�?Schema 验证通过"
    else
        log $YELLOW "⚠️ 数据�?Schema 验证失败，但允许应用继续启动"
    fi
fi

# Check environment configuration
log $BLUE "🔧 检查环境配�?.."

# Validate essential environment variables
essential_vars=("PYTHONPATH")
for var in "${essential_vars[@]}"; do
    if [ -z "${!var}" ]; then
        log $RED "�?必需的环境变量未设置: $var"
        exit 1
    else
        log $GREEN "�?$var = ${!var}"
    fi
done

# Check if .env file exists and load it
if [ -f "/app/.env" ]; then
    log $BLUE "📄 加载环境配置文件..."
    set -a  # automatically export all variables
    source /app/.env
    set +a
    log $GREEN "�?环境配置已加�?
else
    log $YELLOW "⚠️ 未找�?.env 文件，使用默认配�?
fi

# Performance optimization
log $BLUE "�?应用性能优化..."

# Set Python optimizations
export PYTHONOPTIMIZE=1
export PYTHONHASHSEED=random

# Garbage collection tuning for better performance
export PYTHONGC="0"

log $GREEN "�?性能优化完成"

# Final health check before starting main application
log $BLUE "🏥 启动前最终健康检�?.."

# Check if main application file exists
if [ ! -f "/app/run.py" ]; then
    log $RED "�?主应用文�?run.py 不存�?
    exit 1
fi

# Check Python import paths
if ! python3 -c "import sys; print('Python path OK')" >/dev/null 2>&1; then
    log $RED "�?Python 环境配置错误"
    exit 1
fi

log $GREEN "�?启动前检查完�?

# Start the main application
log $GREEN "🎯 启动 LandPPT 主应�?.."
log $BLUE "命令: $@"

# Execute the main command
exec "$@"
