#!/bin/bash
# LandPPT R2 备份恢复脚本

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
    echo "LandPPT R2 备份恢复脚本"
    echo ""
    echo "用法:"
    echo "  $0 [选项] <备份日期>"
    echo ""
    echo "参数:"
    echo "  <备份日期>        要恢复的备份日期 (格式: YYYYMMDD_HHMMSS)"
    echo ""
    echo "选项:"
    echo "  -d, --database    只恢复数据库"
    echo "  -f, --files       只恢复文件"
    echo "  -c, --config      只恢复配置"
    echo "  -l, --list        列出可用的备份"
    echo "  -i, --info        显示备份信息"
    echo "  -y, --yes         自动确认所有操作"
    echo "  -h, --help        显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -l                           # 列出所有备份"
    echo "  $0 -i 20250813_020000           # 显示指定备份的信息"
    echo "  $0 20250813_020000              # 恢复完整备份"
    echo "  $0 -d 20250813_020000           # 只恢复数据库"
    echo "  $0 -f 20250813_020000           # 只恢复文件"
    echo ""
    echo "注意:"
    echo "  - 恢复操作会覆盖现有数据，请谨慎操作"
    echo "  - 建议在恢复前创建当前数据的备份"
    echo "  - 确保 R2 环境变量已正确配置"
}

# 检查必要的环境变量
check_r2_config() {
    if [ -z "$R2_ACCESS_KEY_ID" ] || [ -z "$R2_SECRET_ACCESS_KEY" ] || [ -z "$R2_ENDPOINT" ] || [ -z "$R2_BUCKET_NAME" ]; then
        log_error "R2 环境变量未完整配置"
        log_info "需要配置: R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET_NAME"
        exit 1
    fi
    
    # 配置 rclone for Cloudflare R2
    export RCLONE_CONFIG_R2_TYPE=s3
    export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
    export RCLONE_CONFIG_R2_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID
    export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY
    export RCLONE_CONFIG_R2_ENDPOINT=$R2_ENDPOINT
    
    log_success "R2 配置已加载"
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

# 列出可用备份
list_backups() {
    log_header "可用备份列表"
    
    log_info "从 R2 获取备份列表..."
    
    local backups=$(rclone lsf r2:${R2_BUCKET_NAME}/backups/ --dirs-only | sort -r)
    
    if [ -z "$backups" ]; then
        log_warning "未找到任何备份"
        return 1
    fi
    
    echo ""
    echo "格式: [备份日期] [大小] [组件]"
    echo "----------------------------------------"
    
    while IFS= read -r backup_dir; do
        if [ -n "$backup_dir" ]; then
            local backup_date=${backup_dir%/}
            local backup_path="r2:${R2_BUCKET_NAME}/backups/${backup_dir}"
            
            # 获取备份大小
            local size=$(rclone size "$backup_path" --json 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    bytes_size = data.get('bytes', 0)
    if bytes_size > 1024*1024*1024:
        print(f'{bytes_size/(1024*1024*1024):.1f}GB')
    elif bytes_size > 1024*1024:
        print(f'{bytes_size/(1024*1024):.1f}MB')
    else:
        print(f'{bytes_size/1024:.1f}KB')
except:
    print('未知')
" 2>/dev/null || echo "未知")
            
            # 检查备份组件
            local components=()
            if rclone lsf "$backup_path" | grep -q "database/"; then
                components+=("数据库")
            fi
            if rclone lsf "$backup_path" | grep -q "data/"; then
                components+=("应用数据")
            fi
            if rclone lsf "$backup_path" | grep -q "research_reports/"; then
                components+=("研究报告")
            fi
            if rclone lsf "$backup_path" | grep -q "config/"; then
                components+=("配置")
            fi
            if rclone lsf "$backup_path" | grep -q "logs/"; then
                components+=("日志")
            fi
            
            local component_list=$(IFS=,; echo "${components[*]}")
            echo "📦 $backup_date  [$size]  [$component_list]"
        fi
    done <<< "$backups"
    
    echo ""
    log_info "使用 '$0 -i <备份日期>' 查看详细信息"
}

# 显示备份信息
show_backup_info() {
    local backup_date="$1"
    
    if [ -z "$backup_date" ]; then
        log_error "请指定备份日期"
        return 1
    fi
    
    log_header "备份信息: $backup_date"
    
    local backup_path="r2:${R2_BUCKET_NAME}/backups/${backup_date}/"
    
    # 检查备份是否存在
    if ! rclone lsf "$backup_path" > /dev/null 2>&1; then
        log_error "备份 $backup_date 不存在"
        return 1
    fi
    
    echo ""
    echo "备份路径: $backup_path"
    echo ""
    
    # 显示备份清单
    local manifest_file="backup_manifest_${backup_date}.json"
    if rclone lsf "$backup_path" | grep -q "$manifest_file"; then
        log_info "备份清单:"
        rclone cat "${backup_path}${manifest_file}" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(f\"  备份时间: {data.get('backup_timestamp', '未知')}\")
    print(f\"  LandPPT 版本: {data.get('landppt_version', '未知')}\")
    print(f\"  R2 存储桶: {data.get('r2_bucket', '未知')}\")
    
    components = data.get('components', {})
    print('  包含组件:')
    for comp, enabled in components.items():
        status = '✅' if enabled else '❌'
        print(f'    {status} {comp}')
except:
    print('  无法解析备份清单')
"
    fi
    
    echo ""
    log_info "备份内容:"
    
    # 显示目录结构
    local dirs=$(rclone lsf "$backup_path" --dirs-only)
    while IFS= read -r dir; do
        if [ -n "$dir" ]; then
            local dir_name=${dir%/}
            local dir_size=$(rclone size "${backup_path}${dir}" --json 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    bytes_size = data.get('bytes', 0)
    if bytes_size > 1024*1024*1024:
        print(f'{bytes_size/(1024*1024*1024):.1f}GB')
    elif bytes_size > 1024*1024:
        print(f'{bytes_size/(1024*1024):.1f}MB')
    else:
        print(f'{bytes_size/1024:.1f}KB')
except:
    print('未知')
" 2>/dev/null || echo "未知")
            
            echo "  📁 $dir_name ($dir_size)"
            
            # 显示子目录文件数量
            local file_count=$(rclone lsf "${backup_path}${dir}" --files-only | wc -l)
            if [ "$file_count" -gt 0 ]; then
                echo "     └─ $file_count 个文件"
            fi
        fi
    done <<< "$dirs"
}

# 确认恢复操作
confirm_restore() {
    local backup_date="$1"
    local restore_type="$2"
    
    if [ "$AUTO_CONFIRM" = "true" ]; then
        return 0
    fi
    
    echo ""
    log_warning "⚠️  警告：恢复操作将覆盖现有数据！"
    echo ""
    echo "备份日期: $backup_date"
    echo "恢复类型: $restore_type"
    echo ""
    echo "建议在继续前:"
    echo "1. 停止 LandPPT 服务"
    echo "2. 创建当前数据的备份"
    echo "3. 确认要恢复的备份数据正确"
    echo ""
    
    read -p "确定要继续吗？(输入 'yes' 确认): " confirmation
    
    if [ "$confirmation" != "yes" ]; then
        log_info "恢复操作已取消"
        exit 0
    fi
}

# 恢复数据库
restore_database() {
    local backup_date="$1"
    
    log_header "恢复数据库: $backup_date"
    
    local backup_path="r2:${R2_BUCKET_NAME}/backups/${backup_date}/database/"
    
    # 检查数据库备份是否存在
    local db_files=$(rclone lsf "$backup_path" --files-only | grep "\.sql\.gz$")
    
    if [ -z "$db_files" ]; then
        log_error "备份中未找到数据库文件"
        return 1
    fi
    
    local db_file=$(echo "$db_files" | head -1)
    log_info "找到数据库备份文件: $db_file"
    
    # 检查数据库环境变量
    if [ -z "$DB_HOST" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
        log_error "数据库环境变量未配置"
        return 1
    fi
    
    # 创建临时目录
    local temp_dir="/tmp/restore_$$"
    mkdir -p "$temp_dir"
    
    # 下载数据库备份文件
    log_info "下载数据库备份文件..."
    if ! rclone copy "${backup_path}${db_file}" "$temp_dir/"; then
        log_error "数据库备份文件下载失败"
        rm -rf "$temp_dir"
        return 1
    fi
    
    # 解压备份文件
    log_info "解压数据库备份..."
    gunzip "${temp_dir}/${db_file}"
    local sql_file="${temp_dir}/${db_file%.gz}"
    
    # 恢复数据库
    log_info "恢复数据库..."
    export PGPASSWORD="$DB_PASSWORD"
    
    if psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "${DB_NAME:-postgres}" \
        -f "$sql_file" > "${temp_dir}/restore.log" 2>&1; then
        log_success "数据库恢复成功"
    else
        log_error "数据库恢复失败"
        echo "错误日志:"
        cat "${temp_dir}/restore.log" | tail -10
        rm -rf "$temp_dir"
        return 1
    fi
    
    unset PGPASSWORD
    rm -rf "$temp_dir"
}

# 恢复文件
restore_files() {
    local backup_date="$1"
    
    log_header "恢复文件: $backup_date"
    
    local backup_path="r2:${R2_BUCKET_NAME}/backups/${backup_date}/"
    
    # 恢复应用数据
    if rclone lsf "$backup_path" | grep -q "data/"; then
        log_info "恢复应用数据..."
        
        # 备份现有数据
        if [ -d "/app/data" ]; then
            local backup_existing="/tmp/data_backup_$(date +%s)"
            cp -r /app/data "$backup_existing"
            log_info "现有数据已备份到: $backup_existing"
        fi
        
        mkdir -p /app/data
        if rclone sync "${backup_path}data/" /app/data --progress; then
            log_success "应用数据恢复成功"
        else
            log_error "应用数据恢复失败"
            return 1
        fi
    fi
    
    # 恢复研究报告
    if rclone lsf "$backup_path" | grep -q "research_reports/"; then
        log_info "恢复研究报告..."
        
        # 备份现有报告
        if [ -d "/app/research_reports" ]; then
            local backup_existing="/tmp/reports_backup_$(date +%s)"
            cp -r /app/research_reports "$backup_existing"
            log_info "现有报告已备份到: $backup_existing"
        fi
        
        mkdir -p /app/research_reports
        if rclone sync "${backup_path}research_reports/" /app/research_reports --progress; then
            log_success "研究报告恢复成功"
        else
            log_error "研究报告恢复失败"
            return 1
        fi
    fi
}

# 恢复配置
restore_config() {
    local backup_date="$1"
    
    log_header "恢复配置: $backup_date"
    
    local backup_path="r2:${R2_BUCKET_NAME}/backups/${backup_date}/config/"
    
    # 检查配置备份是否存在
    if ! rclone lsf "$backup_path" > /dev/null 2>&1; then
        log_warning "备份中未找到配置文件"
        return 1
    fi
    
    # 创建临时目录
    local temp_dir="/tmp/config_restore_$$"
    mkdir -p "$temp_dir"
    
    # 下载配置文件
    log_info "下载配置文件..."
    if ! rclone sync "$backup_path" "$temp_dir/"; then
        log_error "配置文件下载失败"
        rm -rf "$temp_dir"
        return 1
    fi
    
    # 恢复配置文件
    log_info "恢复配置文件..."
    
    local config_files=(".env" "docker-compose.yml" "pyproject.toml")
    
    for config_file in "${config_files[@]}"; do
        if [ -f "${temp_dir}/${config_file}" ]; then
            # 备份现有配置
            if [ -f "/app/${config_file}" ]; then
                cp "/app/${config_file}" "/app/${config_file}.backup.$(date +%s)"
            fi
            
            # 恢复配置
            cp "${temp_dir}/${config_file}" "/app/"
            log_info "已恢复: $config_file"
        fi
    done
    
    rm -rf "$temp_dir"
    log_success "配置文件恢复完成"
}

# 主恢复函数
perform_restore() {
    local backup_date="$1"
    local restore_database="$2"
    local restore_files="$3"
    local restore_config="$4"
    
    # 验证备份存在
    local backup_path="r2:${R2_BUCKET_NAME}/backups/${backup_date}/"
    if ! rclone lsf "$backup_path" > /dev/null 2>&1; then
        log_error "备份 $backup_date 不存在"
        return 1
    fi
    
    local restore_type="完整恢复"
    if [ "$restore_database" = "true" ] && [ "$restore_files" = "false" ] && [ "$restore_config" = "false" ]; then
        restore_type="数据库恢复"
    elif [ "$restore_database" = "false" ] && [ "$restore_files" = "true" ] && [ "$restore_config" = "false" ]; then
        restore_type="文件恢复"
    elif [ "$restore_database" = "false" ] && [ "$restore_files" = "false" ] && [ "$restore_config" = "true" ]; then
        restore_type="配置恢复"
    fi
    
    # 确认恢复操作
    confirm_restore "$backup_date" "$restore_type"
    
    echo ""
    log_header "开始恢复操作"
    echo "备份日期: $backup_date"
    echo "恢复时间: $(date)"
    echo "========================================"
    
    local restore_success=true
    
    # 执行恢复操作
    if [ "$restore_database" = "true" ]; then
        if ! restore_database "$backup_date"; then
            restore_success=false
        fi
    fi
    
    if [ "$restore_files" = "true" ]; then
        if ! restore_files "$backup_date"; then
            restore_success=false
        fi
    fi
    
    if [ "$restore_config" = "true" ]; then
        if ! restore_config "$backup_date"; then
            restore_success=false
        fi
    fi
    
    # 总结
    echo "========================================"
    if [ "$restore_success" = "true" ]; then
        log_success "恢复完成！"
        echo ""
        log_info "下一步:"
        echo "1. 检查恢复的数据是否正确"
        echo "2. 重启 LandPPT 服务"
        echo "3. 执行健康检查验证系统状态"
    else
        log_error "恢复过程中出现错误"
        echo ""
        log_info "建议:"
        echo "1. 检查错误日志"
        echo "2. 验证环境配置"
        echo "3. 如需要，从备份文件手动恢复"
    fi
    
    echo "恢复结束时间: $(date)"
}

# 主函数
main() {
    local backup_date=""
    local restore_database="true"
    local restore_files="true"
    local restore_config="true"
    local list_backups_only=false
    local show_info_only=false
    export AUTO_CONFIRM=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--database)
                restore_database="true"
                restore_files="false"
                restore_config="false"
                shift
                ;;
            -f|--files)
                restore_database="false"
                restore_files="true"
                restore_config="false"
                shift
                ;;
            -c|--config)
                restore_database="false"
                restore_files="false"
                restore_config="true"
                shift
                ;;
            -l|--list)
                list_backups_only=true
                shift
                ;;
            -i|--info)
                show_info_only=true
                shift
                ;;
            -y|--yes)
                AUTO_CONFIRM=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -*)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
            *)
                backup_date="$1"
                shift
                ;;
        esac
    done
    
    # 加载环境变量
    if [ -f ".env" ]; then
        source .env
    fi
    
    # 检查工具和配置
    check_rclone
    check_r2_config
    
    # 执行相应操作
    if [ "$list_backups_only" = "true" ]; then
        list_backups
    elif [ "$show_info_only" = "true" ]; then
        if [ -z "$backup_date" ]; then
            log_error "请指定要查看的备份日期"
            exit 1
        fi
        show_backup_info "$backup_date"
    else
        if [ -z "$backup_date" ]; then
            log_error "请指定要恢复的备份日期"
            show_help
            exit 1
        fi
        perform_restore "$backup_date" "$restore_database" "$restore_files" "$restore_config"
    fi
}

# 执行主函数
main "$@"
