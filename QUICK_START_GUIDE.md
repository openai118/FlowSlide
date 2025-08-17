# FlowSlide 快速启动指南

## 🚀 快速开始

### 前置要求
- Python 3.11+
- Git
- (可选) Docker & Docker Compose

### 1. 克隆项目
```bash
git clone https://github.com/openai118/FlowSlide.git
cd FlowSlide
```

### 2. 环境配置

#### 方式一：Python 虚拟环境
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 方式二：Docker (推荐)
```bash
# 使用 Docker Compose 启动
docker-compose up -d

# 查看日志
docker-compose logs -f flowslide
```

### 3. 配置环境变量
```bash
# 复制环境配置模板
cp .env.example .env

# 编辑配置文件
nano .env
```

#### 基本配置
```env
# 数据库配置 (可选，默认使用 SQLite)
DATABASE_URL=sqlite:///./data/flowslide.db

# 安全配置 (生产环境必须修改)
SECRET_KEY=your-secure-random-key-here

# AI 提供商配置 (至少配置一个)
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
GOOGLE_API_KEY=your-google-api-key

# 图像搜索 (可选)
PIXABAY_API_KEY=your-pixabay-api-key
UNSPLASH_ACCESS_KEY=your-unsplash-access-key

# 研究功能 (可选)
TAVILY_API_KEY=your-tavily-api-key
```

### 4. 启动应用

#### Python 方式
```bash
# 启动应用
python run.py
```

#### Docker 方式
```bash
# 已在步骤2启动，检查状态
docker-compose ps
```

### 5. 访问应用
- 🏠 主页: http://localhost:8000/home
- 🌐 控制台: http://localhost:8000/web
- 📚 API 文档: http://localhost:8000/docs
- 🩺 健康检查: http://localhost:8000/health

## 🔧 常见问题

### Q: 启动失败，提示模块未找到
A: 确保已安装所有依赖：
```bash
pip install -r requirements.txt
```

### Q: 数据库连接失败
A: 检查数据库配置：
```bash
# 运行数据库健康检查
python database_health_check.py

# 使用 SQLite (默认)
DATABASE_URL=sqlite:///./data/flowslide.db
```

### Q: AI 功能不可用
A: 确保至少配置了一个 AI 提供商的 API 密钥：
```env
OPENAI_API_KEY=your-api-key
```

### Q: 图像搜索不工作
A: 配置图像 API 密钥：
```env
PIXABAY_API_KEY=your-pixabay-api-key
UNSPLASH_ACCESS_KEY=your-unsplash-access-key
```

## 🎯 基本使用

### 1. 注册/登录
- 访问 http://localhost:8000/auth/login
- 首次启动会创建默认管理员账户：
  - 用户名: admin
  - 密码: admin123456
  - **请立即修改默认密码！**

### 2. 创建演示文稿
1. 登录后访问控制台
2. 选择演示场景（商务汇报、学术演讲等）
3. 输入主题和要求
4. 等待 AI 生成大纲
5. 确认大纲后生成完整演示文稿

### 3. 文件上传
- 支持 .docx, .pdf, .txt, .md 格式
- 可以基于上传文档生成演示文稿
- 自动提取文档内容和结构

### 4. 导出演示文稿
- HTML 格式：在线查看和演示
- PDF 格式：打印和分享
- PPTX 格式：PowerPoint 编辑

## 🛠️ 高级配置

### PostgreSQL 数据库
```env
DATABASE_URL=postgresql://username:password@localhost:5432/flowslide
```

### Redis 缓存 (可选)
```env
REDIS_URL=redis://localhost:6379/0
```

### HTTPS 配置
```env
USE_HTTPS=true
SSL_CERT_PATH=/path/to/cert.pem
SSL_KEY_PATH=/path/to/key.pem
```

### 性能调优
```env
# 工作进程数
MAX_WORKERS=4

# 数据库连接池
DB_POOL_SIZE=10

# 缓存配置
CACHE_TTL=3600
```

## 📊 监控和维护

### 健康检查
```bash
# 快速检查
curl http://localhost:8000/health

# 详细数据库检查
python database_health_check.py

# 性能诊断
python database_diagnosis.py
```

### 日志查看
```bash
# Docker 日志
docker-compose logs -f flowslide

# Python 应用日志
tail -f logs/flowslide.log
```

### 备份数据库
```bash
# SQLite 备份
cp data/flowslide.db data/flowslide_backup_$(date +%Y%m%d).db

# PostgreSQL 备份
pg_dump flowslide > backup_$(date +%Y%m%d).sql
```

## 🔒 安全建议

### 生产环境必做
1. **修改默认密钥**:
   ```env
   SECRET_KEY=your-secure-random-key-here
   ```

2. **修改默认管理员密码**

3. **配置 HTTPS**

4. **限制 CORS 来源**:
   ```env
   ALLOWED_ORIGINS=https://yourdomain.com
   ```

5. **启用登录验证码**:
   ```env
   ENABLE_LOGIN_CAPTCHA=true
   TURNSTILE_SITE_KEY=your-site-key
   TURNSTILE_SECRET_KEY=your-secret-key
   ```

## 📚 更多资源

- [完整部署指南](DEPLOYMENT_GUIDE.md)
- [数据库监控指南](DATABASE_MONITORING_GUIDE.md)
- [安全配置指南](DATABASE_SECURITY_GUIDE.md)
- [项目改进报告](PROJECT_IMPROVEMENTS.md)
- [API 文档](http://localhost:8000/docs)

## 🆘 获取帮助

如果遇到问题：
1. 查看 [故障排除文档](TROUBLESHOOTING.md)
2. 检查 [GitHub Issues](https://github.com/openai118/FlowSlide/issues)
3. 提交新的 Issue

---

🎉 恭喜！您已成功启动 FlowSlide。开始创建您的第一个 AI 演示文稿吧！
