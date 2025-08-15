# 数据库与安全变量配置指南

本文档与 `.env.example` 保持一致，统一变量命名并补充所有相关配置项，便于安全部署与排错。

## 🔒 重要安全提醒

- 不要在代码或提交历史中硬编码敏感信息（数据库密码、JWT 密钥、API 密钥等）。
- `.env` 已在 `.gitignore` 中，勿提交到仓库。
- 建议生产环境使用密钥管理服务（AWS Secrets Manager / Azure Key Vault 等），并定期轮换密钥与密码。

## 📝 推荐配置方式

### 方式一：使用 DATABASE_URL（推荐）

```bash
# 完整数据库连接 URL（示例，与 .env.example 一致）
DATABASE_URL=postgresql://username:password@host:port/database?sslmode=require&options=-c%20search_path%3Dschema,public
```

说明：`DATABASE_URL` 的优先级高于分离变量。

### 方式二：使用分离变量

```bash
# 数据库配置
DB_HOST=localhost
DB_PORT=your-database-port
DB_NAME=your_database_name
DB_USER=your_db_user
DB_PASSWORD=your_secure_password
```

## 🌐 API 与存储配置

```bash
# 通用 REST API（如使用 Supabase，请将 API_URL 设置为项目 URL）
API_URL=https://your-api-endpoint.example.com
API_ANON_KEY=your-anon-key
API_SERVICE_KEY=your-service-key

# 存储
STORAGE_BUCKET=your-storage-bucket-name
STORAGE_PROVIDER=supabase
```

说明：本项目统一使用 `API_URL`/`API_ANON_KEY`/`API_SERVICE_KEY` 命名，替代早期文档的 `SUPABASE_*` 变量。

## ☁️ Cloudflare R2 备份

```bash
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_ENDPOINT=https://<accountid>.r2.cloudflarestorage.com
R2_BUCKET_NAME=flowslide-backup
```

## 💾 备份与健康检查

```bash
# 备份
BACKUP_SCHEDULE="0 2 * * *"   # 每天 02:00
BACKUP_RETENTION_DAYS=30
BACKUP_WEBHOOK_URL=

# 健康检查
SKIP_DB_CHECK=false
REQUIRE_DB=true
RUN_DB_SCHEMA_CHECK=true
```

## ⚙️ 性能与应用设置

```bash
# 性能
MAX_WORKERS=4
REQUEST_TIMEOUT=30
DB_POOL_SIZE=10

# 应用
PORT=8000
DEBUG=false
LOG_LEVEL=INFO
TEMP_CLEANUP_INTERVAL=24
```

## 🔐 安全设置

```bash
# JWT 与速率限制
JWT_SECRET=your_jwt_secret_key
API_RATE_LIMIT=100

# 上传限制（二选一，高优先级：字节数）
MAX_UPLOAD_SIZE=50           # MB
# MAX_FILE_SIZE=52428800     # bytes（若同时设置，优先使用该项）
# MAX_FILE_SIZE_MB=50        # 兼容旧变量

# 登录验证码（建议开启）
ENABLE_LOGIN_CAPTCHA=false
# Cloudflare Turnstile（推荐）
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=
# 或 hCaptcha
HCAPTCHA_SITE_KEY=
HCAPTCHA_SECRET_KEY=
```

## ✉️ 邮件通知（可选）

```bash
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=true
```

## 📈 监控与健康端点（可选）

```bash
METRICS_ENABLED=false
METRICS_PORT=9090
HEALTH_CHECK_ENDPOINT=/health
```

## 🧠 缓存（Redis，可选）

```bash
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=false
```

## 👩‍💻 开发设置

```bash
DEV_RELOAD=false
DEV_HOST=0.0.0.0
ALLOWED_HOSTS=localhost,127.0.0.1
```

## 👤 默认管理员（首次启动会自动创建）

```bash
ADMIN_NAME=admin
ADMIN_PASSWORD=admin123456
ADMIN_EMAIL=
```

## 🚀 使用方法

### 1) 创建 .env 文件

```bash
cp .env.example .env
# 编辑 .env，填入实际值（.env 不会被提交到 Git）
```

Windows PowerShell（可选）：

```powershell
Copy-Item .env.example .env
```

### 2) Docker Compose 部署

```bash
docker-compose --env-file .env up -d
# 或临时注入
DATABASE_URL="your-database-url" docker-compose up -d
```

### 3) 本地开发

```bash
export DATABASE_URL="your-database-url"
python landppt-integrated/run.py
```

## 🛡️ 最佳实践快速清单

- 生产环境启用 `sslmode=require`，并限制数据库用户权限。
- 将 `JWT_SECRET`、API 密钥等保管于安全服务并定期轮换。
- 控制上传大小和速率限制，开启登录验证码以防暴力破解。
- 定期备份，设置保留策略与告警 Webhook。
- 依赖和基础镜像定期更新，避免已知漏洞。

## 📚 相关文档

- PostgreSQL 连接字符串：https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING
- Docker Compose 环境变量：https://docs.docker.com/compose/environment-variables/
- FlowSlide 环境样例：`.env.example`
