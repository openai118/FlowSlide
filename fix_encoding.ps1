# 修复编码问题的脚本
# 修复 PowerShell 编码问题导致的中文乱码

# 需要修复的文件和对应的正确内容
$fixes = @{
    'database_diagnosis.py' = @{
        'LandPPT æ•°æ®åº"è¿žæŽ¥è¯Šæ–­å·¥å…?' = 'LandPPT 数据库连接诊断工具'
        'è¯¦ç»†è¯Šæ–­è¿žæŽ¥é—®é¢˜' = '详细诊断连接问题'
        'â?è¯·å®‰è£?' = '❌ 请安装'
        'è¯Šæ–­æ•°æ®åº"è¿žæŽ¥é—®é¢?' = '诊断数据库连接问题'
        'LandPPT æ•°æ®åº"è¿žæŽ¥è¯Šæ–?' = 'LandPPT 数据库连接诊断'
        'æµ‹è¯•é…ç½®' = '测试配置'
        'åº"ç"¨ç"¨æˆ·' = '应用用户'
        'ç®¡ç†å'˜ç"¨æˆ·' = '管理员用户'
        'è¿žæŽ¥æ­£å¸?' = '连接正常'
        'è¿žæŽ¥å¤±è´?' = '连接失败'
        'æŸ¥è¯¢æˆåŠŸ' = '查询成功'
        'æŸ¥è¯¢å¤±è´?' = '查询失败'
        'è¯Šæ–­ç»"æžœ' = '诊断结果'
        'è§£å†³æ–¹æ¡ˆ' = '解决方案'
        'æ£€æŸ¥ç½'ç»œè¿žæŽ¥' = '检查网络连接'
        'ç¡®è®¤ç"¨æˆ·ååˆ†åˆ«è¯¥' = '确认用户名密码正确'
        'é‡æ–°è¿è¡Œè¯Šæ–­' = '重新运行诊断'
    }
    'database_health_check.py' = @{
        'â? æ³¨æ„' = '⚠️ 注意'
        'é€šå¸¸æƒ…å†µä¸‹' = '通常情况下'
        'åº"ç"¨ä½¿ç"¨' = '应用使用'
        'å³å¯' = '即可'
        'è¿žæŽ¥æˆåŠŸ' = '连接成功'
        'è¿žæŽ¥å¤±è´?' = '连接失败'
        'æµ‹è¯•å®Œæˆ' = '测试完成'
        'åº"ç"¨ç"¨æˆ·è¿žæŽ¥æµ‹è¯•' = '应用用户连接测试'
    }
    'quick_db_check.py' = @{
        'ð?快速æ•°æ®åº"连接检查' = '🚀 快速数据库连接检查'
        'â? 开始连接测试' = '⚡ 开始连接测试'
        'â? è¿žæŽ¥æˆåŠŸ' = '✅ 连接成功'
        'â? è¿žæŽ¥å¤±è´?' = '❌ 连接失败'
        'â? æ•°æ®åº"ä¿¡æ?' = '📊 数据库信息'
        'â? åŸºæœ¬åŠŸèƒ½æµ‹è¯?' = '🔍 基本功能测试'
        'â? å­˜å‚¨æ£€æŸ?' = '💾 存储检查'
        'â? Supabase Storage APIæ?ç"¨' = '✅ Supabase Storage API可用'
        'â? Supabase Storage APIä¸?' = '❌ Supabase Storage API不可用'
        'â? æ‰€æœ‰æµ‹è¯•é€šè¿?' = '🎉 所有测试通过'
        'â? éƒ¨åˆ†æµ‹è¯•å¤±è´?' = '⚠️ 部分测试失败'
    }
}

Write-Host "🔧 开始修复编码问题..." -ForegroundColor Green

foreach ($file in $fixes.Keys) {
    if (Test-Path $file) {
        Write-Host "📝 修复文件: $file" -ForegroundColor Yellow
        
        $content = Get-Content $file -Raw -Encoding UTF8
        
        foreach ($oldText in $fixes[$file].Keys) {
            $newText = $fixes[$file][$oldText]
            $content = $content -replace [regex]::Escape($oldText), $newText
        }
        
        # 使用 UTF8 编码保存
        [System.IO.File]::WriteAllText((Resolve-Path $file).Path, $content, [System.Text.Encoding]::UTF8)
    }
}

Write-Host "✅ 编码修复完成！" -ForegroundColor Green
