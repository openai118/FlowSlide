# LandPPT 本地构建和部署脚本

param(
    [switch]$Build = $false,
    [switch]$Run = $false,
    [switch]$Stop = $false,
    [switch]$Status = $false,
    [switch]$Logs = $false,
    [switch]$Clean = $false
)

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Write-Info { param([string]$msg) Write-ColorOutput "ℹ️  $msg" "Blue" }
function Write-Success { param([string]$msg) Write-ColorOutput "✅ $msg" "Green" }
function Write-Warning { param([string]$msg) Write-ColorOutput "⚠️  $msg" "Yellow" }
function Write-Error { param([string]$msg) Write-ColorOutput "❌ $msg" "Red" }
function Write-Header { param([string]$msg) Write-ColorOutput "🎯 $msg" "Magenta" }

# 检查 Docker 是否可用
function Test-Docker {
    try {
        $null = docker --version
        Write-Success "Docker 可用"
        return $true
    } catch {
        Write-Error "Docker 不可用，请安装 Docker Desktop"
        return $false
    }
}

# 构建镜像
function Build-Image {
    Write-Header "构建 LandPPT 镜像"
    
    Write-Info "开始构建镜像..."
    docker build -t landppt-integrated:latest .
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "镜像构建成功"
        
        # 显示镜像信息
        Write-Info "镜像信息:"
        docker images landppt-integrated:latest
    } else {
        Write-Error "镜像构建失败"
        exit 1
    }
}

# 启动服务
function Start-Service {
    Write-Header "启动 LandPPT 服务"
    
    # 检查是否已经在运行
    $running = docker-compose ps | Select-String "landppt-app.*Up"
    if ($running) {
        Write-Warning "服务已经在运行"
        return
    }
    
    Write-Info "启动服务..."
    docker-compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "服务启动成功"
        
        # 等待服务就绪
        Write-Info "等待服务就绪..."
        Start-Sleep -Seconds 10
        
        # 显示服务状态
        Show-Status
        
        Write-Info "访问地址:"
        Write-Host "  Web界面: http://localhost:8000" -ForegroundColor Cyan
        Write-Host "  API文档: http://localhost:8000/docs" -ForegroundColor Cyan
        Write-Host "  健康检查: http://localhost:8000/health" -ForegroundColor Cyan
    } else {
        Write-Error "服务启动失败"
        docker-compose logs
    }
}

# 停止服务
function Stop-Service {
    Write-Header "停止 LandPPT 服务"
    
    Write-Info "停止服务..."
    docker-compose down
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "服务已停止"
    } else {
        Write-Error "停止服务失败"
    }
}

# 显示状态
function Show-Status {
    Write-Header "服务状态"
    
    Write-Info "Docker Compose 状态:"
    docker-compose ps
    
    Write-Info "容器资源使用:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
}

# 显示日志
function Show-Logs {
    Write-Header "服务日志"
    
    Write-Info "显示最近的日志..."
    docker-compose logs --tail=50 -f
}

# 清理资源
function Clean-Resources {
    Write-Header "清理 Docker 资源"
    
    $confirmation = Read-Host "确定要清理所有 LandPPT 相关资源吗? (y/N)"
    if ($confirmation -eq 'y' -or $confirmation -eq 'Y') {
        Write-Info "停止并删除容器..."
        docker-compose down -v
        
        Write-Info "删除镜像..."
        docker rmi landppt-integrated:latest 2>$null
        
        Write-Info "清理未使用的资源..."
        docker system prune -f
        
        Write-Success "清理完成"
    } else {
        Write-Info "清理已取消"
    }
}

# 显示帮助
function Show-Help {
    Write-Host "LandPPT 本地部署管理脚本" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "用法:" -ForegroundColor Yellow
    Write-Host "  .\deploy_local.ps1 [选项]"
    Write-Host ""
    Write-Host "选项:" -ForegroundColor Yellow
    Write-Host "  -Build    构建 Docker 镜像"
    Write-Host "  -Run      启动服务"
    Write-Host "  -Stop     停止服务"
    Write-Host "  -Status   查看服务状态"
    Write-Host "  -Logs     查看服务日志"
    Write-Host "  -Clean    清理所有资源"
    Write-Host ""
    Write-Host "示例:" -ForegroundColor Yellow
    Write-Host "  .\deploy_local.ps1 -Build    # 构建镜像"
    Write-Host "  .\deploy_local.ps1 -Run      # 启动服务"
    Write-Host "  .\deploy_local.ps1 -Status   # 查看状态"
    Write-Host ""
    Write-Host "快速开始:" -ForegroundColor Green
    Write-Host "  1. .\deploy_local.ps1 -Build"
    Write-Host "  2. .\deploy_local.ps1 -Run"
    Write-Host "  3. 访问 http://localhost:8000"
}

# 主函数
function Main {
    if (!(Test-Docker)) {
        exit 1
    }
    
    if ($Build) {
        Build-Image
    } elseif ($Run) {
        Start-Service
    } elseif ($Stop) {
        Stop-Service
    } elseif ($Status) {
        Show-Status
    } elseif ($Logs) {
        Show-Logs
    } elseif ($Clean) {
        Clean-Resources
    } else {
        Show-Help
    }
}

# 执行主函数
Main
