#!/usr/bin/env powershell

# Docker Hub 认证测试脚本
# 用于验证 GitHub Secrets 配置是否正确

Write-Host "🔍 Docker Hub 认证测试" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan

# 检查必需的环境变量
if (-not $env:DOCKER_HUB_USERNAME) {
    Write-Host "❌ 错误: DOCKER_HUB_USERNAME 环境变量未设置" -ForegroundColor Red
    Write-Host "   请在 GitHub Repository Settings > Secrets 中设置" -ForegroundColor Yellow
    exit 1
}

if (-not $env:DOCKER_HUB_TOKEN) {
    Write-Host "❌ 错误: DOCKER_HUB_TOKEN 环境变量未设置" -ForegroundColor Red
    Write-Host "   请在 GitHub Repository Settings > Secrets 中设置" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ 检测到用户名: $env:DOCKER_HUB_USERNAME" -ForegroundColor Green
Write-Host "✅ 检测到 Token: ***********$(($env:DOCKER_HUB_TOKEN).Substring([Math]::Max(0, ($env:DOCKER_HUB_TOKEN).Length - 4)))" -ForegroundColor Green

# 测试 Docker Hub 认证
Write-Host "`n🔐 测试 Docker Hub 登录..." -ForegroundColor Cyan

try {
    # 登录 Docker Hub
    $env:DOCKER_HUB_TOKEN | docker login --username $env:DOCKER_HUB_USERNAME --password-stdin
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Docker Hub 认证成功!" -ForegroundColor Green
        
        # 检查仓库是否存在
        Write-Host "`n📦 检查仓库 $env:DOCKER_HUB_USERNAME/flowslide..." -ForegroundColor Cyan
        
        # 尝试拉取仓库信息（如果仓库不存在会失败）
        $pullResult = docker pull "$env:DOCKER_HUB_USERNAME/flowslide:latest" 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ 仓库存在且可访问" -ForegroundColor Green
        } else {
            Write-Host "⚠️  仓库可能不存在，这是首次推送的正常情况" -ForegroundColor Yellow
            Write-Host "   Docker Hub 将在首次推送时自动创建仓库" -ForegroundColor Yellow
        }
        
    } else {
        Write-Host "❌ Docker Hub 认证失败!" -ForegroundColor Red
        Write-Host "   请检查以下项目:" -ForegroundColor Yellow
        Write-Host "   1. DOCKER_HUB_USERNAME 是否正确" -ForegroundColor Yellow
        Write-Host "   2. DOCKER_HUB_TOKEN 是否有效" -ForegroundColor Yellow
        Write-Host "   3. Token 权限是否包含 Read, Write, Delete" -ForegroundColor Yellow
        exit 1
    }
    
} catch {
    Write-Host "❌ 认证过程出错: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n🎯 下一步操作建议:" -ForegroundColor Cyan
Write-Host "1. 如果认证成功，可以创建一个提交来触发 GitHub Actions" -ForegroundColor White
Write-Host "2. 如果认证失败，请重新生成 Docker Hub Token" -ForegroundColor White
Write-Host "3. 确保 GitHub Secrets 中的值没有多余的空格或字符" -ForegroundColor White

Write-Host "`n✅ 测试完成!" -ForegroundColor Green
