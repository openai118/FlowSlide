# 🚀 FlowSlide GitHub & Docker Hub 部署指南

## 📋 部署准备工作

### 1. GitHub Repository 设置

#### 创建新仓库
1. 访问 https://github.com/openai118
2. 点击 "New repository"
3. 仓库名称: `FlowSlide`
4. 描述: `AI-powered presentation generator with enterprise-grade monitoring and backup`
5. 设置为 Public
6. 不要初始化 README（我们已有现成的文件）

#### 配置 Secrets
在新创建的 GitHub 仓库中设置以下 Secrets:

1. 进入 `Settings` → `Secrets and variables` → `Actions`
2. 添加以下 Repository secrets:

```bash
# Docker Hub 认证
DOCKER_USERNAME=openai118
DOCKER_PASSWORD=<your-docker-hub-access-token>
```

**获取 Docker Hub Access Token:**
1. 登录 https://hub.docker.com
2. 点击右上角头像 → "Account Settings"
3. 选择 "Security" 标签页
4. 点击 "New Access Token"
5. 名称: `flowslide-github-actions`
6. 权限: `Read, Write, Delete`
7. 复制生成的 Token 作为 `DOCKER_PASSWORD`

### 2. Docker Hub Repository 设置

#### 创建 Docker Hub 仓库
1. 登录 https://hub.docker.com
2. 点击 "Create Repository"
3. 仓库名称: `flowslide`
4. 命名空间: `openai118`
5. 完整名称: `openai118/flowslide`
6. 可见性: Public
7. 描述: `FlowSlide - AI-powered presentation generator`

## 🚀 部署步骤

### 步骤 1: 初始化 Git 仓库并推送

```bash
# 确保在项目根目录
cd "e:\pyprojects\try1\landppt-integrated"

# 初始化 Git（如果还未初始化）
git init

# 添加 GitHub 远程仓库
git remote add origin https://github.com/openai118/FlowSlide.git

# 检查所有文件状态
git status

# 添加所有文件到暂存区
git add .

# 提交更改
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

# 设置主分支
git branch -M main

# 推送到 GitHub
git push -u origin main
```

### 步骤 2: 创建发布版本

```bash
# 创建版本标签
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

# 推送标签（这将触发自动构建和发布）
git push origin v1.0.0
```

### 步骤 3: 验证自动构建

推送标签后，GitHub Actions 将自动开始构建过程：

1. **查看构建状态:**
   - 访问 https://github.com/openai118/FlowSlide/actions
   - 查看 "Release" 工作流运行状态

2. **构建内容:**
   - 多架构 Docker 镜像 (linux/amd64, linux/arm64)
   - 自动推送到 Docker Hub
   - 创建 GitHub Release
   - 更新 Docker Hub 描述

3. **预期结果:**
   - ✅ Docker Hub: https://hub.docker.com/r/openai118/flowslide
   - ✅ GitHub Release: https://github.com/openai118/FlowSlide/releases
   - ✅ 镜像标签: `latest`, `v1.0.0`, `1.0`, `1`

## 🔍 部署验证

### 自动验证（如果有 Docker）
如果您有其他带 Docker 的机器，可以运行验证脚本：

```bash
# 下载验证脚本
curl -o verify-deployment.sh https://raw.githubusercontent.com/openai118/FlowSlide/main/scripts/verify-deployment.sh

# 执行验证
chmod +x verify-deployment.sh
./verify-deployment.sh
```

### 手动验证

1. **测试镜像拉取:**
```bash
docker pull openai118/flowslide:latest
```

2. **快速启动测试:**
```bash
docker run -d --name flowslide-test \
  -p 8000:8000 \
  -e DATABASE_URL="sqlite:///app/data/flowslide.db" \
  openai118/flowslide:latest
```

3. **访问测试:**
   - 首页(公共): http://localhost:8000/home
   - 主页: http://localhost:8000
   - API 文档: http://localhost:8000/docs
   - 健康检查: http://localhost:8000/health

4. **清理测试:**
```bash
docker stop flowslide-test && docker rm flowslide-test
```

## 📋 构建状态检查

### GitHub Actions 状态检查清单

- [ ] **Release 工作流**: 
  - 地址: https://github.com/openai118/FlowSlide/actions/workflows/release.yml
  - 状态: 应显示绿色✅

- [ ] **Docker Build 工作流**:
  - 地址: https://github.com/openai118/FlowSlide/actions/workflows/docker-build-push.yml
  - 状态: 应显示绿色✅

### Docker Hub 检查清单

- [ ] **仓库创建**: https://hub.docker.com/r/openai118/flowslide
- [ ] **镜像推送**: 应显示最新的 tags
- [ ] **描述更新**: 应显示 FlowSlide 相关信息
- [ ] **架构支持**: 应支持 amd64 和 arm64

### GitHub Repository 检查清单

- [ ] **代码推送**: 所有文件正确推送
- [ ] **Release 创建**: https://github.com/openai118/FlowSlide/releases
- [ ] **README 显示**: FlowSlide 品牌信息正确显示
- [ ] **工作流文件**: .github/workflows/ 目录包含所有工作流

## 🎉 部署完成后

### 用户使用指南

用户现在可以通过以下方式使用 FlowSlide:

```bash
# 方式 1: 直接运行
docker run -p 8000:8000 openai118/flowslide:latest

# 方式 2: 使用 docker-compose
git clone https://github.com/openai118/FlowSlide.git
cd FlowSlide
docker-compose up -d

# 方式 3: 生产环境（PostgreSQL）
docker-compose -f docker-compose.postgres.yml up -d
```

### 访问服务
- **首页(公共)**: http://localhost:8000/home
- **Web界面(控制台)**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

### 环境变量配置
详细的环境变量配置请参考 [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)

## 🔧 故障排除

### 常见问题

1. **GitHub Actions 失败**
   - 检查 Docker Hub secrets 是否正确设置
   - 确认仓库有正确的权限

2. **Docker 推送失败**
   - 验证 Docker Hub access token 权限
   - 检查仓库名称是否正确

3. **镜像拉取失败**
   - 确认网络连接正常
   - 检查 Docker Hub 仓库是否为 public

### 获取帮助

- **GitHub Issues**: https://github.com/openai118/FlowSlide/issues
- **Docker Hub**: https://hub.docker.com/r/openai118/flowslide
- **Documentation**: https://github.com/openai118/FlowSlide#readme

---

🎊 **恭喜！FlowSlide 现已成功部署到 GitHub 和 Docker Hub！**

用户可以立即开始使用：`docker pull openai118/flowslide:latest`
