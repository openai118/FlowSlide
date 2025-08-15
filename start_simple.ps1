Write-Host "🚀 启动FlowSlide测试服务器..." -ForegroundColor Green

# 切换到脚本所在目录
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $PSScriptRoot

# 激活虚拟环境
Write-Host "📦 激活虚拟环境..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# 启动简单测试服务器
Write-Host "🌐 启动服务器..." -ForegroundColor Cyan
python simple_test.py

Write-Host "`n可用地址:" -ForegroundColor Green
Write-Host "🏠 首页(公共): http://localhost:8000/home" -ForegroundColor Cyan
Write-Host "📚 API文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🌐 Web界面(控制台): http://localhost:8000/web" -ForegroundColor Cyan
