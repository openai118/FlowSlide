# LandPPT 项目整合脚本 (PowerShell版本)
# 用于在 Windows 环境下整合原项目和增强功能

param(
    [switch]$Force = $false
)

# 颜色输出函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Info { param([string]$msg) Write-ColorOutput "ℹ️  $msg" "Blue" }
function Write-Success { param([string]$msg) Write-ColorOutput "✅ $msg" "Green" }
function Write-Warning { param([string]$msg) Write-ColorOutput "⚠️  $msg" "Yellow" }
function Write-Error { param([string]$msg) Write-ColorOutput "❌ $msg" "Red" }
function Write-Header { param([string]$msg) Write-ColorOutput "🎯 $msg" "Magenta" }

# 检查原项目目录
function Test-OriginalProject {
    Write-Info "检查原项目目录..."
    
    $originalPath = "F:\projects\landppt-original"
    
    if (!(Test-Path $originalPath)) {
        Write-Error "未找到原项目目录: $originalPath"
        Write-Host ""
        Write-Host "请确保已运行 download_original_project.ps1 下载原项目"
        exit 1
    }
    
    Write-Success "找到原项目目录"
    return $originalPath
}

# 备份当前项目
function Backup-CurrentProject {
    Write-Header "备份当前项目"
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupDir = "F:\projects\try1-backup-$timestamp"
    
    Write-Info "创建备份: $backupDir"
    Copy-Item -Path "." -Destination $backupDir -Recurse -Force
    
    Write-Success "当前项目已备份到: $backupDir"
}

# 复制原项目文件
function Copy-OriginalFiles {
    param([string]$OriginalPath)
    
    Write-Header "复制原项目文件"
    
    # 核心目录
    $coreDirs = @("src", "template_examples", "docs")
    
    foreach ($dir in $coreDirs) {
        $sourcePath = Join-Path $OriginalPath $dir
        if (Test-Path $sourcePath) {
            Write-Info "复制目录: $dir"
            if (Test-Path $dir) {
                Remove-Item -Path $dir -Recurse -Force
            }
            Copy-Item -Path $sourcePath -Destination "." -Recurse -Force
            Write-Success "已复制: $dir"
        } else {
            Write-Warning "原项目中未找到目录: $dir"
        }
    }
    
    # 核心文件
    $coreFiles = @(
        "run.py",
        "pyproject.toml", 
        "uv.lock",
        "uv.toml",
        ".python-version",
        "CONTRIBUTING.md",
        "LICENSE",
        "README.md",
        "README_EN.md"
    )
    
    foreach ($file in $coreFiles) {
        $sourcePath = Join-Path $OriginalPath $file
        if (Test-Path $sourcePath) {
            Write-Info "复制文件: $file"
            Copy-Item -Path $sourcePath -Destination "." -Force
            Write-Success "已复制: $file"
        } else {
            Write-Warning "原项目中未找到文件: $file"
        }
    }
}

# 合并环境配置
function Merge-EnvConfig {
    param([string]$OriginalPath)
    
    Write-Header "合并环境配置"
    
    $originalEnv = Join-Path $OriginalPath ".env.example"
    $currentEnv = ".env.example"
    $mergedEnv = ".env.example.merged"
    
    if (!(Test-Path $originalEnv)) {
        Write-Warning "原项目环境配置不存在，保持当前配置"
        return
    }
    
    Write-Info "合并环境配置文件..."
    
    # 创建合并后的环境配置
    $envContent = @'
# LandPPT 完整环境配置文件
# 原项目配置 + 数据库监控 + R2备份功能

# ======================
# AI 提供商配置
# ======================
DEFAULT_AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=your_azure_endpoint_here

# Ollama 本地模型配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# ======================
# 服务器配置
# ======================
HOST=0.0.0.0
PORT=8000
SECRET_KEY=your-secure-secret-key
BASE_URL=http://localhost:8000

# ======================
# 数据库配置
# ======================
DB_HOST=your-supabase-host
DB_PORT=5432
DB_NAME=postgres
DB_USER=your_db_user
DB_PASSWORD=your_secure_password

# ======================
# Supabase 配置
# ======================
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# ======================
# 存储配置
# ======================
STORAGE_BUCKET=your-storage-bucket
STORAGE_PROVIDER=supabase

# ======================
# 研究功能配置
# ======================
TAVILY_API_KEY=your_tavily_api_key_here
SEARXNG_HOST=http://localhost:8888
RESEARCH_PROVIDER=tavily

# ======================
# 图像服务配置
# ======================
ENABLE_IMAGE_SERVICE=true
PIXABAY_API_KEY=your_pixabay_api_key_here
UNSPLASH_ACCESS_KEY=your_unsplash_key_here
SILICONFLOW_API_KEY=your_siliconflow_key_here
POLLINATIONS_API_TOKEN=your_pollinations_token

# ======================
# 导出功能配置
# ======================
APRYSE_LICENSE_KEY=your_apryse_key_here

# ======================
# Cloudflare R2 备份配置
# ======================
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
R2_BUCKET_NAME=landppt-backups
BACKUP_SCHEDULE=0 2 * * *
BACKUP_RETENTION_DAYS=30
BACKUP_WEBHOOK_URL=

# ======================
# 健康检查配置
# ======================
SKIP_DB_CHECK=false
REQUIRE_DB=true
RUN_DB_SCHEMA_CHECK=true

# ======================
# 性能配置
# ======================
MAX_WORKERS=4
REQUEST_TIMEOUT=30
DB_POOL_SIZE=10
MAX_TOKENS=8192
TEMPERATURE=0.7

# ======================
# 应用配置
# ======================
DEBUG=false
LOG_LEVEL=INFO
TEMP_CLEANUP_INTERVAL=24

# ======================
# 安全配置
# ======================
JWT_SECRET=your_jwt_secret_key
API_RATE_LIMIT=100
MAX_UPLOAD_SIZE=50

# ======================
# 邮件配置 (可选)
# ======================
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=true

# ======================
# 监控配置 (可选)
# ======================
METRICS_ENABLED=false
METRICS_PORT=9090
HEALTH_CHECK_ENDPOINT=/health

# ======================
# Redis 配置 (可选)
# ======================
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=false

# ======================
# 开发配置
# ======================
DEV_RELOAD=false
DEV_HOST=0.0.0.0
ALLOWED_HOSTS=localhost,127.0.0.1
'@

    # 备份原配置并使用新配置
    if (Test-Path $currentEnv) {
        Move-Item -Path $currentEnv -Destination "$currentEnv.backup" -Force
        Write-Info "原配置已备份为: $currentEnv.backup"
    }
    
    $envContent | Out-File -FilePath $currentEnv -Encoding UTF8
    Write-Success "环境配置已合并"
}

# 合并 Dockerfile
function Merge-Dockerfile {
    param([string]$OriginalPath)
    
    Write-Header "合并 Dockerfile"
    
    $originalDockerfile = Join-Path $OriginalPath "Dockerfile"
    $enhancedDockerfile = "Dockerfile.ci-compatible"
    $mergedDockerfile = "Dockerfile"
    
    if (!(Test-Path $originalDockerfile)) {
        Write-Warning "原项目 Dockerfile 不存在，使用增强版 Dockerfile"
        Copy-Item -Path $enhancedDockerfile -Destination $mergedDockerfile -Force
        return
    }
    
    Write-Info "合并 Dockerfile..."
    
    # 使用我们优化过的 Dockerfile
    Copy-Item -Path $enhancedDockerfile -Destination $mergedDockerfile -Force
    Write-Success "Dockerfile 已合并"
}

# 更新脚本文件
function Update-Scripts {
    param([string]$OriginalPath)
    
    Write-Header "更新脚本文件"
    
    # 检查原项目脚本
    $originalScripts = @("docker-entrypoint.sh", "docker-healthcheck.sh")
    
    foreach ($script in $originalScripts) {
        $originalScript = Join-Path $OriginalPath $script
        if (Test-Path $originalScript) {
            Write-Info "更新脚本: $script"
            
            # 复制原脚本
            Copy-Item -Path $originalScript -Destination "." -Force
            
            # 创建增强版脚本
            $enhancedScript = $script -replace "\.sh$", "-enhanced.sh"
            Copy-Item -Path $originalScript -Destination $enhancedScript -Force
            
            Write-Success "已创建增强版脚本: $enhancedScript"
        } else {
            Write-Warning "原项目中未找到脚本: $script"
        }
    }
}

# 创建整合后的文档
function New-IntegratedDocs {
    Write-Header "创建整合文档"
    
    $readmeContent = @'
# LandPPT 完整版 - AI驱动的PPT生成平台

## 🌟 项目简介

LandPPT 完整版是一个集成了数据库监控、自动化备份和企业级运维功能的 AI PPT 生成平台。

### 🎯 核心功能
- **AI PPT 生成**: 基于多种 AI 模型的智能演示文稿生成
- **数据库监控**: 实时监控 Supabase 数据库健康状态  
- **自动化备份**: Cloudflare R2 自动备份和恢复
- **企业级部署**: Docker 容器化部署和 CI/CD 集成
- **系统监控**: 全面的健康检查和性能监控

## 📥 快速开始

### 1. 配置环境
```bash
# 复制环境配置
copy .env.example .env

# 编辑 .env 文件，填入你的 API 密钥和数据库信息
```

### 2. 启动服务
```bash
# 使用 Docker Compose 启动
docker-compose up -d

# 或者本地开发
uv sync
uv run python run.py
```

### 3. 访问应用
- Web 界面: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 🛠️ 管理工具

### 数据库监控
```bash
# 快速健康检查
python tools/quick_db_check.py

# 全面健康检查  
python tools/database_health_check.py
```

### 备份管理
```bash
# 测试备份配置
python validate_system.py

# 手动备份 (需要 bash 环境)
# ./backup-manager.sh run-backup
```

## 🔧 配置说明

### 必需配置
- **AI 提供商**: OpenAI、Anthropic、Google 等 API 密钥
- **数据库**: Supabase 数据库连接信息
- **存储**: Supabase Storage 或其他存储服务

### 可选配置
- **备份**: Cloudflare R2 配置（推荐）
- **研究**: Tavily API 密钥
- **图像**: Pixabay、Unsplash API 密钥

## 📄 许可证

本项目采用 Apache License 2.0 许可证。

---

**如果这个项目对你有帮助，请给我们一个 ⭐️ Star！**
'@

    $readmeContent | Out-File -FilePath "README_INTEGRATED.md" -Encoding UTF8
    Write-Success "已创建完整项目文档"
}

# 主整合函数
function Start-Integration {
    Write-Header "LandPPT 项目自动整合"
    Write-Host "开始时间: $(Get-Date)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    try {
        # 执行整合步骤
        $originalPath = Test-OriginalProject
        
        if (!$Force) {
            $confirmation = Read-Host "是否要备份当前项目？(y/N)"
            if ($confirmation -eq 'y' -or $confirmation -eq 'Y') {
                Backup-CurrentProject
            }
        }
        
        Copy-OriginalFiles -OriginalPath $originalPath
        Merge-EnvConfig -OriginalPath $originalPath
        Merge-Dockerfile -OriginalPath $originalPath
        Update-Scripts -OriginalPath $originalPath
        New-IntegratedDocs
        
        # 总结
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Success "项目整合完成！"
        Write-Host ""
        Write-Host "📁 整合结果:" -ForegroundColor Cyan
        Write-Host "  ✅ 原项目核心文件已复制" -ForegroundColor White
        Write-Host "  ✅ 环境配置已合并" -ForegroundColor White
        Write-Host "  ✅ Docker 配置已优化" -ForegroundColor White
        Write-Host "  ✅ 脚本文件已增强" -ForegroundColor White
        Write-Host "  ✅ 文档已更新" -ForegroundColor White
        Write-Host ""
        Write-Host "🚀 下一步:" -ForegroundColor Yellow
        Write-Host "  1. 编辑 .env 文件，配置你的 API 密钥" -ForegroundColor White
        Write-Host "  2. 运行 'python validate_system.py' 验证系统" -ForegroundColor White
        Write-Host "  3. 使用 'docker-compose up -d' 启动服务" -ForegroundColor White
        Write-Host "  4. 访问 http://localhost:8000 开始使用" -ForegroundColor White
        Write-Host ""
        Write-Host "📚 更多信息请查看:" -ForegroundColor Yellow
        Write-Host "  - README_INTEGRATED.md" -ForegroundColor White
        Write-Host "  - INTEGRATION_GUIDE.md" -ForegroundColor White
        Write-Host "  - DATABASE_MONITORING_GUIDE.md" -ForegroundColor White
        
        Write-Host ""
        Write-Host "完成时间: $(Get-Date)" -ForegroundColor Cyan
        
    } catch {
        Write-Error "整合过程中出现错误: $($_.Exception.Message)"
        Write-Host ""
        Write-Host "💡 建议:" -ForegroundColor Yellow
        Write-Host "  1. 检查原项目是否正确下载" -ForegroundColor White
        Write-Host "  2. 确保有足够的磁盘空间" -ForegroundColor White
        Write-Host "  3. 检查文件权限" -ForegroundColor White
        exit 1
    }
}

# 执行整合
Start-Integration
