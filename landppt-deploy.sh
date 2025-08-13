#!/bin/bash

# LandPPT Docker 部署和管理脚本

set -e

# 颜色代码
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# 日志函数
log() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] ${message}${NC}"
}

# 显示帮助信息
show_help() {
    echo "LandPPT Docker 部署和管理脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  build                 构建 Docker 镜像"
    echo "  start                 启动服务"
    echo "  stop                  停止服务"
    echo "  restart               重启服务"
    echo "  logs                  查看日志"
    echo "  status                查看服务状态"
    echo "  db-check             运行数据库健康检查"
    echo "  db-test              运行数据库压力测试"
    echo "  cleanup              清理未使用的 Docker 资源"
    echo "  update               更新并重启服务"
    echo "  backup               备份数据"
    echo "  restore [file]       恢复数据"
    echo "  monitor              启动监控服务"
    echo "  help                 显示此帮助信息"
    echo ""
}

# 检查必要的文件
check_prerequisites() {
    log $BLUE "检查必要文件..."
    
    required_files=(
        "Dockerfile.enhanced"
        "docker-compose.yml"
        "docker-healthcheck-enhanced.sh"
        "docker-entrypoint-enhanced.sh"
        "database_health_check.py"
        "quick_db_check.py"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log $RED "缺少必要文件: $file"
            return 1
        fi
    done
    
    log $GREEN "所有必要文件已就绪"
}

# 构建镜像
build_image() {
    log $BLUE "构建 LandPPT Docker 镜像..."
    
    if ! check_prerequisites; then
        exit 1
    fi
    
    # 确保脚本可执行
    chmod +x docker-healthcheck-enhanced.sh docker-entrypoint-enhanced.sh
    
    docker-compose build --no-cache
    
    log $GREEN "镜像构建完成"
}

# 启动服务
start_services() {
    log $BLUE "启动 LandPPT 服务..."
    
    if ! check_prerequisites; then
        exit 1
    fi
    
    # 运行数据库预检查
    log $BLUE "执行数据库预检查..."
    if python3 quick_db_check.py; then
        log $GREEN "数据库预检查通过"
    else
        log $YELLOW "数据库预检查失败，但继续启动服务"
    fi
    
    docker-compose up -d
    
    log $GREEN "服务启动完成"
    log $BLUE "等待服务就绪..."
    
    # 等待健康检查通过
    max_wait=180
    wait_time=0
    while [ $wait_time -lt $max_wait ]; do
        if docker-compose ps | grep -q "healthy"; then
            log $GREEN "服务健康检查通过"
            break
        fi
        sleep 5
        wait_time=$((wait_time + 5))
        log $YELLOW "等待健康检查通过... (${wait_time}/${max_wait}s)"
    done
    
    if [ $wait_time -ge $max_wait ]; then
        log $RED "服务启动超时，请检查日志"
        docker-compose logs --tail=50
        return 1
    fi
    
    log $GREEN "LandPPT 服务已就绪！"
    log $BLUE "访问地址: http://localhost:8000"
}

# 停止服务
stop_services() {
    log $BLUE "停止 LandPPT 服务..."
    docker-compose down
    log $GREEN "服务已停止"
}

# 重启服务
restart_services() {
    log $BLUE "重启 LandPPT 服务..."
    stop_services
    start_services
}

# 查看日志
view_logs() {
    log $BLUE "查看服务日志..."
    docker-compose logs -f --tail=100
}

# 查看状态
check_status() {
    log $BLUE "检查服务状态..."
    
    echo ""
    echo "=== Docker Compose 服务状态 ==="
    docker-compose ps
    
    echo ""
    echo "=== 容器资源使用情况 ==="
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
    
    echo ""
    echo "=== 卷使用情况 ==="
    docker volume ls | grep landppt
    
    # 检查数据库连接
    echo ""
    echo "=== 数据库连接状态 ==="
    if docker-compose exec -T landppt python3 /app/tools/quick_db_check.py 2>/dev/null; then
        log $GREEN "数据库连接正常"
    else
        log $RED "数据库连接异常"
    fi
}

# 数据库健康检查
run_db_check() {
    log $BLUE "运行数据库健康检查..."
    
    if [ -f "database_health_check.py" ]; then
        python3 database_health_check.py
    else
        log $RED "数据库健康检查工具不存在"
        return 1
    fi
}

# 数据库压力测试
run_db_test() {
    log $BLUE "运行数据库压力测试..."
    
    if [ -f "simple_performance_test.py" ]; then
        python3 simple_performance_test.py
    else
        log $RED "数据库压力测试工具不存在"
        return 1
    fi
}

# 清理 Docker 资源
cleanup_docker() {
    log $BLUE "清理 Docker 资源..."
    
    # 停止服务
    docker-compose down
    
    # 清理未使用的镜像
    docker image prune -f
    
    # 清理未使用的卷（谨慎操作）
    read -p "是否清理未使用的 Docker 卷？这将删除所有未使用的数据 (y/N): " confirm
    if [[ $confirm =~ ^[Yy]$ ]]; then
        docker volume prune -f
        log $YELLOW "Docker 卷已清理"
    fi
    
    # 清理未使用的网络
    docker network prune -f
    
    log $GREEN "Docker 资源清理完成"
}

# 更新服务
update_services() {
    log $BLUE "更新 LandPPT 服务..."
    
    # 备份当前数据
    backup_data
    
    # 重新构建并启动
    build_image
    restart_services
    
    log $GREEN "服务更新完成"
}

# 备份数据
backup_data() {
    log $BLUE "备份数据..."
    
    backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    # 备份 Docker 卷
    docker run --rm -v landppt_data:/data -v landppt_uploads:/uploads -v "$(pwd)/$backup_dir":/backup alpine tar czf /backup/landppt_data.tar.gz -C / data uploads
    
    # 运行数据库检查并保存报告
    if python3 database_health_check.py --non-interactive > "$backup_dir/db_health_report.txt" 2>&1; then
        log $GREEN "数据库健康报告已保存"
    fi
    
    log $GREEN "数据备份完成: $backup_dir"
}

# 恢复数据
restore_data() {
    local backup_file=$1
    
    if [ -z "$backup_file" ]; then
        log $RED "请指定备份文件"
        return 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log $RED "备份文件不存在: $backup_file"
        return 1
    fi
    
    log $BLUE "恢复数据: $backup_file"
    
    # 停止服务
    stop_services
    
    # 恢复数据
    docker run --rm -v landppt_data:/data -v landppt_uploads:/uploads -v "$(pwd)":/backup alpine tar xzf "/backup/$backup_file" -C /
    
    # 启动服务
    start_services
    
    log $GREEN "数据恢复完成"
}

# 启动监控服务
start_monitoring() {
    log $BLUE "启动监控服务..."
    docker-compose --profile monitoring up -d db-monitor
    log $GREEN "监控服务已启动"
}

# 主函数
main() {
    case "${1:-help}" in
        build)
            build_image
            ;;
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            view_logs
            ;;
        status)
            check_status
            ;;
        db-check)
            run_db_check
            ;;
        db-test)
            run_db_test
            ;;
        cleanup)
            cleanup_docker
            ;;
        update)
            update_services
            ;;
        backup)
            backup_data
            ;;
        restore)
            restore_data "$2"
            ;;
        monitor)
            start_monitoring
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log $RED "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
}

# 检查是否安装了 Docker 和 Docker Compose
if ! command -v docker &> /dev/null; then
    log $RED "Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log $RED "Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 执行主函数
main "$@"
