#!/bin/bash
set -e

# Enhanced Docker Health Check Script for LandPPT
# Includes database connectivity verification

echo "🔍 LandPPT 容器健康检查"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if main application is responding
log "检查主应用响应..."
if ! curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
    log "❌ 主应用健康检查失败"
    exit 1
fi
log "✅ 主应用响应正常"

# Check database connectivity if environment variables are set
if [ -n "$DATABASE_URL" ] || [ -n "$SUPABASE_URL" ]; then
    log "检查数据库连接..."
    
    # Run a quick database check
    if [ -f "/app/tools/quick_db_check.py" ] && command -v python3 >/dev/null 2>&1; then
        # Create a non-interactive version of the database check
        cat > /tmp/db_health_check.py << 'EOF'
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/opt/venv')

try:
    import psycopg2
    from datetime import datetime
    
    # Database configuration from environment or default
    config = {
        'host': os.getenv('DB_HOST', 'db.fiuzetazperebuqwmrna.supabase.co'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'postgres'),
        'user': os.getenv('DB_USER', 'landppt_user'),
        'password': os.getenv('DB_PASSWORD', 'Openai9zLwR1sT4u'),
        'sslmode': 'require'
    }
    
    # Quick connection test
    conn = psycopg2.connect(**config)
    with conn.cursor() as cur:
        cur.execute("SELECT 1;")
        cur.fetchone()
    conn.close()
    
    print("✅ 数据库连接正常")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
    sys.exit(1)
EOF
        
        if python3 /tmp/db_health_check.py; then
            log "✅ 数据库连接验证通过"
        else
            log "⚠️ 数据库连接验证失败，但允许应用继续运行"
            # 不退出，允许应用在数据库暂时不可用时继续运行
        fi
        rm -f /tmp/db_health_check.py
    else
        log "⚠️ 跳过数据库检查（工具不可用）"
    fi
else
    log "⚠️ 跳过数据库检查（未配置数据库连接）"
fi

# Check disk space
log "检查磁盘空间..."
DISK_USAGE=$(df /app | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    log "⚠️ 磁盘空间不足: ${DISK_USAGE}%"
    # 警告但不退出
else
    log "✅ 磁盘空间正常: ${DISK_USAGE}%"
fi

# Check memory usage (if available)
if command -v free >/dev/null 2>&1; then
    MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    if [ "$MEMORY_USAGE" -gt 90 ]; then
        log "⚠️ 内存使用率高: ${MEMORY_USAGE}%"
    else
        log "✅ 内存使用正常: ${MEMORY_USAGE}%"
    fi
fi

# Check if required directories exist and are writable
log "检查目录权限..."
for dir in /app/temp /app/uploads /app/data; do
    if [ ! -d "$dir" ]; then
        log "⚠️ 目录不存在: $dir"
    elif [ ! -w "$dir" ]; then
        log "⚠️ 目录不可写: $dir"
    else
        log "✅ 目录权限正常: $dir"
    fi
done

log "🎉 容器健康检查完成"
exit 0
