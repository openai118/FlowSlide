Write-Host "🔍 检查FlowSlide服务器状态..." -ForegroundColor Green

# 检查端口是否被占用
Write-Host "`n📡 检查端口8000状态..." -ForegroundColor Yellow
$port8000Check = netstat -an | Select-String ":8000"
if ($port8000Check) {
    Write-Host "✅ 端口8000有服务在监听:" -ForegroundColor Green
    Write-Host $port8000Check -ForegroundColor Cyan
} else {
    Write-Host "❌ 端口8000没有服务在监听" -ForegroundColor Red
}

# 尝试访问服务器
Write-Host "`n🌐 尝试访问FlowSlide服务器..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ 服务器响应正常! 状态码: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "📄 响应内容: $($response.Content)" -ForegroundColor Cyan
} catch {
    Write-Host "❌ 无法访问服务器: $($_.Exception.Message)" -ForegroundColor Red
    
    Write-Host "`n🚀 尝试启动服务器..." -ForegroundColor Yellow
    $PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    Set-Location $PSScriptRoot
    
    # 激活虚拟环境
    Write-Host "📦 激活虚拟环境..." -ForegroundColor Cyan
    & ".\.venv\Scripts\Activate.ps1"
    
    # 启动服务器
    Write-Host "🔥 启动FlowSlide..." -ForegroundColor Cyan
    python start_flowslide.py
}

Write-Host "`n访问地址:" -ForegroundColor Green
Write-Host "🏠 首页(公共): http://localhost:8000/home" -ForegroundColor Cyan
Write-Host "🏠 主页: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📚 API文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🌐 Web界面(控制台): http://localhost:8000/web" -ForegroundColor Cyan
