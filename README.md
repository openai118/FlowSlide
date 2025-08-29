# FlowSlide - AI-Powered Presentation Generator

![FlowSlide Logo](https://img.shields.io/badge/FlowSlide-AI%20Presentation-blue?style=for-the-badge)
![Version](https://img.shields.io/badge/version-1.0.0-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-blue)
![Docker](https://img.shields.io/badge/deployment-Docker-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

> 🚀 **Enterprise-ready AI presentation generator with universal PostgreSQL monitoring and automated backup**

一个功能强大的 AI 演示文稿生成器，提供流畅的幻灯片创作体验。集成了企业级数据库监控和自动备份功能，支持多种 AI 模型，自动图像配图，智能研究功能，并提供完整的运维监控体系。

## ✨ 主要特性

### 🎯 AI 演示文稿生成
- **多 AI 模型支持**: OpenAI GPT-4, Anthropic Claude, Google Gemini, Ollama 本地模型
- **智能图像配图**: 集成 Pixabay, Unsplash API 自动匹配图片
- **智能研究功能**: 使用 Tavily API 进行实时信息搜索
- **多格式导出**: HTML, PDF, PPTX 等多种格式
- **丰富模板系统**: 内置多种专业演示模板

### 🔄 智能数据库架构

FlowSlide 采用智能数据库架构，优先保证运行速度和可靠性：

#### 数据库模式选择

**1. 本地优先模式 (DATABASE_MODE=local)** - 推荐用于开发和个人使用
- ✅ **快速启动**：使用本地SQLite数据库，无需外部依赖
- 🔄 **可选同步**：可配置外部数据库作为备份/同步目标
- ☁️ **云备份**：支持R2自动备份
- 🎯 **最佳实践**：开发环境默认选择

**2. 外部数据库模式 (DATABASE_MODE=external)** - 推荐用于生产环境
- 🏢 **企业级**：直接使用PostgreSQL等企业数据库
- ⚡ **高性能**：连接池和性能优化
- 🔧 **运维友好**：完整的监控和维护工具

**3. 混合模式 (DATABASE_MODE=hybrid)** - 推荐用于分布式部署
- 🔄 **实时同步**：本地和外部数据库双写
- 🛡️ **高可用**：任意一端故障自动切换
- 📊 **负载均衡**：智能读写分离

#### 配置示例

```bash
# 开发环境 - 本地优先
DATABASE_MODE=local
DATABASE_URL=postgresql://user:pass@host:port/db  # 可选，用于备份

# 生产环境 - 外部数据库
DATABASE_MODE=external
DATABASE_URL=postgresql://user:pass@host:port/db

# 分布式 - 混合模式
DATABASE_MODE=hybrid
DATABASE_URL=postgresql://user:pass@host:port/db
ENABLE_DATA_SYNC=true
SYNC_INTERVAL=300
```

#### 🛡️ 三层备份保障

##### 1. 本地自动备份
- 📁 定时本地快照
- 🔧 自动清理过期备份
- 📊 备份状态监控

##### 2. 外部数据库同步
- 🔄 实时/定时数据同步
- ⚡ 增量同步优化
- 🛡️ 冲突解决机制

##### 3. 云端R2备份
- ☁️ Cloudflare R2对象存储
- 🌐 全球CDN加速
- 🔒 企业级安全性
- 💰 成本优化存储

### 🔄 智能双向同步系统

FlowSlide 集成了先进的智能双向同步系统，支持本地SQLite与外部PostgreSQL数据库之间的无缝数据同步：

#### 同步特性

##### 🔄 双向自动同步
- 📤 **本地→外部**: 新建用户和数据自动同步到云端
- 📥 **外部→本地**: 云端数据自动同步到本地SQLite
- ⏰ **定时同步**: 每5分钟自动执行增量同步
- 🔍 **智能检测**: 自动检测数据库配置并启用相应同步策略

##### 🛡️ 冲突解决机制
- 🔄 **版本控制**: 基于时间戳的冲突检测和解决
- 📊 **数据合并**: 智能合并重复记录，避免数据丢失
- 📝 **操作日志**: 完整的同步操作记录和状态跟踪

##### ⚡ 性能优化
- 🚀 **增量同步**: 只同步变更数据，减少网络传输
- 🏗️ **批量处理**: 批量操作提高同步效率
- 💾 **本地缓存**: 本地SQLite保证快速访问

#### 同步配置

```bash
# 启用数据同步
ENABLE_DATA_SYNC=true

# 同步间隔（秒）
SYNC_INTERVAL=300

# 同步方向（可组合）
SYNC_DIRECTIONS=local_to_external,external_to_local

# 同步模式
SYNC_MODE=incremental  # incremental 或 full
```

#### 同步管理API

```bash
# 获取同步状态
GET /api/database/sync/status

# 手动触发同步
POST /api/database/sync/trigger

# 获取同步配置
GET /api/database/sync/config
```

#### 同步演示

运行同步功能演示：

```bash
# 运行演示脚本
python sync_demo.py

# 启动应用程序
python -m src.flowslide.main

# 访问同步状态页面
# http://localhost:8000/api/database/sync/status
```

### 🐳 容器化部署
- **Docker 多阶段构建**: 优化的镜像大小和安全性
- **健康检查机制**: 自动监控和故障恢复
- **环境变量配置**: 生产环境就绪的配置管理
- **资源限制**: 内存和 CPU 使用控制

## 🚀 快速开始

### 环境要求

- **Python 3.11+**
- **Git** (用于版本控制)
- **PostgreSQL 数据库** (支持任何 PostgreSQL 兼容服务)
- **Docker & Docker Compose** (推荐用于生产部署)
- **Cloudflare R2 存储** (用于备份功能，可选)

### 1. 克隆项目

```bash
git clone https://github.com/openai118/FlowSlide.git
cd FlowSlide
```

### 2. 配置环境变量

```bash
# 复制环境配置模板
cp .env.example .env

# 编辑配置文件
nano .env
```

**主要配置项：**
```bash
# 数据库配置（推荐使用 DATABASE_URL）
DATABASE_URL=postgresql://username:password@host:port/database?sslmode=require

# 或者使用分离的环境变量
DB_HOST=your-database-host
DB_USER=your_db_user
DB_PASSWORD=your_secure_password

# API 配置（如果使用 Supabase 等带 API 的服务）
API_URL=https://your-api-endpoint.com
API_ANON_KEY=your-api-key
API_SERVICE_KEY=your-service-key

# 存储配置（可选）
STORAGE_BUCKET=your-bucket-name
STORAGE_PROVIDER=postgresql  # 或 supabase, aws-s3 等

提示：
- 未设置 DATABASE_URL 时，系统将默认使用本地 SQLite（./data/flowslide.db），可直接运行；
- 设置了有效的 DATABASE_URL（如 PostgreSQL）后将自动使用该数据库；
- 未配置 R2 备份相关变量时，备份脚本会跳过备份并正常退出，不影响程序运行。
```

### 3. 部署方式

#### 方式一：Docker Compose 部署（推荐）

```bash
# 使用 Docker Compose 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker logs flowslide
```

#### 方式二：Docker Hub 镜像部署

```bash
# 从 Docker Hub 拉取最新镜像
docker pull openai118/flowslide:latest

# 运行容器
docker run -d \
  --name flowslide \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@host:port/db?sslmode=require" \
  -e API_URL="https://your-api-endpoint.com" \
  -e API_ANON_KEY="your-api-key" \
  openai118/flowslide:latest
```

#### 方式三：本地开发

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 可选：安装 Apryse SDK 以支持 PPTX 导出功能
pip install --extra-index-url https://pypi.apryse.com apryse-sdk>=11.6.0

# 4. 启动应用 (选择其中一种方式)

# 方式A: 使用Python脚本启动
python start_flowslide.py

# 方式B: 使用批处理文件 (Windows)
start.bat

# 方式C: 使用PowerShell脚本 (Windows)
powershell -ExecutionPolicy Bypass -File start.ps1

# 方式D: 直接使用uvicorn
.venv\Scripts\python.exe -m uvicorn src.flowslide.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🚪 访问入口

- 🏠 首页(公共): http://localhost:8000/home
- 🌐 Web界面(控制台): http://localhost:8000/web
- 📚 API 文档: http://localhost:8000/docs
- 🩺 健康检查: http://localhost:8000/health

## 📊 监控和测试

### 🧪 测试套件
项目包含完整的测试框架：

```bash
# 运行所有测试
python -m pytest

# 运行特定测试
python -m pytest tests/test_auth.py

# 运行性能测试
python tests/performance/run_performance_tests.py
```

### 🔒 安全扫描
```bash
# 运行安全扫描
python security/security_scan.py
```

## 🔄 备份和恢复

### 📦 自动备份到 Cloudflare R2

```bash
# 配置 R2 环境变量
export R2_ACCESS_KEY_ID=your_access_key
export R2_SECRET_ACCESS_KEY=your_secret_key
export R2_ENDPOINT=https://your-account.r2.cloudflarestorage.com
export R2_BUCKET_NAME=your-backup-bucket

# 运行备份
./backup_to_r2_enhanced.sh
```

### 🔄 从备份恢复

```bash
# 从 R2 恢复数据库
./restore_from_r2.sh backup_filename.sql.gz
```

## 🏗️ 架构设计

### 核心组件

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FlowSlide App │────│  PostgreSQL DB   │────│  Monitoring     │
│                 │    │                  │    │  Tools          │
│ • AI Generation │    │ • User Data      │    │                 │
│ • Image Search  │    │ • Sessions       │    │ • Health Check  │
│ • Template Eng  │    │ • File Metadata  │    │ • Diagnosis     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │                        │                        │
         v                        v                        v
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   File Storage  │    │   Backup System  │    │   Monitoring    │
│                 │    │                  │    │   Dashboard     │
│ • Generated PPT │    │ • Cloudflare R2  │    │ • Health Status │
│ • Images        │    │ • Scheduled Jobs │    │ • Performance   │
│ • Templates     │    │ • Incremental    │    │ • Alerts        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### 数据库兼容性

| 数据库服务 | 基本功能 | API 测试 | 存储测试 | 备份支持 |
|------------|----------|----------|----------|----------|
| PostgreSQL | ✅ | ❌ | ❌ | ✅ |
| Supabase | ✅ | ✅ | ✅ | ✅ |
| Neon | ✅ | ❌ | ❌ | ✅ |
| AWS RDS | ✅ | ❌ | ❌ | ✅ |
| Google Cloud SQL | ✅ | ❌ | ❌ | ✅ |
| Azure Database | ✅ | ❌ | ❌ | ✅ |

## 🛠️ 故障排查

### 常见问题

**连接失败**
```bash
# 检查网络连通性
telnet your-host your-port

# 检查 SSL 配置
psql "postgresql://user:pass@host:port/db?sslmode=disable"
```

**权限问题**
```sql
-- 检查用户权限
SELECT * FROM information_schema.role_table_grants WHERE grantee = 'your_user';

-- 检查模式权限
SELECT schema_name FROM information_schema.schemata;
```

**性能问题**
```sql
-- 启用统计扩展
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 检查慢查询
SELECT query, mean_time FROM pg_stat_statements ORDER BY_mean_time DESC LIMIT 10;
```

## 📚 文档

- [PostgreSQL 兼容性指南](POSTGRESQL_COMPATIBILITY_GUIDE.md)
- [数据库安全配置指南](DATABASE_SECURITY_GUIDE.md)
- [数据库监控指南](DATABASE_MONITORING_GUIDE.md)
- [部署指南](DEPLOYMENT_GUIDE.md)
- [集成指南](INTEGRATION_GUIDE.md)
- [Docker Hub 自动发布配置](DOCKER_HUB_SETUP.md)

## 🤝 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

### 致谢与来源

本项目基于开源项目 LandPPT（Apache-2.0）进行二次开发与重构：
- 原始项目仓库：https://github.com/sligter/LandPPT
- 许可证：Apache License 2.0

我们在遵循 Apache-2.0 许可条款的前提下，对架构、路由、鉴权、主题与文档进行了深度改造与增强。

## 📝 更新日志

### v1.0.0 (2025-08-15)
- 核心修复与稳定性：
  - 重写 `src/flowslide/core/simple_config.py`，修复启动 NameError/IndentationError；
  - 初始化数据库、安全、上传、缓存、默认管理员与验证码配置更健壮。
- AI 提供商配置：
  - 新增 Anthropic `base_url`（默认 `https://api.anthropic.com`）；
  - 新增 Google Generative AI `base_url`（默认 `https://generativelanguage.googleapis`）；
  - 前端测试与后端运行均尊重自定义 Base URL。
- 鉴权与体验：
  - `/home` 保持公共页面，登录后导航栏状态正确；
  - 登录/注册成功后跳转到 `/home`（替代旧的 `/dashboard`）。
- 仓库与文档：
  - 将 `docs/_site/` 加入 `.gitignore`；清理临时产物，移除本地 SQLite 数据库文件出仓；
  - 元数据指向 `openai118/FlowSlide`，完善部署/集成文档链接。

作为首个公开版本（Initial Release），聚合了近期全部改动并完成基础功能与部署路径的打磨。

## 📄 许可证

本项目基于 Apache License 2.0 开源 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 支持

如果您遇到问题或有疑问：

1. 查看 [PostgreSQL 兼容性指南](POSTGRESQL_COMPATIBILITY_GUIDE.md)
2. 搜索 [Issues](https://github.com/openai118/FlowSlide/issues)
3. 创建新的 Issue
4. 联系维护者

---

⭐ 如果这个项目对您有帮助，请给个 Star！
