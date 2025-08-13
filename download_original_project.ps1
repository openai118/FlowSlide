# LandPPT 项目下载脚本 (PowerShell)
# 用于在没有 git 的情况下下载原项目

# 设置下载参数
$repoUrl = "https://github.com/sligter/LandPPT/archive/refs/heads/master.zip"
$downloadPath = "F:\projects\landppt-original.zip"
$extractPath = "F:\projects\landppt-original"

Write-Host "🔄 开始下载 LandPPT 原项目..." -ForegroundColor Blue

try {
    # 创建目录
    if (!(Test-Path "F:\projects")) {
        New-Item -ItemType Directory -Path "F:\projects" -Force | Out-Null
    }
    
    # 下载 ZIP 文件
    Write-Host "📥 正在下载项目文件..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $repoUrl -OutFile $downloadPath -UseBasicParsing
    
    Write-Host "✅ 下载完成" -ForegroundColor Green
    
    # 解压文件
    Write-Host "📦 正在解压文件..." -ForegroundColor Yellow
    
    # 如果目标目录存在，先删除
    if (Test-Path $extractPath) {
        Remove-Item -Path $extractPath -Recurse -Force
    }
    
    # 解压到临时目录
    $tempExtractPath = "F:\projects\temp_extract"
    if (Test-Path $tempExtractPath) {
        Remove-Item -Path $tempExtractPath -Recurse -Force
    }
    
    Expand-Archive -Path $downloadPath -DestinationPath $tempExtractPath -Force
    
    # 移动文件到正确位置（GitHub ZIP 会创建一个带版本号的文件夹）
    $extractedFolder = Get-ChildItem -Path $tempExtractPath -Directory | Select-Object -First 1
    Move-Item -Path $extractedFolder.FullName -Destination $extractPath
    
    # 清理临时文件
    Remove-Item -Path $tempExtractPath -Recurse -Force
    Remove-Item -Path $downloadPath -Force
    
    Write-Host "✅ 解压完成" -ForegroundColor Green
    
    # 显示下载的文件
    Write-Host "`n📁 下载的文件结构:" -ForegroundColor Cyan
    Get-ChildItem -Path $extractPath | Select-Object Name, Length | Format-Table
    
    Write-Host "🎉 LandPPT 原项目下载完成！" -ForegroundColor Green
    Write-Host "📂 项目位置: $extractPath" -ForegroundColor Blue
    Write-Host "`n🚀 下一步:" -ForegroundColor Yellow
    Write-Host "   1. 切换到 try1 目录: cd F:\projects\try1" -ForegroundColor White
    Write-Host "   2. 运行整合脚本: .\integrate_project.sh" -ForegroundColor White
    
} catch {
    Write-Host "❌ 下载失败: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "`n💡 备选方案:" -ForegroundColor Yellow
    Write-Host "   1. 手动访问: https://github.com/sligter/LandPPT" -ForegroundColor White
    Write-Host "   2. 点击 'Code' -> 'Download ZIP'" -ForegroundColor White
    Write-Host "   3. 解压到 F:\projects\landppt-original\" -ForegroundColor White
}
