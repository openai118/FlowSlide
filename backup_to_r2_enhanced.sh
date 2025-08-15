#!/bin/bash
# FlowSlide 增强版备份脚本 - 支持数据库和文件备份到 Cloudflare R2
# 包含数据库监控集成功能
# 注意：未配置 R2 环境变量时将跳过备份并正常退出，不影响主程序运行。

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查并安装 rclone
check_rclone() {
    if ! command -v rclone &> /dev/null; then
        log_info "安装 rclone..."
        curl https://rclone.org/install.sh | bash
        if ! command -v rclone &> /dev/null; then
            log_error "rclone 安装失败"
            exit 1
        fi
    fi
    log_success "rclone 已准备就绪"
}

# 检查数据库监控工具
check_db_tools() {
    local tools_available=0
    
    if [ -f "/app/tools/quick_db_check.py" ]; then
        tools_available=1
    elif [ -f "/app/quick_db_check.py" ]; then
        tools_available=1
    elif [ -f "quick_db_check.py" ]; then
        tools_available=1
    fi
    
    if [ $tools_available -eq 1 ]; then
        log_success "数据库监控工具可用"
        return 0
    else
        log_warning "数据库监控工具不可用"
        return 1
    fi
}

# 执行数据库健康检查
run_db_health_check() {
    log_info "执行备份前数据库健康检查..."
    
    # 查找数据库检查工具
    local db_check_tool=""
    
    if [ -f "/app/tools/quick_db_check.py" ]; then
        db_check_tool="/app/tools/quick_db_check.py"
    elif [ -f "/app/quick_db_check.py" ]; then
        db_check_tool="/app/quick_db_check.py"
    elif [ -f "quick_db_check.py" ]; then
        db_check_tool="quick_db_check.py"
    fi
    
    if [ -n "$db_check_tool" ]; then
        if python3 "$db_check_tool" > /tmp/db_check.log 2>&1; then
            log_success "数据库健康检查通过"
            return 0
        else
            log_warning "数据库健康检查警告，继续备份"
            cat /tmp/db_check.log | tail -5
            return 1
        fi
    else
        log_warning "未找到数据库检查工具，跳过健康检查"
        return 1
    fi
}

# 创建数据库备份
create_database_backup() {
    log_info "创建数据库备份..."
    
    # 检查数据库环境变量
    if [ -z "$DB_HOST" ] || [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
        log_warning "数据库环境变量未配置，跳过数据库备份"
        return 1
    fi
    
    # 创建备份目录
    mkdir -p /tmp/backup
    
    # 使用 pg_dump 创建数据库备份
    local backup_file="/tmp/backup/database_${BACKUP_DATE}.sql"
    
    export PGPASSWORD="$DB_PASSWORD"
    
    if pg_dump -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" \
        --verbose --clean --if-exists --create > "$backup_file" 2>/tmp/pgdump.log; then
        
        # 压缩备份文件
        gzip "$backup_file"
        log_success "数据库备份创建成功: ${backup_file}.gz"
        
        # 上传到 R2
        if rclone copy "${backup_file}.gz" r2:${R2_BUCKET_NAME}/backups/${BACKUP_DATE}/database/ \
            --progress --log-level INFO; then
            log_success "数据库备份已上传到 R2"
            rm -f "${backup_file}.gz"
        else
            log_error "数据库备份上传失败"
            return 1
        fi
    else
        log_error "数据库备份创建失败"
        cat /tmp/pgdump.log | tail -5
        return 1
    fi
    
    unset PGPASSWORD
}

# 备份应用配置
backup_config() {
    log_info "备份应用配置..."
    
    local config_files=(
        "/app/.env"
        "/app/docker-compose.yml"
        "/app/pyproject.toml"
    )
    
    mkdir -p /tmp/backup/config
    
    for config_file in "${config_files[@]}"; do
        if [ -f "$config_file" ]; then
            cp "$config_file" /tmp/backup/config/
            log_info "已复制: $(basename $config_file)"
        fi
    done
    
    # 上传配置备份
    if rclone sync /tmp/backup/config r2:${R2_BUCKET_NAME}/backups/${BACKUP_DATE}/config \
        --progress --log-level INFO; then
        log_success "配置文件备份完成"
        rm -rf /tmp/backup/config
    else
        log_error "配置文件备份上传失败"
        return 1
    fi
}

# 备份日志文件
backup_logs() {
    log_info "备份日志文件..."
    
    local log_dirs=(
        "/app/logs"
    "/var/log/flowslide"
    )
    
    for log_dir in "${log_dirs[@]}"; do
        if [ -d "$log_dir" ]; then
            log_info "备份日志目录: $log_dir"
            rclone sync "$log_dir" r2:${R2_BUCKET_NAME}/backups/${BACKUP_DATE}/logs/$(basename $log_dir) \
                --progress --log-level INFO \
                --exclude "*.tmp" --exclude "*.lock" \
                --max-age 30d  # 只备份30天内的日志
        fi
    done
}

# 创建备份清单
create_backup_manifest() {
    log_info "创建备份清单..."
    
    local manifest_file="/tmp/backup_manifest_${BACKUP_DATE}.json"
    
    cat > "$manifest_file" << EOF
{
    "backup_date": "${BACKUP_DATE}",
    "backup_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "flowslide_version": "$(cat /app/VERSION 2>/dev/null || echo 'unknown')",
    "components": {
        "database": $([ -n "$DB_HOST" ] && echo "true" || echo "false"),
        "application_data": $([ -d "/app/data" ] && echo "true" || echo "false"),
        "research_reports": $([ -d "/app/research_reports" ] && echo "true" || echo "false"),
        "configuration": true,
        "logs": true
    },
    "r2_bucket": "${R2_BUCKET_NAME}",
    "backup_path": "backups/${BACKUP_DATE}/",
    "created_by": "backup_to_r2_enhanced.sh"
}
EOF
    
    # 上传清单文件
    if rclone copy "$manifest_file" r2:${R2_BUCKET_NAME}/backups/${BACKUP_DATE}/ \
        --progress --log-level INFO; then
        log_success "备份清单已创建"
        rm -f "$manifest_file"
    else
        log_error "备份清单上传失败"
    fi
}

# 清理旧备份
cleanup_old_backups() {
    log_info "清理超过30天的旧备份..."
    
    # 使用 rclone 清理30天前的备份
    local cutoff_date=$(date -d '30 days ago' +%Y%m%d)
    
    # 列出所有备份并删除旧的
    rclone lsf r2:${R2_BUCKET_NAME}/backups/ --dirs-only | while read backup_dir; do
        # 提取日期部分 (假设格式为 YYYYMMDD_HHMMSS/)
        local backup_date_part=$(echo "$backup_dir" | cut -d'_' -f1)
        
        if [[ "$backup_date_part" < "$cutoff_date" ]]; then
            log_info "删除旧备份: $backup_dir"
            rclone purge r2:${R2_BUCKET_NAME}/backups/$backup_dir
        fi
    done
    
    log_success "旧备份清理完成"
}

# 发送备份通知 (可选)
send_backup_notification() {
    if [ -n "$BACKUP_WEBHOOK_URL" ]; then
        log_info "发送备份完成通知..."
        
        local payload=$(cat << EOF
{
    "text": "FlowSlide 备份完成",
    "attachments": [
        {
            "color": "good",
            "fields": [
                {
                    "title": "备份时间",
                    "value": "${BACKUP_DATE}",
                    "short": true
                },
                {
                    "title": "备份路径",
                    "value": "backups/${BACKUP_DATE}/",
                    "short": true
                }
            ]
        }
    ]
}
EOF
)
        
        curl -X POST -H 'Content-type: application/json' \
            --data "$payload" \
            "$BACKUP_WEBHOOK_URL" || log_warning "通知发送失败"
    fi
}

# 主备份函数
main() {
    echo "🔄 开始 FlowSlide 增强版备份到 Cloudflare R2..."
    echo "备份时间: $(date)"
    echo "========================================"
    
    # 检查必要的环境变量（未配置则跳过备份并正常退出）
    if [ -z "$R2_ACCESS_KEY_ID" ] || [ -z "$R2_SECRET_ACCESS_KEY" ] || [ -z "$R2_ENDPOINT" ] || [ -z "$R2_BUCKET_NAME" ]; then
        log_warning "R2 环境变量未配置，跳过备份（此行为不会影响应用运行）"
        exit 0
    fi
    
    # 生成备份时间戳
    export BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
    
    # 配置 rclone for Cloudflare R2
    export RCLONE_CONFIG_R2_TYPE=s3
    export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
    export RCLONE_CONFIG_R2_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID
    export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY
    export RCLONE_CONFIG_R2_ENDPOINT=$R2_ENDPOINT
    
    # 检查工具
    check_rclone
    check_db_tools
    
    # 执行数据库健康检查
    run_db_health_check || log_warning "数据库健康检查未通过，继续备份"
    
    # 备份步骤
    local backup_success=true
    
    # 1. 数据库备份
    create_database_backup || {
        log_warning "数据库备份失败，继续其他备份"
        backup_success=false
    }
    
    # 2. 应用数据备份
    if [ -d "/app/data" ]; then
        log_info "📦 备份应用数据..."
        if rclone sync /app/data r2:${R2_BUCKET_NAME}/backups/${BACKUP_DATE}/data \
            --progress --log-level INFO \
            --exclude "*.tmp" --exclude "cache/**" --exclude "*.lock"; then
            log_success "应用数据备份完成"
        else
            log_error "应用数据备份失败"
            backup_success=false
        fi
    fi
    
    # 3. 研究报告备份
    if [ -d "/app/research_reports" ]; then
        log_info "📊 备份研究报告..."
        if rclone sync /app/research_reports r2:${R2_BUCKET_NAME}/backups/${BACKUP_DATE}/research_reports \
            --progress --log-level INFO; then
            log_success "研究报告备份完成"
        else
            log_error "研究报告备份失败"
            backup_success=false
        fi
    fi
    
    # 4. 配置文件备份
    backup_config || {
        log_warning "配置文件备份失败"
        backup_success=false
    }
    
    # 5. 日志备份
    backup_logs || log_warning "日志备份失败"
    
    # 6. 创建备份清单
    create_backup_manifest
    
    # 7. 清理旧备份
    cleanup_old_backups || log_warning "旧备份清理失败"
    
    # 8. 发送通知
    send_backup_notification
    
    # 总结
    echo "========================================"
    if [ "$backup_success" = true ]; then
        log_success "备份完成！备份路径: backups/${BACKUP_DATE}/"
        echo "🎉 所有组件备份成功"
    else
        log_warning "备份完成，但某些组件备份失败"
        echo "⚠️  请检查上述错误信息"
    fi
    
    echo "备份结束时间: $(date)"
    
    # 清理临时文件
    rm -rf /tmp/backup
    rm -f /tmp/db_check.log /tmp/pgdump.log
}

# 执行主函数
main "$@"
