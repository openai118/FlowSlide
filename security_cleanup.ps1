# 🚨 安全修复脚本
# 此脚本将清理所有包含敏感信息的文件

# 敏感信息占位符
$OLD_HOST = "your-supabase-host"
$OLD_USER = "landppt_user"  
$OLD_PASSWORD = "Openai9zLwR1sT4u"
$OLD_URL = "https://your-project-id.supabase.co"

# 新的占位符
$NEW_HOST = "your-supabase-host"
$NEW_USER = "your_db_user"
$NEW_PASSWORD = "your_secure_password"
$NEW_URL = "https://your-project.supabase.co"

Write-Host "🔒 开始清理敏感信息..." -ForegroundColor Red

# 需要清理的文件列表
$files = @(
    "database_health_check.py",
    "quick_db_check.py", 
    "database_stress_test.py",
    "database_diagnosis.py",
    "simple_performance_test.py",
    "docker-healthcheck-enhanced.sh",
    "docker-entrypoint-enhanced.sh",
    "docker-compose.yml",
    "docker-compose.backup.yml",
    "DEPLOYMENT_GUIDE.md",
    "DATABASE_MONITORING_GUIDE.md",
    "README.md",
    ".env.integrated"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "🧹 清理文件: $file" -ForegroundColor Yellow
        
        # 替换敏感信息
        (Get-Content $file -Raw) `
            -replace [regex]::Escape($OLD_HOST), $NEW_HOST `
            -replace [regex]::Escape($OLD_USER), $NEW_USER `
            -replace [regex]::Escape($OLD_PASSWORD), $NEW_PASSWORD `
            -replace [regex]::Escape($OLD_URL), $NEW_URL |
        Set-Content $file -NoNewline
    }
}

Write-Host "✅ 敏感信息清理完成！" -ForegroundColor Green
Write-Host "⚠️  请立即更改真实数据库密码！" -ForegroundColor Red
