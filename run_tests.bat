@echo off
chcp 65001 >nul
echo ========================================
echo LandPPT Supabase 数据库检测工具
echo ========================================
echo.

:menu
echo 请选择要执行的检测:
echo.
echo [1] 完整健康检查 (推荐首次使用)
echo [2] 快速检查 (日常监控)
echo [3] 压力测试 (性能评估)
echo [4] 安装依赖
echo [5] 退出
echo.
set /p choice="请输入选项 (1-5): "

if "%choice%"=="1" goto health_check
if "%choice%"=="2" goto quick_check
if "%choice%"=="3" goto stress_test
if "%choice%"=="4" goto install_deps
if "%choice%"=="5" goto exit
echo 无效选项，请重新选择
goto menu

:health_check
echo.
echo 🚀 开始完整健康检查...
echo ========================================
python database_health_check.py
echo.
echo 检查完成！按任意键返回菜单...
pause >nul
goto menu

:quick_check
echo.
echo ⚡ 开始快速检查...
echo ========================================
python quick_db_check.py
echo.
echo 检查完成！按任意键返回菜单...
pause >nul
goto menu

:stress_test
echo.
echo 🔥 开始压力测试...
echo ========================================
python database_stress_test.py
echo.
echo 测试完成！按任意键返回菜单...
pause >nul
goto menu

:install_deps
echo.
echo 📦 安装 Python 依赖...
echo ========================================
pip install psycopg2-binary requests
echo.
echo 依赖安装完成！按任意键返回菜单...
pause >nul
goto menu

:exit
echo.
echo 👋 感谢使用 LandPPT 数据库检测工具！
echo.
exit /b 0
