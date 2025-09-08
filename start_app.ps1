#!/usr/bin/env pwsh
Write-Host "Starting FlowSlide application..." -ForegroundColor Green
Write-Host ""

# 设置工作目录
Set-Location $PSScriptRoot

# 检查Python环境
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python version: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Python not found; ensure Python 3.11+ is installed" -ForegroundColor Red
    Read-Host "Press any key to exit"
    exit 1
}

# 循环启动应用程序，直到手动停止
$restartCount = 0
while ($true) {
    $restartCount++
    Write-Host "Starting FlowSlide... (restarts: $restartCount)" -ForegroundColor Yellow

    try {
        # 启动应用程序 using uvicorn import string to support reload/workers correctly
        Write-Host "Launching uvicorn with import string src.flowslide.main:app" -ForegroundColor Cyan
        python -m uvicorn src.flowslide.main:app --host 0.0.0.0 --port 8000

        # 如果正常退出（exit code 0），则停止循环
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Application exited normally" -ForegroundColor Green
            break
        }

        # 如果是重启退出码（exit code 42），则重新启动
        if ($LASTEXITCODE -eq 42) {
            Write-Host "Restart requested, restarting..." -ForegroundColor Yellow
            Start-Sleep -Seconds 2
            continue
        }

        # 其他错误退出
    Write-Host "Application exited with error (Exit Code: $LASTEXITCODE)" -ForegroundColor Red
    Write-Host "Press any key to exit, or wait 5 seconds to retry..." -ForegroundColor Yellow
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
    Write-Host "Retrying..." -ForegroundColor Yellow

    } catch {
    Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Press any key to exit, or wait 5 seconds to retry..." -ForegroundColor Yellow
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
    Write-Host "Retrying..." -ForegroundColor Yellow
    }
}

Write-Host "FlowSlide application stopped" -ForegroundColor Cyan
