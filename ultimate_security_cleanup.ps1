# 终极安全清理脚本 - 清除所有敏感信息

Write-Host "🚨 开始终极安全清理..." -ForegroundColor Red

# 定义所有需要替换的敏感信息
$sensitiveData = @{
    # JWT 令牌
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZpdXpldGF6cGVyZWJ1cXdtcm5hIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ5NTI2NjgsImV4cCI6MjA3MDUyODY2OH0.aQwP7h_SFau6UsfsGbUHY3kf-RDYM8LEOLu0hsbv5Ns' = 'your_supabase_anon_key'
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZpdXpldGF6cGVyZWJ1cXdtcm5hIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NDk1MjY2OCwiZXhwIjoyMDcwNTI4NjY4fQ.8vdb7DH860INPx5ZhDd9JTdsfJtDAhOizQNZgEqONNE' = 'your_supabase_service_key'
    
    # 项目标识符
    'fiuzetazperebuqwmrna' = 'your-project-id'
    'landppt-files' = 'your-storage-bucket'
    
    # 在清理脚本中的残留
    'db.fiuzetazperebuqwmrna.supabase.co' = 'your-supabase-host'
    'https://fiuzetazperebuqwmrna.supabase.co' = 'https://your-project.supabase.co'
}

# 需要清理的所有文件
$filesToClean = @(
    "database_health_check.py",
    "quick_db_check.py",
    "database_stress_test.py", 
    "database_diagnosis.py",
    "simple_performance_test.py",
    "docker-compose.yml",
    "docker-compose.backup.yml",
    "README.md",
    "DEPLOYMENT_GUIDE.md",
    "DATABASE_MONITORING_GUIDE.md",
    ".env.integrated",
    "security_cleanup.ps1"
)

$cleanedCount = 0

foreach ($file in $filesToClean) {
    if (Test-Path $file) {
        Write-Host "🧹 清理文件: $file" -ForegroundColor Yellow
        
        $content = Get-Content $file -Raw -Encoding UTF8
        $originalContent = $content
        
        # 替换所有敏感信息
        foreach ($sensitive in $sensitiveData.Keys) {
            $replacement = $sensitiveData[$sensitive]
            $content = $content -replace [regex]::Escape($sensitive), $replacement
        }
        
        # 如果内容有变化，保存文件
        if ($content -ne $originalContent) {
            [System.IO.File]::WriteAllText((Resolve-Path $file).Path, $content, [System.Text.Encoding]::UTF8)
            Write-Host "   ✅ 已清理敏感信息" -ForegroundColor Green
            $cleanedCount++
        } else {
            Write-Host "   ✅ 无敏感信息" -ForegroundColor Green
        }
    } else {
        Write-Host "   ⚠️ 文件不存在: $file" -ForegroundColor Yellow
    }
}

Write-Host "`n🎯 清理完成统计:" -ForegroundColor Cyan
Write-Host "   修改的文件数: $cleanedCount" -ForegroundColor White
Write-Host "   检查的文件数: $($filesToClean.Count)" -ForegroundColor White

Write-Host "`n🔒 安全提醒:" -ForegroundColor Red
Write-Host "   1. 立即撤销所有 Supabase JWT 令牌" -ForegroundColor Yellow
Write-Host "   2. 在 Supabase 控制台重新生成 ANON 和 SERVICE ROLE 密钥" -ForegroundColor Yellow  
Write-Host "   3. 更改数据库密码" -ForegroundColor Yellow
Write-Host "   4. 检查访问日志是否有异常" -ForegroundColor Yellow

Write-Host "`n✅ 终极安全清理完成！" -ForegroundColor Green
