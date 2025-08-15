@echo off
REM FlowSlide GitHub 部署脚本
REM 用于将 FlowSlide 项目推送到 GitHub openai118/FlowSlide

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   FlowSlide GitHub 部署脚本
echo ========================================
echo.

REM 检查是否在正确的目录
if not exist "run.py" (
    echo [错误] 请在 FlowSlide 项目根目录运行此脚本
    echo 当前目录: %CD%
    pause
    exit /b 1
)

echo [信息] 检查 Git 状态...
git status > nul 2>&1
if errorlevel 1 (
    echo [信息] 初始化 Git 仓库...
    git init
    if errorlevel 1 (
        echo [错误] Git 初始化失败，请检查 Git 是否已安装
        pause
        exit /b 1
    )
)

echo [信息] 检查远程仓库设置...
git remote -v | findstr "openai118/FlowSlide" > nul
if errorlevel 1 (
    echo [信息] 添加 GitHub 远程仓库...
    git remote add origin https://github.com/openai118/FlowSlide.git
    if errorlevel 1 (
        echo [错误] 添加远程仓库失败
        pause
        exit /b 1
    )
) else (
    echo [信息] 远程仓库已存在
)

echo [信息] 添加所有文件到暂存区...
git add .
if errorlevel 1 (
    echo [错误] 添加文件失败
    pause
    exit /b 1
)

echo [信息] 提交更改...
git commit -m "feat: FlowSlide v1.0.0 - Enterprise AI Presentation Platform

🚀 Features:
- FlowSlide branding and enterprise packaging
- Enterprise-grade AI presentation generator
- Multi-provider AI model support (OpenAI, Claude, Gemini, Ollama)
- Universal PostgreSQL monitoring and backup
- Automated Docker deployment pipeline
- Enhanced UI/UX with FlowSlide branding

🐳 Docker & Deployment:
- Docker image: openai118/flowslide
- Multi-architecture support (linux/amd64, linux/arm64)
- GitHub Actions CI/CD pipeline
- Automated Docker Hub publishing
- Production-ready configurations

🔧 Technical Updates:
- Updated all configuration files
- Modernized Docker compose setup
- Enhanced security and monitoring
- Comprehensive documentation
- Version bump to 1.0.0"

if errorlevel 1 (
    echo [警告] 提交可能失败（可能没有新的更改）
    echo [信息] 继续推送...
)

echo [信息] 设置主分支...
git branch -M main

echo [信息] 推送到 GitHub...
git push -u origin main
if errorlevel 1 (
    echo [错误] 推送失败，请检查：
    echo   1. GitHub 仓库是否已创建: https://github.com/openai118/FlowSlide
    echo   2. 网络连接是否正常
    echo   3. Git 认证是否正确
    pause
    exit /b 1
)

echo [成功] 代码推送完成！

echo.
echo [信息] 创建发布标签...
git tag -a v1.0.0 -m "FlowSlide v1.0.0 - Initial Release

🎉 FlowSlide 1.0.0 正式发布！

✨ 主要特性:
- AI 驱动的演示文稿生成器
- 支持多种 AI 模型 (GPT-4, Claude, Gemini)
- 企业级数据库监控
- 自动化备份系统
- Docker 容器化部署
- 现代化 Web界面(控制台)

🚀 快速开始:
docker run -p 8000:8000 openai118/flowslide:latest

📚 文档: https://github.com/openai118/FlowSlide
🐳 Docker Hub: https://hub.docker.com/r/openai118/flowslide"

if errorlevel 1 (
    echo [警告] 标签创建失败（可能已存在）
) else (
    echo [信息] 推送标签（这将触发自动构建）...
    git push origin v1.0.0
    if errorlevel 1 (
        echo [错误] 标签推送失败
        pause
        exit /b 1
    )
    echo [成功] 标签推送完成！
)

echo.
echo ========================================
echo   部署完成！
echo ========================================
echo.
echo ✅ GitHub 仓库: https://github.com/openai118/FlowSlide
echo ✅ GitHub Actions: https://github.com/openai118/FlowSlide/actions
echo ✅ Docker Hub: https://hub.docker.com/r/openai118/flowslide
echo.
echo [提醒] 请确保在 GitHub 仓库中设置以下 Secrets:
echo   - DOCKER_USERNAME: openai118
echo   - DOCKER_PASSWORD: ^<your-docker-hub-access-token^>
echo.
echo [下一步] 
echo   1. 访问 GitHub Actions 查看构建状态
echo   2. 等待 Docker 镜像构建完成
echo   3. 测试: docker pull openai118/flowslide:latest
echo.

pause
