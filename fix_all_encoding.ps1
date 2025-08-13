# 一键修复所有编码问题的脚本

Write-Host "🔧 开始修复所有文件的编码问题..." -ForegroundColor Green

# 检查哪些文件有乱码
$files_to_check = @(
    "database_health_check.py",
    "quick_db_check.py", 
    "database_stress_test.py",
    "simple_performance_test.py"
)

foreach ($file in $files_to_check) {
    if (Test-Path $file) {
        $content = Get-Content $file -Raw
        
        # 检查是否有乱码字符
        if ($content -match '[â€™â€œâ€�â€¦â‚¬Â£Â¥Â§Â©Â®Â°Â±Â²Â³Â¹Â¼Â½Â¾ÃÄÅÆÇÈÉÊÑÒÖÜàáâäåæçèéêñòöüÿ]') {
            Write-Host "⚠️  发现乱码文件: $file" -ForegroundColor Yellow
            
            # 基本的乱码修复
            $content = $content -replace 'â?', '❌'
            $content = $content -replace 'â?', '✅'
            $content = $content -replace 'ðŸ"', '🔧'
            $content = $content -replace 'ðŸš€', '🚀'
            $content = $content -replace 'â?', '⚡'
            $content = $content -replace 'ðŸ"Š', '📊'
            $content = $content -replace 'ðŸ"?', '🔍'
            $content = $content -replace 'ðŸ'?', '💾'
            $content = $content -replace 'ðŸŽ‰', '🎉'
            $content = $content -replace 'â?ï¸?', '⚠️'
            
            # 常见中文乱码修复
            $content = $content -replace 'æ•°æ®åº"', '数据库'
            $content = $content -replace 'è¿žæŽ¥', '连接'
            $content = $content -replace 'æµ‹è¯•', '测试'
            $content = $content -replace 'æˆåŠŸ', '成功'
            $content = $content -replace 'å¤±è´?', '失败'
            $content = $content -replace 'è¯·å®‰è£?', '请安装'
            $content = $content -replace 'å¼€å§‹', '开始'
            $content = $content -replace 'é€šè¿?', '通过'
            $content = $content -replace 'ä¿¡æ?', '信息'
            $content = $content -replace 'æ£€æŸ?', '检查'
            $content = $content -replace 'å­˜å‚¨', '存储'
            $content = $content -replace 'å¯ç"¨', '可用'
            $content = $content -replace 'ä¸?å¯ç"¨', '不可用'
            $content = $content -replace 'éƒ¨åˆ†', '部分'
            $content = $content -replace 'å®Œæˆ', '完成'
            
            # 保存修复后的文件
            [System.IO.File]::WriteAllText((Resolve-Path $file).Path, $content, [System.Text.Encoding]::UTF8)
            Write-Host "✅ 已修复: $file" -ForegroundColor Green
        } else {
            Write-Host "✅ 无需修复: $file" -ForegroundColor Green
        }
    }
}

Write-Host "`n🎉 编码修复完成！" -ForegroundColor Green
Write-Host "💡 如果仍有乱码，请手动检查和修复相应文件" -ForegroundColor Yellow
