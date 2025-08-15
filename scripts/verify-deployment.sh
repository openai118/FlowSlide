#!/bin/bash

# FlowSlide 部署状态检查脚本
# 用于验证 Docker Hub 镜像是否可用并测试运行

set -e

echo "🚀 FlowSlide 部署状态检查"
echo "========================="

# 配置
DOCKER_IMAGE="openai118/flowslide:latest"
TEST_PORT="8000"
CONTAINER_NAME="flowslide-test"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Docker 是否已安装
check_docker() {
    print_status "检查 Docker 环境..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    print_success "Docker 已安装"
}

# 拉取最新镜像
pull_image() {
    print_status "拉取最新的 FlowSlide 镜像..."
    if docker pull "$DOCKER_IMAGE"; then
        print_success "镜像拉取成功"
    else
        print_error "镜像拉取失败"
        exit 1
    fi
}

# 清理现有容器
cleanup_existing() {
    print_status "清理现有测试容器..."
    if docker ps -a --format 'table {{.Names}}' | grep -q "$CONTAINER_NAME"; then
        docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
        docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
        print_success "清理完成"
    else
        print_status "无需清理"
    fi
}

# 启动测试容器
start_container() {
    print_status "启动测试容器..."
    
    if docker run -d \
        --name "$CONTAINER_NAME" \
        -p "$TEST_PORT:8000" \
        -e DATABASE_URL="sqlite:///app/data/flowslide.db" \
        "$DOCKER_IMAGE"; then
        print_success "容器启动成功"
    else
        print_error "容器启动失败"
        exit 1
    fi
}

# 等待服务启动
wait_for_service() {
    print_status "等待服务启动..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:$TEST_PORT/health" >/dev/null 2>&1; then
            print_success "服务已启动并响应"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_error "服务启动超时"
    print_status "查看容器日志:"
    docker logs "$CONTAINER_NAME"
    return 1
}

# 测试基本功能
test_endpoints() {
    print_status "测试基本端点..."
    
    # 测试健康检查
    if curl -s "http://localhost:$TEST_PORT/health" | grep -q "ok"; then
        print_success "健康检查端点正常"
    else
        print_warning "健康检查端点异常"
    fi
    
    # 测试主页
    if curl -s "http://localhost:$TEST_PORT/" >/dev/null; then
        print_success "主页端点正常"
    else
        print_warning "主页端点异常"
    fi
    
    # 测试API文档
    if curl -s "http://localhost:$TEST_PORT/docs" >/dev/null; then
        print_success "API文档端点正常"
    else
        print_warning "API文档端点异常"
    fi
}

# 显示部署信息
show_deployment_info() {
    print_status "部署信息:"
    echo "- 镜像: $DOCKER_IMAGE"
    echo "- 本地访问: http://localhost:$TEST_PORT"
    echo "- 容器名称: $CONTAINER_NAME"
    echo "- 容器状态: $(docker ps --format 'table {{.Status}}' --filter name=$CONTAINER_NAME | tail -n 1)"
    
    print_status "容器资源使用:"
    docker stats "$CONTAINER_NAME" --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
}

# 清理测试环境
cleanup() {
    print_status "清理测试环境..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    print_success "清理完成"
}

# 主函数
main() {
    echo "开始部署验证流程..."
    
    check_docker
    pull_image
    cleanup_existing
    start_container
    
    if wait_for_service; then
        test_endpoints
        show_deployment_info
        
        echo ""
        print_success "✅ FlowSlide 部署验证成功!"
        print_status "服务现在可以通过 http://localhost:$TEST_PORT 访问"
        print_status "按 Ctrl+C 停止测试，或运行以下命令清理："
        echo "docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
        
        # 保持容器运行以便手动测试
        echo ""
        print_status "容器将继续运行以便手动测试..."
        print_status "按任意键停止并清理测试环境"
        read -n 1 -s
        cleanup
    else
        print_error "❌ FlowSlide 部署验证失败"
        cleanup
        exit 1
    fi
}

# 捕获中断信号
trap cleanup SIGINT SIGTERM

# 运行主函数
main
