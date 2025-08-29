#!/usr/bin/env pwsh
Write-Host "🚀 启动 FlowSlide 应用程序..." -ForegroundColor Green
Write-Host ""

# 设置工作目录
Set-Location $PSScriptRoot

# 检查Python环境
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python版本: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 未找到Python，请确保已安装Python 3.11+" -ForegroundColor Red
    Read-Host "按任意键退出"
    exit 1
}

# 启动应用程序
Write-Host "📦 正在启动 FlowSlide..." -ForegroundColor Yellow
python -m src.flowslide.main

Read-Host "按任意键退出"
