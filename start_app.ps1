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

# 循环启动应用程序，直到手动停止
$restartCount = 0
while ($true) {
    $restartCount++
    Write-Host "📦 正在启动 FlowSlide... (重启次数: $restartCount)" -ForegroundColor Yellow

    try {
        # 启动应用程序
        python -m src.flowslide.main

        # 如果正常退出（exit code 0），则停止循环
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ 应用程序正常退出" -ForegroundColor Green
            break
        }

        # 如果是重启退出码（exit code 42），则重新启动
        if ($LASTEXITCODE -eq 42) {
            Write-Host "🔄 检测到重启请求，正在重新启动..." -ForegroundColor Yellow
            Start-Sleep -Seconds 2
            continue
        }

        # 其他错误退出
        Write-Host "❌ 应用程序异常退出 (Exit Code: $LASTEXITCODE)" -ForegroundColor Red
        Write-Host "按任意键退出，或等待5秒后重试..." -ForegroundColor Yellow
        $key = $null
        $timeout = 5
        while ($timeout -gt 0 -and -not $key) {
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true)
            }
            Start-Sleep -Milliseconds 1000
            $timeout--
        }
        if ($key) {
            break
        }
        Write-Host "自动重试..." -ForegroundColor Yellow

    } catch {
        Write-Host "❌ 启动失败: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "按任意键退出，或等待5秒后重试..." -ForegroundColor Yellow
        $key = $null
        $timeout = 5
        while ($timeout -gt 0 -and -not $key) {
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true)
            }
            Start-Sleep -Milliseconds 1000
            $timeout--
        }
        if ($key) {
            break
        }
        Write-Host "自动重试..." -ForegroundColor Yellow
    }
}

Write-Host "👋 FlowSlide 应用程序已停止" -ForegroundColor Cyan
