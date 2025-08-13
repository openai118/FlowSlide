# Docker Hub 自动发布配置指南

## 🎯 概述

这个指南将帮助你配置GitHub Actions自动推送Docker镜像到Docker Hub。

## 📋 前置要求

### 1. Docker Hub 账户设置

1. **创建Docker Hub账户**: 访问 [Docker Hub](https://hub.docker.com/)
2. **创建仓库**: 
   - 仓库名建议: `your-username/land-ppt`
   - 设置为公开或私有仓库

### 2. 生成Docker Hub访问令牌

1. 登录Docker Hub
2. 进入 **Account Settings** → **Security**
3. 点击 **New Access Token**
3. **令牌名称**: `github-actions-land-ppt`
5. 权限: **Read, Write, Delete**
6. **保存生成的令牌** (只显示一次!)

## 🔐 GitHub Secrets 配置

在你的GitHub仓库中配置以下Secrets:

### 必需的Secrets:

1. **DOCKER_HUB_USERNAME**
   - 值: 你的Docker Hub用户名
   - 路径: `Settings` → `Secrets and variables` → `Actions`

2. **DOCKER_HUB_TOKEN**
   - 值: 上面生成的Docker Hub访问令牌
   - **注意**: 不是密码，是访问令牌

### 配置步骤:

```bash
# 在GitHub仓库页面
1. 点击 Settings
2. 点击 Secrets and variables → Actions
3. 点击 New repository secret
4. 添加以下两个secrets:
   - Name: DOCKER_HUB_USERNAME, Secret: your_dockerhub_username
   - Name: DOCKER_HUB_TOKEN, Secret: your_dockerhub_token
```

## 🚀 触发条件

工作流程将在以下情况下自动触发:

### 自动触发:
- ✅ **推送到main分支**: 发布 `latest` 标签
- ✅ **创建版本标签**: 发布版本号标签 (如 `v1.0.0`)
- ✅ **发布Release**: 发布完整版本

### 手动触发:
- ✅ **workflow_dispatch**: 在GitHub Actions页面手动运行

## 🏷️ 标签策略

生成的Docker镜像标签:

| 触发条件 | 生成的标签 | 示例 |
|----------|------------|------|
| 推送到main分支 | `latest`, `YYYYMMDD-sha` | `latest`, `20250813-abc1234` |
| 版本标签 | `vX.Y.Z`, `vX.Y`, `vX` | `v2.0.0`, `v2.0`, `v2` |
| 其他分支 | `branch-name` | `develop`, `feature-auth` |

## 📦 多平台支持

Docker镜像将构建为多平台:
- ✅ `linux/amd64` (x86_64)
- ✅ `linux/arm64` (ARM64/Apple Silicon)

## 🧪 使用发布的镜像

### 基本使用:

```bash
# 拉取最新镜像
docker pull your-username/land-ppt:latest

# 运行容器
docker run -d \
  --name land-ppt \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@host:port/db" \
  your-username/land-ppt:latest
```

### 使用Docker Compose:

```yaml
version: '3.8'
services:
  land-ppt:
    image: your-username/land-ppt:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@host:port/db
      - API_URL=https://your-api-endpoint.com
      - API_ANON_KEY=your-api-key
    restart: unless-stopped
```

### 指定版本:

```bash
# 使用特定版本
docker pull your-username/land-ppt:v2.0.0
docker run -d your-username/land-ppt:v2.0.0

# 使用日期标签
docker pull your-username/land-ppt:20250813-abc1234
```

## 🔧 自定义配置

### 修改镜像名称:

在 `.github/workflows/docker-hub-publish.yml` 中修改:

```yaml
env:
  IMAGE_NAME: your-custom-name  # 改为你想要的镜像名
```

### 修改平台支持:

```yaml
platforms: linux/amd64  # 只构建 x86_64
# 或
platforms: linux/amd64,linux/arm64,linux/arm/v7  # 添加更多平台
```

### 修改触发条件:

```yaml
on:
  push:
    branches: [ main, develop ]  # 添加更多分支
    tags: [ 'v*.*.*', 'release-*' ]  # 修改标签模式
```

## 📊 监控和日志

### 查看构建状态:
1. GitHub仓库 → Actions标签页
2. 选择 "Docker Hub Publish" 工作流程
3. 查看构建日志和状态

### 验证发布:
1. 访问 Docker Hub 仓库页面
2. 检查 Tags 标签页
3. 确认镜像大小和更新时间

## 🛠️ 故障排查

### 常见问题:

**1. 认证失败**
```
Error: Cannot perform an interactive login from a non TTY device
```
**解决**: 检查DOCKER_HUB_USERNAME和DOCKER_HUB_TOKEN是否正确配置

**2. 权限被拒绝**
```
Error: denied: requested access to the resource is denied
```
**解决**: 确保Docker Hub令牌有写入权限，仓库名称正确

**3. 平台构建失败**
```
Error: failed to solve: failed to build for platform linux/arm64
```
**解决**: 移除arm64平台或检查Dockerfile的多平台兼容性

**4. 镜像过大**
```
Warning: Image size exceeds Docker Hub limits
```
**解决**: 优化Dockerfile，使用多阶段构建，清理缓存

### 测试命令:

```bash
# 本地测试构建
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t your-username/land-ppt:test \
  --push .

# 测试镜像运行
docker run --rm your-username/land-ppt:test python --version
```

## 🎯 最佳实践

1. **版本管理**: 使用语义化版本号 (v1.0.0, v1.1.0, v2.0.0)
2. **安全**: 定期轮换Docker Hub访问令牌
3. **优化**: 使用多阶段构建减小镜像大小
4. **测试**: 在推送前本地测试Docker镜像
5. **文档**: 保持README和Docker Hub描述同步

## 📚 相关链接

- [Docker Hub官方文档](https://docs.docker.com/docker-hub/)
- [GitHub Actions文档](https://docs.github.com/en/actions)
- [Docker Buildx文档](https://docs.docker.com/buildx/)
- [多平台构建指南](https://docs.docker.com/build/building/multi-platform/)
