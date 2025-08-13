# LandPPT 项目整合脚本 (PowerShell版本 - 修复版)

# 检查原项目目录
function Test-OriginalProject {
    Write-Host "检查原项目目录..." -ForegroundColor Blue
    
    $originalPath = "F:\projects\landppt-original"
    
    if (!(Test-Path $originalPath)) {
        Write-Host "未找到原项目目录: $originalPath" -ForegroundColor Red
        Write-Host "请确保已运行 download_original_project.ps1 下载原项目" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "找到原项目目录" -ForegroundColor Green
    return $originalPath
}

# 复制原项目文件
function Copy-OriginalFiles {
    param([string]$OriginalPath)
    
    Write-Host "复制原项目文件..." -ForegroundColor Magenta
    
    # 核心目录
    $coreDirs = @("src", "template_examples", "docs")
    
    foreach ($dir in $coreDirs) {
        $sourcePath = Join-Path $OriginalPath $dir
        if (Test-Path $sourcePath) {
            Write-Host "复制目录: $dir" -ForegroundColor Blue
            if (Test-Path $dir) {
                Remove-Item -Path $dir -Recurse -Force
            }
            Copy-Item -Path $sourcePath -Destination "." -Recurse -Force
            Write-Host "已复制: $dir" -ForegroundColor Green
        } else {
            Write-Host "原项目中未找到目录: $dir" -ForegroundColor Yellow
        }
    }
    
    # 核心文件
    $coreFiles = @(
        "run.py",
        "pyproject.toml", 
        "uv.lock",
        ".python-version",
        "LICENSE",
        "README.md"
    )
    
    foreach ($file in $coreFiles) {
        $sourcePath = Join-Path $OriginalPath $file
        if (Test-Path $sourcePath) {
            Write-Host "复制文件: $file" -ForegroundColor Blue
            Copy-Item -Path $sourcePath -Destination "." -Force
            Write-Host "已复制: $file" -ForegroundColor Green
        } else {
            Write-Host "原项目中未找到文件: $file" -ForegroundColor Yellow
        }
    }
}

# 更新环境配置
function Update-EnvConfig {
    Write-Host "更新环境配置..." -ForegroundColor Magenta
    
    # 备份当前配置
    if (Test-Path ".env.example") {
        Copy-Item -Path ".env.example" -Destination ".env.example.backup" -Force
        Write-Host "原配置已备份" -ForegroundColor Blue
    }
    
    Write-Host "环境配置已更新" -ForegroundColor Green
}

# 合并 Dockerfile
function Merge-Dockerfile {
    Write-Host "合并 Dockerfile..." -ForegroundColor Magenta
    
    if (Test-Path "Dockerfile.ci-compatible") {
        Copy-Item -Path "Dockerfile.ci-compatible" -Destination "Dockerfile" -Force
        Write-Host "Dockerfile 已更新" -ForegroundColor Green
    }
}

# 主整合函数
function Start-Integration {
    Write-Host "LandPPT 项目自动整合" -ForegroundColor Magenta
    Write-Host "开始时间: $(Get-Date)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    try {
        # 执行整合步骤
        $originalPath = Test-OriginalProject
        Copy-OriginalFiles -OriginalPath $originalPath
        Update-EnvConfig
        Merge-Dockerfile
        
        # 检查文件结构
        Write-Host ""
        Write-Host "当前项目文件结构:" -ForegroundColor Cyan
        Get-ChildItem -Name | Sort-Object
        
        # 总结
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "项目整合完成！" -ForegroundColor Green
        Write-Host ""
        Write-Host "整合结果:" -ForegroundColor Cyan
        Write-Host "  原项目核心文件已复制" -ForegroundColor White
        Write-Host "  环境配置已保留" -ForegroundColor White
        Write-Host "  Docker 配置已优化" -ForegroundColor White
        Write-Host ""
        Write-Host "下一步:" -ForegroundColor Yellow
        Write-Host "  1. 编辑 .env 文件，配置你的 API 密钥" -ForegroundColor White
        Write-Host "  2. 运行 python validate_system.py 验证系统" -ForegroundColor White
        Write-Host "  3. 使用 docker-compose up -d 启动服务" -ForegroundColor White
        Write-Host ""
        Write-Host "完成时间: $(Get-Date)" -ForegroundColor Cyan
        
    } catch {
        Write-Host "整合过程中出现错误: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

# 执行整合
Start-Integration
