# GitHub 快速推送脚本
# 使用方法: .\push_to_github.ps1 -RepoName "landppt-integrated" -UserName "your-github-username"

param(
    [Parameter(Mandatory=$true)]
    [string]$RepoName,
    
    [Parameter(Mandatory=$true)]
    [string]$UserName,
    
    [string]$CommitMessage = "Initial commit: LandPPT integrated with database monitoring and R2 backup"
)

Write-Host "🚀 开始准备推送到 GitHub..." -ForegroundColor Green

# 检查是否已经是 Git 仓库
if (-not (Test-Path ".git")) {
    Write-Host "📁 初始化 Git 仓库..." -ForegroundColor Yellow
    git init
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Git 初始化失败" -ForegroundColor Red
        exit 1
    }
}

# 检查 Git 用户配置
$gitUser = git config user.name
$gitEmail = git config user.email

if (-not $gitUser) {
    $inputUser = Read-Host "请输入您的 Git 用户名"
    git config user.name $inputUser
}

if (-not $gitEmail) {
    $inputEmail = Read-Host "请输入您的 Git 邮箱"
    git config user.email $inputEmail
}

Write-Host "👤 Git 用户配置:" -ForegroundColor Cyan
Write-Host "   用户名: $(git config user.name)" -ForegroundColor Gray
Write-Host "   邮箱: $(git config user.email)" -ForegroundColor Gray

# 检查远程仓库配置
$remoteUrl = git remote get-url origin 2>$null
if (-not $remoteUrl) {
    Write-Host "🔗 配置远程仓库..." -ForegroundColor Yellow
    $repoUrl = "https://github.com/$UserName/$RepoName.git"
    git remote add origin $repoUrl
    Write-Host "   远程仓库: $repoUrl" -ForegroundColor Gray
} else {
    Write-Host "🔗 远程仓库已配置: $remoteUrl" -ForegroundColor Gray
}

# 检查当前分支
$currentBranch = git branch --show-current
if ($currentBranch -ne "main") {
    Write-Host "🌿 切换到 main 分支..." -ForegroundColor Yellow
    git checkout -B main
}

# 添加文件到暂存区
Write-Host "📦 添加文件到暂存区..." -ForegroundColor Yellow
git add .

# 检查是否有文件需要提交
$status = git status --porcelain
if (-not $status) {
    Write-Host "✅ 没有需要提交的更改" -ForegroundColor Green
    exit 0
}

# 显示将要提交的文件
Write-Host "📋 将要提交的文件:" -ForegroundColor Cyan
git status --short

# 创建提交
Write-Host "💾 创建提交..." -ForegroundColor Yellow
git commit -m $CommitMessage
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 提交失败" -ForegroundColor Red
    exit 1
}

# 推送到 GitHub
Write-Host "🚀 推送到 GitHub..." -ForegroundColor Yellow
Write-Host "⚠️  如果是首次推送，可能需要输入 GitHub 用户名和 Personal Access Token" -ForegroundColor Yellow

git push -u origin main
if ($LASTEXITCODE -eq 0) {
    Write-Host "🎉 推送成功！" -ForegroundColor Green
    Write-Host "🌐 访问您的仓库: https://github.com/$UserName/$RepoName" -ForegroundColor Cyan
} else {
    Write-Host "❌ 推送失败" -ForegroundColor Red
    Write-Host "💡 可能的解决方案:" -ForegroundColor Yellow
    Write-Host "   1. 检查网络连接" -ForegroundColor Gray
    Write-Host "   2. 确认 GitHub 用户名正确" -ForegroundColor Gray
    Write-Host "   3. 使用 Personal Access Token 作为密码" -ForegroundColor Gray
    Write-Host "   4. 确认仓库已在 GitHub 上创建" -ForegroundColor Gray
}

Write-Host "`n📚 下一步:" -ForegroundColor Cyan
Write-Host "   1. 在 GitHub 上完善仓库描述" -ForegroundColor Gray
Write-Host "   2. 添加适当的主题标签" -ForegroundColor Gray
Write-Host "   3. 设置仓库的可见性" -ForegroundColor Gray
Write-Host "   4. 邀请协作者 (如需要)" -ForegroundColor Gray
