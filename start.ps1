# FlowSlide PowerShell 启动脚本
# 使用方法: powershell -ExecutionPolicy Bypass -File start.ps1

Write-Host "🚀 启动FlowSlide应用..." -ForegroundColor Green
Write-Host ""

# 检查虚拟环境
$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "❌ 虚拟环境不存在，请先运行:" -ForegroundColor Red
    Write-Host "   python -m venv .venv" -ForegroundColor Yellow
    Write-Host "   uv sync" -ForegroundColor Yellow
    Read-Host "按任意键退出"
    exit 1
}

Write-Host "✅ 使用虚拟环境: $venvPython" -ForegroundColor Green
Write-Host "📍 访问地址: http://localhost:8000" -ForegroundColor Cyan
Write-Host "🏠 主页: http://localhost:8000/home" -ForegroundColor Cyan
Write-Host "📚 API文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""

# 启动应用
try {
    & $venvPython -m uvicorn src.flowslide.main:app --host 0.0.0.0 --port 8000 --reload
} catch {
    Write-Host "❌ 启动失败: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "按任意键退出"
    exit 1
}
