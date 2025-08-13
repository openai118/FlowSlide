#!/bin/bash
# LandPPT 备份管理脚本

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

# 显示使用帮助
show_help() {
    echo "LandPPT 备份管理脚本"
    echo ""
    echo "用法:"
    echo "  $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  start-scheduler    启动定时备份服务"
    echo "  stop-scheduler     停止定时备份服务"
    echo "  status            查看备份服务状态"
    echo "  run-backup        立即执行一次备份"
    echo "  list-backups      列出现有备份"
    echo "  restore           恢复备份（交互式）"
    echo "  cleanup           清理旧备份"
    echo "  test-config       测试备份配置"
    echo "  logs              查看备份日志"
    echo ""
    echo "选项:"
    echo "  -h, --help        显示此帮助信息"
    echo "  -v, --verbose     详细输出"
    echo ""
    echo "示例:"
    echo "  $0 start-scheduler              # 启动定时备份"
    echo "  $0 run-backup                   # 立即备份"
    echo "  $0 list-backups                 # 查看备份列表"
    echo "  $0 test-config                  # 测试配置"
}

# 检查依赖
check_dependencies() {
    local deps=("docker" "docker-compose")
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            log_error "$dep 未安装或不在 PATH 中"
            exit 1
        fi
    done
    
    log_success "依赖检查通过"
}

# 检查环境变量
check_env_vars() {
    local required_vars=(
        "R2_ACCESS_KEY_ID"
        "R2_SECRET_ACCESS_KEY" 
        "R2_ENDPOINT"
        "R2_BUCKET_NAME"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_error "缺少必要的环境变量:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        log_info "请在 .env 文件中设置这些变量"
        return 1
    fi
    
    log_success "环境变量检查通过"
    return 0
}

# 启动定时备份服务
start_scheduler() {
    log_header "启动定时备份服务"
    
    # 检查是否已经运行
    if docker-compose -f docker-compose.backup.yml ps | grep -q "backup-scheduler.*Up"; then
        log_warning "备份调度器已经在运行"
        return 0
    fi
    
    log_info "启动备份调度器..."
    docker-compose -f docker-compose.backup.yml up -d backup-scheduler
    
    # 等待服务启动
    sleep 5
    
    if docker-compose -f docker-compose.backup.yml ps | grep -q "backup-scheduler.*Up"; then
        log_success "备份调度器启动成功"
        
        # 显示调度信息
        local schedule="${BACKUP_SCHEDULE:-0 2 * * *}"
        log_info "备份调度: $schedule (cron 格式)"
        log_info "数据保留: ${BACKUP_RETENTION_DAYS:-30} 天"
    else
        log_error "备份调度器启动失败"
        docker-compose -f docker-compose.backup.yml logs backup-scheduler
        return 1
    fi
}

# 停止定时备份服务
stop_scheduler() {
    log_header "停止定时备份服务"
    
    if ! docker-compose -f docker-compose.backup.yml ps | grep -q "backup-scheduler"; then
        log_warning "备份调度器未运行"
        return 0
    fi
    
    log_info "停止备份调度器..."
    docker-compose -f docker-compose.backup.yml stop backup-scheduler
    docker-compose -f docker-compose.backup.yml rm -f backup-scheduler
    
    log_success "备份调度器已停止"
}

# 查看服务状态
show_status() {
    log_header "备份服务状态"
    
    echo ""
    echo "Docker Compose 服务状态:"
    docker-compose -f docker-compose.backup.yml ps
    
    echo ""
    echo "备份调度器状态:"
    if docker-compose -f docker-compose.backup.yml ps | grep -q "backup-scheduler.*Up"; then
        log_success "备份调度器正在运行"
        
        # 显示下次备份时间
        local schedule="${BACKUP_SCHEDULE:-0 2 * * *}"
        echo "  调度设置: $schedule"
        echo "  保留天数: ${BACKUP_RETENTION_DAYS:-30} 天"
    else
        log_warning "备份调度器未运行"
    fi
    
    echo ""
    echo "磁盘使用情况:"
    docker system df
}

# 执行立即备份
run_backup() {
    log_header "执行立即备份"
    
    log_info "启动备份容器..."
    docker-compose -f docker-compose.backup.yml run --rm manual-backup
    
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        log_success "备份完成"
    else
        log_error "备份失败 (退出码: $exit_code)"
        return $exit_code
    fi
}

# 列出现有备份
list_backups() {
    log_header "现有备份列表"
    
    if ! check_env_vars > /dev/null 2>&1; then
        log_error "无法列出备份：R2 配置不完整"
        return 1
    fi
    
    log_info "连接到 R2 存储..."
    
    # 使用临时容器执行 rclone 命令
    docker run --rm \
        -e RCLONE_CONFIG_R2_TYPE=s3 \
        -e RCLONE_CONFIG_R2_PROVIDER=Cloudflare \
        -e RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
        -e RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
        -e RCLONE_CONFIG_R2_ENDPOINT="$R2_ENDPOINT" \
        rclone/rclone:latest \
        lsd r2:${R2_BUCKET_NAME}/backups/ || {
        log_error "无法列出备份，请检查 R2 配置"
        return 1
    }
}

# 测试备份配置
test_config() {
    log_header "测试备份配置"
    
    echo ""
    log_info "检查 Docker 和 Docker Compose..."
    check_dependencies
    
    echo ""
    log_info "检查环境变量..."
    if check_env_vars; then
        echo "✅ R2_ACCESS_KEY_ID: $(echo ${R2_ACCESS_KEY_ID:0:8}...)"
        echo "✅ R2_SECRET_ACCESS_KEY: $(echo ${R2_SECRET_ACCESS_KEY:0:8}...)"
        echo "✅ R2_ENDPOINT: $R2_ENDPOINT"
        echo "✅ R2_BUCKET_NAME: $R2_BUCKET_NAME"
        
        if [ -n "$BACKUP_WEBHOOK_URL" ]; then
            echo "✅ BACKUP_WEBHOOK_URL: 已配置"
        else
            echo "ℹ️  BACKUP_WEBHOOK_URL: 未配置 (可选)"
        fi
    fi
    
    echo ""
    log_info "测试 R2 连接..."
    if docker run --rm \
        -e RCLONE_CONFIG_R2_TYPE=s3 \
        -e RCLONE_CONFIG_R2_PROVIDER=Cloudflare \
        -e RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
        -e RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
        -e RCLONE_CONFIG_R2_ENDPOINT="$R2_ENDPOINT" \
        rclone/rclone:latest \
        lsd r2:${R2_BUCKET_NAME}/ > /dev/null 2>&1; then
        log_success "R2 连接测试成功"
    else
        log_error "R2 连接测试失败"
        return 1
    fi
    
    echo ""
    log_info "检查数据库配置..."
    if [ -n "$DB_HOST" ] && [ -n "$DB_USER" ]; then
        echo "✅ 数据库配置存在"
        echo "  主机: $DB_HOST"
        echo "  用户: $DB_USER"
        echo "  数据库: ${DB_NAME:-postgres}"
    else
        log_warning "数据库配置不完整，数据库备份将被跳过"
    fi
    
    echo ""
    log_success "配置测试完成"
}

# 查看备份日志
show_logs() {
    log_header "备份日志"
    
    echo ""
    echo "备份调度器日志:"
    docker-compose -f docker-compose.backup.yml logs --tail=50 backup-scheduler 2>/dev/null || {
        log_warning "备份调度器未运行，无法显示日志"
    }
    
    echo ""
    echo "最近的手动备份日志:"
    docker-compose -f docker-compose.backup.yml logs --tail=20 manual-backup 2>/dev/null || {
        log_info "暂无手动备份日志"
    }
}

# 清理旧备份
cleanup_backups() {
    log_header "清理旧备份"
    
    local retention_days="${BACKUP_RETENTION_DAYS:-30}"
    
    log_info "清理 $retention_days 天前的备份..."
    
    # 使用备份脚本的清理功能
    docker-compose -f docker-compose.backup.yml run --rm manual-backup bash -c "
        export BACKUP_DATE=\$(date +%Y%m%d_%H%M%S)
        
        # 配置 rclone
        export RCLONE_CONFIG_R2_TYPE=s3
        export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
        export RCLONE_CONFIG_R2_ACCESS_KEY_ID=\$R2_ACCESS_KEY_ID
        export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=\$R2_SECRET_ACCESS_KEY
        export RCLONE_CONFIG_R2_ENDPOINT=\$R2_ENDPOINT
        
        # 清理旧备份
        cutoff_date=\$(date -d '$retention_days days ago' +%Y%m%d)
        echo \"清理 \$cutoff_date 之前的备份...\"
        
        rclone lsf r2:\${R2_BUCKET_NAME}/backups/ --dirs-only | while read backup_dir; do
            backup_date_part=\$(echo \"\$backup_dir\" | cut -d'_' -f1)
            if [[ \"\$backup_date_part\" < \"\$cutoff_date\" ]]; then
                echo \"删除旧备份: \$backup_dir\"
                rclone purge r2:\${R2_BUCKET_NAME}/backups/\$backup_dir
            fi
        done
        
        echo \"清理完成\"
    "
    
    log_success "旧备份清理完成"
}

# 主函数
main() {
    case "${1:-}" in
        "start-scheduler")
            check_dependencies
            start_scheduler
            ;;
        "stop-scheduler")
            check_dependencies
            stop_scheduler
            ;;
        "status")
            check_dependencies
            show_status
            ;;
        "run-backup")
            check_dependencies
            run_backup
            ;;
        "list-backups")
            list_backups
            ;;
        "test-config")
            test_config
            ;;
        "logs")
            check_dependencies
            show_logs
            ;;
        "cleanup")
            check_dependencies
            cleanup_backups
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        "")
            log_error "请指定一个命令"
            echo ""
            show_help
            exit 1
            ;;
        *)
            log_error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 加载环境变量
if [ -f ".env" ]; then
    source .env
fi

# 执行主函数
main "$@"
